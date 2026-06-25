"""ColorROI Analyzer 的图像处理和颜色分析核心逻辑。

本模块对应原 R Shiny 项目中 `app.R` 的计算部分。界面层只负责收集图片、
ROI 边界和毛发标注；真正可测试、可复用的逻辑集中放在这里，便于后续
用命令行脚本、Streamlit 或批量任务复用同一套算法。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import color
from sklearn.cluster import KMeans


COLOR_LABELS = ("black", "brown", "gray", "blue")


@dataclass(frozen=True)
class ClusterResult:
    """Lab 四分类结果。

    centers:
        KMeans 聚类中心，列顺序固定为 L*, a*, b*。
    cluster_id:
        每个 ROI 像素对应的聚类编号，编号从 0 开始。
    label_clusters:
        黑、棕、灰、蓝各自对应的聚类编号；蓝色不存在时为空列表。
    ratios:
        黑、棕、灰、蓝比例，四项之和为 1。
    dmdi:
        按原项目公式计算出的 DMDI：0×黑 + 1×棕 + 2×灰 + 3×蓝。
    """

    centers: np.ndarray
    cluster_id: np.ndarray
    label_clusters: dict[str, list[int]]
    ratios: dict[str, float]
    dmdi: float


def load_rgb_image(path: str | Path) -> np.ndarray:
    """读取图片并转换为 0-1 范围的 RGB 浮点数组。

    原 R 版只做尺度保护，不做全局对比度拉伸。这里保持同样策略，避免
    每张图片被单独归一化后破坏真实颜色比例。
    """

    image = Image.open(path)
    if image.mode not in {"RGB", "RGBA", "L"}:
        image = image.convert("RGB")
    elif image.mode == "RGBA":
        # 透明通道不参与颜色分析；使用白底合成，避免透明像素被当成黑色。
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image).convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")

    arr = np.asarray(image, dtype=np.float32)
    if arr.max(initial=0) > 1:
        arr = arr / 255.0
    return np.clip(arr[:, :, :3], 0.0, 1.0)


def match_dims(mask: np.ndarray | None, target_h: int, target_w: int) -> np.ndarray:
    """把 mask 裁剪或补零到目标尺寸。

    浏览器画布、图片解码和预览缩放之间可能出现 1-2 像素差异，因此算法入口
    统一做一次防御性对齐，避免后续布尔索引报错。
    """

    if mask is None:
        return np.zeros((target_h, target_w), dtype=bool)

    mat = np.asarray(mask)
    if mat.shape == (target_h, target_w):
        return mat.astype(bool)
    if mat.shape == (target_w, target_h):
        mat = mat.T

    out = np.zeros((target_h, target_w), dtype=bool)
    copy_h = min(mat.shape[0], target_h)
    copy_w = min(mat.shape[1], target_w)
    out[:copy_h, :copy_w] = mat[:copy_h, :copy_w].astype(bool)
    return out


def resize_mask_to_image(mask: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """使用最近邻采样把显示画布 mask 映射回原图尺寸。"""

    mask_bool = np.asarray(mask).astype(bool)
    source_h, source_w = mask_bool.shape[:2]
    if (source_h, source_w) == (target_h, target_w):
        return mask_bool
    if (source_h, source_w) == (target_w, target_h):
        mask_bool = mask_bool.T
        source_h, source_w = mask_bool.shape

    row_idx = np.clip(
        np.round((np.arange(target_h) + 0.5) * source_h / target_h - 0.5).astype(int),
        0,
        source_h - 1,
    )
    col_idx = np.clip(
        np.round((np.arange(target_w) + 0.5) * source_w / target_w - 0.5).astype(int),
        0,
        source_w - 1,
    )
    return mask_bool[row_idx[:, None], col_idx[None, :]]


def fill_roi_from_boundary(boundary: np.ndarray, min_pixels: int = 50) -> np.ndarray:
    """从用户手绘黄色边界生成实心 ROI。

    实现思路与 R 版保持一致：
    1. 先膨胀边界，补齐手绘时常见的轻微断点；
    2. 从图片四周对“非边界区域”做外部 flood fill；
    3. 不能从外部连通到的区域就是被边界围住的 ROI；
    4. 如果 ROI 太小，再用二值孔洞填充作为兜底。
    """

    boundary_bool = np.asarray(boundary).astype(bool)
    if not boundary_bool.any():
        return np.zeros_like(boundary_bool, dtype=bool)

    wall = ndimage.binary_dilation(boundary_bool, structure=_disc_structure(11))
    passable = ~wall
    outside = np.zeros_like(passable, dtype=bool)

    # 四条边上的 passable 像素作为外部背景种子。binary_propagation 会在 passable
    # 内扩散，速度比 Python 手写队列更稳定，也更适合大图。
    seeds = np.zeros_like(passable, dtype=bool)
    seeds[0, :] = passable[0, :]
    seeds[-1, :] = passable[-1, :]
    seeds[:, 0] = passable[:, 0]
    seeds[:, -1] = passable[:, -1]
    if seeds.any():
        outside = ndimage.binary_propagation(seeds, mask=passable)

    roi = (~outside) & (~wall)
    if int(roi.sum()) < min_pixels:
        filled = ndimage.binary_fill_holes(wall)
        roi = filled & (~wall)
    return roi.astype(bool)


def inpaint_masked_pixels(
    img: np.ndarray,
    mask: np.ndarray,
    roi: np.ndarray | None = None,
    max_iter: int = 40,
) -> np.ndarray:
    """用邻域有效像素逐步填补红色毛发标注区域。

    该方法不是医学级修复模型，而是复刻原 R 版的轻量局部补色策略：对细毛发
    或小遮挡区域，逐轮用周围有效像素均值向内扩散，避免红色标注区域直接影响
    ROI 颜色聚类。
    """

    img_arr = np.asarray(img, dtype=np.float32)
    pending_template = np.asarray(mask).astype(bool)
    if roi is not None:
        pending_template &= np.asarray(roi).astype(bool)
    if not pending_template.any():
        return img_arr.copy()

    pending_template = ndimage.binary_dilation(pending_template, structure=_disc_structure(3))
    kernel = np.ones((3, 3), dtype=np.float32)
    out = img_arr.copy()

    for ch in range(3):
        channel = out[:, :, ch].copy()
        pending = pending_template.copy()
        valid = ~pending

        for _ in range(max_iter):
            if not pending.any():
                break
            valid_float = valid.astype(np.float32)
            neighbor_sum = ndimage.convolve(channel * valid_float, kernel, mode="nearest")
            neighbor_count = ndimage.convolve(valid_float, kernel, mode="nearest")
            fillable = pending & (neighbor_count > 0)
            if not fillable.any():
                break

            channel[fillable] = neighbor_sum[fillable] / neighbor_count[fillable]
            valid[fillable] = True
            pending[fillable] = False

        if pending.any():
            # 极端孤立区域用局部中值兜底，保证不会留下 NaN 或未定义像素。
            fallback = ndimage.median_filter(channel, size=9, mode="nearest")
            channel[pending] = fallback[pending]

        out[:, :, ch] = np.clip(channel, 0.0, 1.0)

    return out


def mask_to_boundary(mask: np.ndarray, width: int = 3) -> np.ndarray:
    """把实心 ROI mask 转换成闭合边界 mask。

    分析函数的入口沿用“黄色边界 -> 填充 ROI”的交互模型。这个工具函数用于
    测试、脚本或其它显式传入的实心 ROI mask 转换，不会在应用里自动生成 ROI。
    """

    mask_bool = np.asarray(mask).astype(bool)
    if not mask_bool.any():
        return np.zeros(mask_bool.shape, dtype=bool)

    eroded = ndimage.binary_erosion(mask_bool, structure=_disc_structure(max(1, width)))
    return (mask_bool & (~eroded)).astype(bool)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """把 0-1 RGB 像素转换为 CIELAB，返回列顺序为 L*, a*, b* 的数组。"""

    rgb_arr = np.asarray(rgb, dtype=np.float32)
    if rgb_arr.ndim == 1:
        rgb_arr = rgb_arr.reshape(1, 3)
    rgb_arr = np.clip(rgb_arr, 0.0, 1.0)
    lab = color.rgb2lab(rgb_arr.reshape(-1, 1, 3)).reshape(-1, 3)
    return lab.astype(np.float32)


def cluster_lab_colors(lab: np.ndarray, k: int = 4, sample_limit: int = 12000) -> ClusterResult | None:
    """基于 Lab 空间做 KMeans 四分类，并稳定映射为黑、棕、灰、蓝。

    标签命名规则复刻 R 版：
    - L* 最低的是黑；
    - 只有 b* < 0 的候选才允许命名为蓝，避免把“相对最不黄”的皮肤误算成蓝；
    - 剩余类别中色度 C* 最低的是灰；
    - 剩余类别归为棕。
    """

    lab_arr = np.asarray(lab, dtype=np.float32)
    if lab_arr.shape[0] < k:
        return None

    rng = np.random.default_rng(42)
    if lab_arr.shape[0] > sample_limit:
        sample_idx = rng.choice(lab_arr.shape[0], size=sample_limit, replace=False)
    else:
        sample_idx = np.arange(lab_arr.shape[0])

    model = KMeans(n_clusters=k, n_init=25, max_iter=100, random_state=42)
    model.fit(lab_arr[sample_idx, :3])
    centers = model.cluster_centers_.astype(np.float32)

    distances = ((lab_arr[:, None, :3] - centers[None, :, :]) ** 2).sum(axis=2)
    cluster_id = np.argmin(distances, axis=1)

    chroma = np.sqrt(centers[:, 1] ** 2 + centers[:, 2] ** 2)
    black_id = int(np.argmin(centers[:, 0]))
    remaining = [idx for idx in range(k) if idx != black_id]

    blue_candidates = [idx for idx in remaining if centers[idx, 2] < 0]
    blue_ids: list[int] = []
    if blue_candidates:
        blue_ids = [min(blue_candidates, key=lambda idx: centers[idx, 2])]
    remaining = [idx for idx in remaining if idx not in blue_ids]

    gray_id = min(remaining, key=lambda idx: chroma[idx])
    brown_ids = [idx for idx in remaining if idx != gray_id]

    ratios = {
        "black": float(np.mean(cluster_id == black_id)),
        "brown": float(np.mean(np.isin(cluster_id, brown_ids))) if brown_ids else 0.0,
        "gray": float(np.mean(cluster_id == gray_id)),
        "blue": float(np.mean(np.isin(cluster_id, blue_ids))) if blue_ids else 0.0,
    }
    dmdi = round(
        0 * ratios["black"] + 1 * ratios["brown"] + 2 * ratios["gray"] + 3 * ratios["blue"],
        4,
    )
    return ClusterResult(
        centers=centers,
        cluster_id=cluster_id,
        label_clusters={
            "black": [black_id],
            "brown": brown_ids,
            "gray": [gray_id],
            "blue": blue_ids,
        },
        ratios=ratios,
        dmdi=float(dmdi),
    )


def make_heatmap_image(img: np.ndarray, roi: np.ndarray, hair: np.ndarray, dmdi: float) -> np.ndarray:
    """生成 DMDI 热图预览。

    当前 DMDI 是 ROI 级综合指数，热图用于突出有效分析区域和整体等级，不表示
    逐像素独立预测。
    """

    h, w = img.shape[:2]
    heat = np.full((h, w, 3), 0.72, dtype=np.float32)
    valid = np.asarray(roi).astype(bool) & (~np.asarray(hair).astype(bool))
    if dmdi < 0.75:
        color_rgb = np.array([0.12, 0.35, 0.95], dtype=np.float32)
    elif dmdi < 1.5:
        color_rgb = np.array([0.12, 0.72, 0.78], dtype=np.float32)
    elif dmdi < 2.25:
        color_rgb = np.array([0.95, 0.76, 0.18], dtype=np.float32)
    else:
        color_rgb = np.array([0.90, 0.18, 0.12], dtype=np.float32)

    heat[valid] = color_rgb
    heat[np.asarray(hair).astype(bool)] = 0.05
    return heat


def overlay_masks_from_rgba(overlay: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """从画布 RGBA 图层中识别黄色 ROI 边界和红色毛发标注。

    Streamlit 画布导出的边缘像素会受抗锯齿影响，不一定是纯黄色或纯红色。
    因此沿用 R 版后期修正后的“优势通道”规则，提高对浏览器差异的容错能力。
    """

    arr = np.asarray(overlay, dtype=np.float32)
    if arr.max(initial=0) > 1:
        arr = arr / 255.0
    if arr.ndim == 2:
        red = green = blue = arr
        alpha = arr
    else:
        red = arr[:, :, 0]
        green = arr[:, :, 1]
        blue = arr[:, :, 2]
        alpha = arr[:, :, 3] if arr.shape[2] >= 4 else np.maximum.reduce([red, green, blue])

    roi_boundary = (
        (red > 0.45)
        & (green > 0.35)
        & (red > blue + 0.15)
        & (green > blue + 0.12)
        & (alpha > 0.08)
    )
    hair_mask = (
        (red > 0.45)
        & (red > green + 0.18)
        & (red > blue + 0.18)
        & (alpha > 0.08)
    )
    return roi_boundary, hair_mask


def to_uint8_image(img: np.ndarray) -> Image.Image:
    """把 0-1 RGB 数组转换为 Pillow 图片，供界面和脚本保存预览。"""

    arr = np.clip(np.asarray(img), 0.0, 1.0)
    return Image.fromarray((arr * 255).astype(np.uint8), mode="RGB")


def _disc_structure(size: int) -> np.ndarray:
    """创建近似 EBImage 圆盘刷子的二值结构元素。"""

    radius = max(1, size // 2)
    yy, xx = np.ogrid[-radius : radius + 1, -radius : radius + 1]
    return (xx * xx + yy * yy) <= radius * radius


