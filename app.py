"""ColorROI Analyzer Python 交互式应用入口。

该界面使用 Streamlit 复刻原 R Shiny 应用的核心工作流：上传图片、手动画出
黄色 ROI 边界、红色标注毛发或遮挡、可选局部修复后分析颜色比例和 DMDI，
并支持保存多条记录与导出 CSV。
"""

from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image
from PIL import ImageDraw


def _patch_streamlit_canvas_image_api() -> None:
    """为 streamlit-drawable-canvas 补齐新版 Streamlit 中移动过的图片 API。

    `streamlit-drawable-canvas==0.9.3` 仍会从 `streamlit.elements.image`
    调用旧签名的内部函数 `image_to_url(image, width, clamp, channels,
    output_format, image_id)`。Streamlit 1.58 已把该函数移动到
    `streamlit.elements.lib.image_utils`，并把第二个参数改为 `LayoutConfig`。
    这里在导入 `st_canvas` 之前提供一个兼容旧签名的包装器，只影响当前进程，
    不修改第三方包源码。
    """

    try:
        import streamlit.elements.image as legacy_image
        from streamlit.elements.lib.image_utils import image_to_url as modern_image_to_url
        from streamlit.elements.lib.layout_utils import LayoutConfig
    except Exception:
        return

    def legacy_image_to_url(image, width, clamp, channels, output_format, image_id):
        # 旧画布组件传入的是整数宽度；新版 Streamlit 需要带 width 属性的
        # LayoutConfig。其它参数保持原样透传，避免改变图片编码和缓存 ID。
        layout_config = width if isinstance(width, LayoutConfig) else LayoutConfig(width=width)
        return modern_image_to_url(image, layout_config, clamp, channels, output_format, image_id)

    legacy_image.image_to_url = legacy_image_to_url


_patch_streamlit_canvas_image_api()
from streamlit_drawable_canvas import st_canvas

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from colorroi_analyzer.analysis import analyze_image
from colorroi_analyzer.core import overlay_masks_from_rgba, to_uint8_image


MAX_DISPLAY_WIDTH = 860


def main() -> None:
    """渲染 Streamlit 应用。"""

    st.set_page_config(page_title="ColorROI Analyzer Python", layout="wide")
    _init_state()

    st.title("ColorROI Analyzer")

    with st.sidebar:
        uploaded = st.file_uploader("上传图片", type=["jpg", "jpeg", "png", "bmp", "tif", "tiff"])
        draw_mode = st.radio("绘制模式", ["ROI 边界（黄色）", "毛发标注（红色）", "橡皮擦"], index=0)
        brush_size = st.slider("画笔粗细", min_value=3, max_value=36, value=10, step=1)
        repair_hair = st.checkbox("分析前修复红色毛发区域", value=True)
        run_analysis = st.button("开始分析", type="primary", use_container_width=True)

        st.divider()
        st.subheader("样本信息")
        sample_name = st.text_input("姓名/样本名")
        sample_id = st.text_input("编号")
        gender = st.radio("性别", ["男", "女", "未知"], index=2, horizontal=True)
        hair_clinical = st.radio("临床是否可见毛发", ["有", "无", "未知"], index=2, horizontal=True)
        pattern = st.selectbox("结构模式", ["未填写", "Globular", "Homogeneous", "Reticular", "Multicomponent"])
        save_record = st.button("保存记录", use_container_width=True)

    if uploaded is None:
        st.info("请先上传一张图片。")
        _render_records()
        return

    img = _read_uploaded_image(uploaded)
    display_img, scale = _make_display_image(img)
    stroke_color, drawing_mode = _canvas_style(draw_mode)

    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 0)",
        stroke_width=brush_size,
        stroke_color=stroke_color,
        background_image=display_img,
        update_streamlit=True,
        height=display_img.height,
        width=display_img.width,
        drawing_mode=drawing_mode,
        key=f"canvas_{uploaded.name}_{display_img.width}_{display_img.height}",
    )

    roi_boundary, hair_mask = _extract_masks(
        image_data=canvas_result.image_data,
        json_data=canvas_result.json_data,
        target_shape=img.shape[:2],
        display_shape=(display_img.height, display_img.width),
        scale=scale,
    )
    if run_analysis:
        _run_analysis(img, roi_boundary, hair_mask, repair_hair)

    _render_previews(img, roi_boundary, hair_mask)
    _render_metrics()
    _render_lab_scatter()

    if save_record:
        _save_record(
            img_shape=img.shape,
            sample_name=sample_name,
            sample_id=sample_id,
            gender=gender,
            hair_clinical=hair_clinical,
            pattern=pattern,
        )

    _render_records()


def _init_state() -> None:
    """初始化跨 rerun 保存的状态。"""

    st.session_state.setdefault("analysis", None)
    st.session_state.setdefault("records", [])


def _read_uploaded_image(uploaded) -> np.ndarray:
    """读取上传图片并转换为 0-1 RGB 数组。"""

    image = Image.open(uploaded).convert("RGB")
    arr = np.asarray(image, dtype=np.float32) / 255.0
    return np.clip(arr, 0.0, 1.0)


def _make_display_image(img: np.ndarray) -> tuple[Image.Image, float]:
    """根据最大显示宽度生成画布背景图。"""

    h, w = img.shape[:2]
    scale = min(1.0, MAX_DISPLAY_WIDTH / w)
    display_w = int(round(w * scale))
    display_h = int(round(h * scale))
    pil_img = to_uint8_image(img)
    if scale < 1:
        pil_img = pil_img.resize((display_w, display_h), Image.Resampling.LANCZOS)
    return pil_img, scale


def _canvas_style(draw_mode: str) -> tuple[str, str]:
    """把中文绘制模式转换为 canvas 画笔颜色和模式。"""

    if draw_mode == "毛发标注（红色）":
        return "rgba(230,45,24,1)", "freedraw"
    if draw_mode == "橡皮擦":
        return "rgba(0,0,0,1)", "transform"
    return "rgba(255,220,0,1)", "freedraw"


def _extract_masks(
    image_data: np.ndarray | None,
    json_data: dict | None,
    target_shape: tuple[int, int],
    display_shape: tuple[int, int],
    scale: float,
) -> tuple[np.ndarray, np.ndarray]:
    """从 Streamlit 画布图层中提取 ROI 边界和毛发 mask。

    优先使用 `json_data` 中的 Fabric 手绘对象重建 mask。这样只读取用户真正
    画出的路径，不会把背景皮肤颜色、网格线或图片上的标尺误判为黄色/红色
    标注。只有当旧版组件没有返回 JSON 对象时，才回退到 RGBA 截图颜色识别。
    """

    h, w = target_shape
    roi_small, hair_small = _masks_from_canvas_json(json_data, display_shape)
    if roi_small.any() or hair_small.any():
        return _resize_canvas_masks(roi_small, hair_small, target_shape)

    if image_data is None:
        return np.zeros((h, w), dtype=bool), np.zeros((h, w), dtype=bool)

    roi_small, hair_small = overlay_masks_from_rgba(image_data)
    if scale == 1 and roi_small.shape == (h, w):
        return roi_small, hair_small

    return _resize_canvas_masks(roi_small, hair_small, target_shape)


def _resize_canvas_masks(
    roi_small: np.ndarray,
    hair_small: np.ndarray,
    target_shape: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """把画布显示尺寸的二值 mask 映射回原图尺寸。"""

    h, w = target_shape
    roi_img = Image.fromarray((roi_small.astype(np.uint8) * 255), mode="L").resize((w, h), Image.Resampling.NEAREST)
    hair_img = Image.fromarray((hair_small.astype(np.uint8) * 255), mode="L").resize((w, h), Image.Resampling.NEAREST)
    return np.asarray(roi_img) > 0, np.asarray(hair_img) > 0


def _masks_from_canvas_json(json_data: dict | None, display_shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """从 Fabric.js JSON 对象中重建黄色 ROI 和红色毛发 mask。

    `streamlit-drawable-canvas` 的 `image_data` 是背景图和标注合成后的截图；
    而 `json_data["objects"]` 只包含用户画出的对象。读取 JSON 路径能避免背景
    图片颜色干扰，是当前交互式标注最稳定的解析入口。
    """

    display_h, display_w = display_shape
    roi_img = Image.new("L", (display_w, display_h), 0)
    hair_img = Image.new("L", (display_w, display_h), 0)
    roi_draw = ImageDraw.Draw(roi_img)
    hair_draw = ImageDraw.Draw(hair_img)

    for obj in (json_data or {}).get("objects", []):
        points = _fabric_path_points(obj)
        if len(points) < 2:
            continue

        stroke_width = max(1, int(round(float(obj.get("strokeWidth") or 1))))
        stroke = str(obj.get("stroke") or "")
        if _is_roi_stroke(stroke):
            roi_draw.line(points, fill=255, width=stroke_width, joint="curve")
        elif _is_hair_stroke(stroke):
            hair_draw.line(points, fill=255, width=stroke_width, joint="curve")

    return np.asarray(roi_img) > 0, np.asarray(hair_img) > 0


def _fabric_path_points(obj: dict) -> list[tuple[float, float]]:
    """把 Fabric.js path 对象转换为可绘制点序列。

    自由画笔通常生成 `M`、`L`、`Q` 命令；这里同时兼容三次贝塞尔 `C`。
    曲线会被采样成短线段，便于 Pillow 直接绘制成二值 mask。
    """

    if obj.get("type") != "path":
        return []

    points: list[tuple[float, float]] = []
    current: tuple[float, float] | None = None
    for command in obj.get("path") or []:
        if not command:
            continue
        code = str(command[0]).upper()
        values = [float(v) for v in command[1:]]

        if code == "M" and len(values) >= 2:
            current = (values[0], values[1])
            points.append(current)
        elif code == "L" and len(values) >= 2:
            current = (values[0], values[1])
            points.append(current)
        elif code == "Q" and current is not None and len(values) >= 4:
            control = (values[0], values[1])
            end = (values[2], values[3])
            points.extend(_sample_quadratic(current, control, end))
            current = end
        elif code == "C" and current is not None and len(values) >= 6:
            control1 = (values[0], values[1])
            control2 = (values[2], values[3])
            end = (values[4], values[5])
            points.extend(_sample_cubic(current, control1, control2, end))
            current = end

    return points


def _sample_quadratic(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
    steps: int = 16,
) -> list[tuple[float, float]]:
    """采样二次贝塞尔曲线。"""

    out: list[tuple[float, float]] = []
    for idx in range(1, steps + 1):
        t = idx / steps
        x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t**2 * end[0]
        y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t**2 * end[1]
        out.append((x, y))
    return out


def _sample_cubic(
    start: tuple[float, float],
    control1: tuple[float, float],
    control2: tuple[float, float],
    end: tuple[float, float],
    steps: int = 20,
) -> list[tuple[float, float]]:
    """采样三次贝塞尔曲线。"""

    out: list[tuple[float, float]] = []
    for idx in range(1, steps + 1):
        t = idx / steps
        x = (
            (1 - t) ** 3 * start[0]
            + 3 * (1 - t) ** 2 * t * control1[0]
            + 3 * (1 - t) * t**2 * control2[0]
            + t**3 * end[0]
        )
        y = (
            (1 - t) ** 3 * start[1]
            + 3 * (1 - t) ** 2 * t * control1[1]
            + 3 * (1 - t) * t**2 * control2[1]
            + t**3 * end[1]
        )
        out.append((x, y))
    return out


def _is_roi_stroke(stroke: str) -> bool:
    """判断画笔颜色是否为黄色 ROI。"""

    rgb = _parse_rgb(stroke)
    if rgb is None:
        return False
    red, green, blue = rgb
    return red > 180 and green > 140 and blue < 90


def _is_hair_stroke(stroke: str) -> bool:
    """判断画笔颜色是否为红色毛发标注。"""

    rgb = _parse_rgb(stroke)
    if rgb is None:
        return False
    red, green, blue = rgb
    return red > 160 and green < 120 and blue < 120


def _parse_rgb(stroke: str) -> tuple[int, int, int] | None:
    """解析 Fabric.js 常见的 `rgba(...)` 或 `#rrggbb` 颜色字符串。"""

    color_text = stroke.strip().lower()
    if color_text.startswith("#") and len(color_text) >= 7:
        try:
            return (
                int(color_text[1:3], 16),
                int(color_text[3:5], 16),
                int(color_text[5:7], 16),
            )
        except ValueError:
            return None

    if color_text.startswith("rgb"):
        start = color_text.find("(")
        end = color_text.find(")", start + 1)
        if start >= 0 and end > start:
            parts = color_text[start + 1 : end].split(",")[:3]
            try:
                return tuple(int(float(part.strip())) for part in parts)  # type: ignore[return-value]
            except ValueError:
                return None
    return None


def _run_analysis(img: np.ndarray, roi_boundary: np.ndarray, hair_mask: np.ndarray, repair_hair: bool) -> None:
    """执行一次 ROI 分析，并把结果写入 session_state。"""

    try:
        st.session_state.analysis = analyze_image(img, roi_boundary, hair_mask, repair_hair=repair_hair)
        st.success("分析完成。")
    except Exception as exc:
        st.session_state.analysis = None
        st.warning(str(exc))


def _render_previews(img: np.ndarray, roi_boundary: np.ndarray, hair_mask: np.ndarray) -> None:
    """渲染原图、ROI、修复图和热图预览。"""

    analysis = st.session_state.analysis
    cols = st.columns(4)
    cols[0].image(to_uint8_image(img), caption="原始图", use_container_width=True)
    cols[1].image(_make_overlay_preview(img, roi_boundary, hair_mask), caption="ROI / 毛发标注", use_container_width=True)
    if analysis is not None:
        cols[2].image(to_uint8_image(analysis.clean_image), caption="毛发修复后", use_container_width=True)
        cols[3].image(to_uint8_image(analysis.heatmap), caption="DMDI 热图", use_container_width=True)
    else:
        cols[2].empty()
        cols[3].empty()


def _make_overlay_preview(img: np.ndarray, roi_boundary: np.ndarray, hair_mask: np.ndarray) -> Image.Image:
    """生成带黄色 ROI 和红色毛发标注的预览图。"""

    preview = np.asarray(img).copy()
    boundary = np.asarray(roi_boundary).astype(bool)
    hair = np.asarray(hair_mask).astype(bool)
    preview[boundary] = np.array([1.0, 0.86, 0.0], dtype=np.float32)
    preview[hair] = np.array([0.90, 0.18, 0.12], dtype=np.float32)
    return to_uint8_image(preview)


def _render_metrics() -> None:
    """渲染 ROI 面积、颜色比例和 DMDI。"""

    analysis = st.session_state.analysis
    if analysis is None:
        st.caption("当前尚未生成分析结果。")
        return

    ratios = analysis.clusters.ratios
    metric_cols = st.columns(6)
    metric_cols[0].metric("ROI 面积", f"{analysis.roi_px} px")
    metric_cols[1].metric("毛发标注", f"{analysis.hair_px} px")
    metric_cols[2].metric("有效区", f"{analysis.effective_px} px")
    metric_cols[3].metric("黑", f"{ratios['black'] * 100:.2f}%")
    metric_cols[4].metric("棕", f"{ratios['brown'] * 100:.2f}%")
    metric_cols[5].metric("灰 / 蓝灰 / DMDI", f"{ratios['gray'] * 100:.2f}% / {ratios['blue'] * 100:.2f}% / {analysis.clusters.dmdi:.4f}")


def _render_lab_scatter() -> None:
    """渲染 Lab 空间散点图。"""

    analysis = st.session_state.analysis
    if analysis is None:
        return

    lab = analysis.lab
    if lab.shape[0] > 5000:
        rng = np.random.default_rng(42)
        lab = lab[rng.choice(lab.shape[0], size=5000, replace=False)]
    df = pd.DataFrame(lab, columns=["L", "a", "b"])
    fig = px.scatter(df, x="a", y="L", color="b", opacity=0.35, labels={"a": "a*", "L": "L*", "b": "b*"})
    fig.update_layout(height=320, margin=dict(l=40, r=20, t=20, b=40))
    st.plotly_chart(fig, use_container_width=True)


def _save_record(
    img_shape: tuple[int, ...],
    sample_name: str,
    sample_id: str,
    gender: str,
    hair_clinical: str,
    pattern: str,
) -> None:
    """保存当前分析记录到 session_state。"""

    analysis = st.session_state.analysis
    if analysis is None:
        st.warning("请先完成分析再保存记录。")
        return
    if not sample_name.strip() or not sample_id.strip():
        st.warning("保存前请填写姓名/样本名和编号。")
        return

    ratios = analysis.clusters.ratios
    h, w = img_shape[:2]
    st.session_state.records.append(
        {
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sample_name": sample_name.strip(),
            "sample_id": sample_id.strip(),
            "gender": gender,
            "hair_clinical": hair_clinical,
            "pattern": pattern,
            "roi_px": analysis.roi_px,
            "roi_percent": round(analysis.roi_px / (h * w) * 100, 4),
            "hair_px": analysis.hair_px,
            "effective_px": analysis.effective_px,
            "black_percent": round(ratios["black"] * 100, 4),
            "brown_percent": round(ratios["brown"] * 100, 4),
            "gray_percent": round(ratios["gray"] * 100, 4),
            "blue_percent": round(ratios["blue"] * 100, 4),
            "dmdi": analysis.clusters.dmdi,
        }
    )
    st.success("记录已保存。")


def _render_records() -> None:
    """渲染已保存记录和 CSV 下载按钮。"""

    st.subheader("已保存记录")
    records = st.session_state.records
    if not records:
        st.caption("暂无保存记录。")
        return

    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_bytes = _dataframe_to_csv_bytes(df)
    st.download_button(
        "导出 CSV",
        data=csv_bytes,
        file_name=f"colorroi_records_{datetime.now():%Y-%m-%d}.csv",
        mime="text/csv",
    )


def _dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """以 UTF-8 BOM 导出 CSV，方便 Windows Excel 直接识别中文列值。"""

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


if __name__ == "__main__":
    main()
