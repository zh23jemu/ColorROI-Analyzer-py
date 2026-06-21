"""面向应用层的一次性分析封装。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .core import (
    ClusterResult,
    auto_hair_mask,
    cluster_lab_colors,
    fill_roi_from_boundary,
    inpaint_masked_pixels,
    make_heatmap_image,
    rgb_to_lab,
)


@dataclass(frozen=True)
class AnalysisResult:
    """一次 ROI 分析的完整结果。"""

    roi: np.ndarray
    hair: np.ndarray
    clean_image: np.ndarray
    heatmap: np.ndarray
    lab: np.ndarray
    clusters: ClusterResult
    roi_px: int
    hair_px: int
    effective_px: int
    roi_percent: float
    hair_source: str


def analyze_image(
    img: np.ndarray,
    roi_boundary: np.ndarray,
    hair_mask: np.ndarray | None = None,
    repair_hair: bool = True,
    hair_source_hint: str | None = None,
) -> AnalysisResult:
    """根据原图、ROI 边界和毛发标注完成一次 DMDI 分析。

    参数:
        img: 0-1 RGB 图片数组。
        roi_boundary: 黄色手绘边界 mask，函数内部会填充为实心 ROI。
        hair_mask: 红色毛发或遮挡 mask；为空或没有任何像素时自动检测毛发。
        repair_hair: 是否在分析前对红色 mask 做局部修复。
        hair_source_hint: 调用方已提前准备毛发 mask 时，可传入 `manual` 或 `auto`
            标记来源，便于界面按 TXT 需求显示毛发来自手动标注还是自动检测。

    返回:
        AnalysisResult，包含 ROI、修复后图片、Lab 像素、四分类比例和 DMDI。
    """

    image = np.asarray(img, dtype=np.float32)
    h, w = image.shape[:2]
    roi = fill_roi_from_boundary(roi_boundary)
    if roi.shape != (h, w):
        raise ValueError("ROI mask 尺寸必须与图片尺寸一致。")
    if int(roi.sum()) < 50:
        raise ValueError("ROI 内有效像素过少，请先画出闭合的黄色 ROI 边界。")

    hair = np.zeros((h, w), dtype=bool) if hair_mask is None else np.asarray(hair_mask).astype(bool)
    if hair.shape != (h, w):
        raise ValueError("毛发 mask 尺寸必须与图片尺寸一致。")
    hair_source = hair_source_hint or "manual"
    if not hair.any():
        hair = auto_hair_mask(image) & roi
        hair_source = "auto"

    clean = inpaint_masked_pixels(image, hair, roi) if repair_hair else image.copy()
    effective_mask = roi & (~hair)
    roi_pixels = clean[effective_mask]
    if roi_pixels.shape[0] < 50:
        raise ValueError("ROI 内有效像素过少，无法稳定分析。")

    lab = rgb_to_lab(roi_pixels)
    clusters = cluster_lab_colors(lab, k=4)
    if clusters is None:
        raise ValueError("ROI 内像素不足，无法完成四分类。")

    heatmap = make_heatmap_image(image, roi, hair, clusters.dmdi)
    roi_px = int(roi.sum())
    return AnalysisResult(
        roi=roi,
        hair=hair,
        clean_image=clean,
        heatmap=heatmap,
        lab=lab,
        clusters=clusters,
        roi_px=roi_px,
        hair_px=int(hair.sum()),
        effective_px=int(effective_mask.sum()),
        roi_percent=round(roi_px / (h * w) * 100, 4),
        hair_source=hair_source,
    )
