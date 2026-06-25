"""ColorROI Analyzer Python 交互式应用入口。

该界面使用 Streamlit 复刻原 R Shiny 应用的核心工作流：上传图片、手动画出
黄色 ROI 边界、红色标注毛发或遮挡、可选局部修复后分析颜色比例和 DMDI，
并支持保存多条记录与导出 CSV。
"""

from __future__ import annotations

import io
import importlib
import sys
import base64
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from PIL import ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
CANVAS_COMPONENT_DIR = PROJECT_ROOT / "components" / "colorroi_canvas"
colorroi_canvas_component = components.declare_component("colorroi_canvas", path=str(CANVAS_COMPONENT_DIR))

import colorroi_analyzer.core as colorroi_core
import colorroi_analyzer.analysis as colorroi_analysis


MAX_DISPLAY_WIDTH = 860
DRAW_MODE_OPTIONS = {
    "ROI boundary (yellow)": "roi",
    "Hair / obstruction (red)": "hair",
    "Eraser": "eraser",
}
GENDER_OPTIONS = ["Male", "Female", "Unknown"]
HAIR_CLINICAL_OPTIONS = ["Present", "Absent", "Unknown"]
PATTERN_OPTIONS = ["Not specified", "Globular", "Homogeneous", "Reticular", "Multicomponent"]


def main() -> None:
    """渲染 Streamlit 应用。"""

    st.set_page_config(page_title="ColorROI Analyzer Python", layout="wide")
    _init_state()

    st.title("ColorROI Analyzer")

    with st.sidebar:
        uploaded = st.file_uploader("Upload image", type=["jpg", "jpeg", "png", "bmp", "tif", "tiff"])
        draw_mode = st.radio("Drawing mode", list(DRAW_MODE_OPTIONS), index=0)
        brush_size = st.slider("Brush size", min_value=3, max_value=36, value=10, step=1)
        clear_marks = st.button("Clear all annotations", use_container_width=True)
        use_auto_lesion = st.checkbox("Auto-detect lesion candidate when ROI is not drawn", value=True)
        repair_hair = st.checkbox("Inpaint red hair / obstruction marks before analysis", value=True)
        run_analysis = st.button("Analyze", type="primary", use_container_width=True)

        st.divider()
        st.subheader("Sample Information")
        sample_name = st.text_input("Name / sample")
        sample_id = st.text_input("ID")
        gender = st.radio("Sex", GENDER_OPTIONS, index=2, horizontal=True)
        hair_clinical = st.radio("Clinically visible hair", HAIR_CLINICAL_OPTIONS, index=2, horizontal=True)
        pattern = st.selectbox("Pattern", PATTERN_OPTIONS)
        save_record = st.button("Save record", use_container_width=True)

    if uploaded is None:
        st.info("Please upload an image first.")
        _render_records()
        return

    _reset_analysis_when_upload_changes(uploaded)
    img = _read_uploaded_image(uploaded)
    display_img, scale = _make_display_image(img)
    canvas_signature = _canvas_signature(uploaded, display_img)
    _ensure_canvas_mark_state(canvas_signature, (display_img.height, display_img.width))
    if clear_marks:
        _reset_canvas_marks(canvas_signature, (display_img.height, display_img.width))
    canvas_key = _canvas_key(uploaded, display_img)
    _merge_component_value_into_state(_pending_component_value(canvas_key), (display_img.height, display_img.width))
    display_roi, display_hair = _current_display_masks()
    canvas_value = _render_annotation_canvas(
        display_img=display_img,
        roi_mask=display_roi,
        hair_mask=display_hair,
        draw_mode=draw_mode,
        brush_size=brush_size,
        key=canvas_key,
    )
    _merge_component_value_into_state(canvas_value, (display_img.height, display_img.width))

    roi_boundary, hair_mask = _current_masks_for_analysis(img.shape[:2])
    roi_boundary, roi_source = _prepare_roi_boundary(img, roi_boundary, use_auto_lesion)
    if run_analysis:
        hair_mask, hair_source = _prepare_hair_mask_for_analysis(img, roi_boundary, hair_mask)
        _run_analysis(img, roi_boundary, hair_mask, repair_hair, hair_source, roi_source)

    _render_previews(img, roi_boundary, hair_mask, roi_source)
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
    st.session_state.setdefault("uploaded_signature", None)
    st.session_state.setdefault("roi_source", "unknown")
    st.session_state.setdefault("canvas_signature", None)
    st.session_state.setdefault("canvas_version", 0)
    st.session_state.setdefault("canvas_roi_display", None)
    st.session_state.setdefault("canvas_hair_display", None)


def _reset_analysis_when_upload_changes(uploaded) -> None:
    """上传文件变化时清理旧分析结果，避免旧 session 对象继续渲染。"""

    signature = (uploaded.name, uploaded.size)
    if st.session_state.uploaded_signature != signature:
        st.session_state.uploaded_signature = signature
        st.session_state.analysis = None
        st.session_state.roi_source = "unknown"
        st.session_state.canvas_signature = None
        st.session_state.canvas_version = 0
        st.session_state.canvas_roi_display = None
        st.session_state.canvas_hair_display = None


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
    pil_img = colorroi_core.to_uint8_image(img)
    if scale < 1:
        pil_img = pil_img.resize((display_w, display_h), Image.Resampling.LANCZOS)
    return pil_img, scale


def _canvas_signature(uploaded, display_img: Image.Image) -> tuple[str, int, int, int]:
    """生成当前上传图片和显示尺寸对应的画布状态签名。

    画布标记是按显示尺寸保存的；当用户换图或显示尺寸变化时，旧标记不能继续复用，
    否则会出现上一张图的 ROI 残留到新图上的问题。
    """

    return (uploaded.name, int(uploaded.size), int(display_img.width), int(display_img.height))


def _ensure_canvas_mark_state(signature: tuple[str, int, int, int], display_shape: tuple[int, int]) -> None:
    """确保 session 中存在当前图片的累计标记层。"""

    needs_reset = (
        st.session_state.canvas_signature != signature
        or st.session_state.canvas_roi_display is None
        or st.session_state.canvas_hair_display is None
    )
    if needs_reset:
        _reset_canvas_marks(signature, display_shape)


def _reset_canvas_marks(signature: tuple[str, int, int, int], display_shape: tuple[int, int]) -> None:
    """清空当前图片的累计 ROI/毛发标记层。"""

    display_h, display_w = display_shape
    st.session_state.canvas_signature = signature
    st.session_state.canvas_roi_display = np.zeros((display_h, display_w), dtype=bool)
    st.session_state.canvas_hair_display = np.zeros((display_h, display_w), dtype=bool)
    st.session_state.canvas_version = int(st.session_state.canvas_version) + 1


def _canvas_key(uploaded, display_img: Image.Image) -> str:
    """生成当前画布组件 key。

    key 中包含 `canvas_version`，用于在清空标记或切换图片时重建前端组件，避免
    浏览器继续沿用上一张图片的隐藏 mask。普通绘制不会改变 key，保证前端画布
    能持续处理笔画和橡皮擦，减少 Streamlit rerun 带来的视觉中断。
    """

    return f"canvas_{uploaded.name}_{display_img.width}_{display_img.height}_{st.session_state.canvas_version}"


def _pending_canvas_json(canvas_key: str) -> dict | None:
    """读取上一次画布组件回传、但尚未合并的 JSON。

    Streamlit 组件触发 rerun 时，组件值通常已经进入 `session_state`。先读取它，
    再渲染画布，可以在同一次 rerun 内完成“合并标记层 -> 清空临时对象 ->
    显示更新后的顶部大图”，避免额外调用 `st.rerun()` 造成明显二次刷新。
    """

    value = st.session_state.get(canvas_key)
    if value is None:
        return None
    if isinstance(value, dict):
        json_data = value.get("json_data")
        return json_data if isinstance(json_data, dict) else None
    json_data = getattr(value, "json_data", None)
    return json_data if isinstance(json_data, dict) else None


def _pending_component_value(canvas_key: str) -> dict | None:
    """读取自定义画布上一次回传、但本轮渲染前尚未合并的 mask。

    Streamlit 自定义组件会把前端返回值存到 `st.session_state[canvas_key]`。
    如果先渲染组件再合并该值，前端会短暂收到旧 mask，表现为第二次擦除时第一
    次擦掉的标记又被旧状态画回来。这里在渲染前先合并上一次回传值，保证组件
    每一轮拿到的都是最新累计 mask。
    """

    value = st.session_state.get(canvas_key)
    if not isinstance(value, dict):
        return None
    if "roiMaskDataUrl" not in value or "hairMaskDataUrl" not in value:
        return None
    return value


def _current_display_masks() -> tuple[np.ndarray, np.ndarray]:
    """读取当前显示尺寸下的累计标记层。"""

    return (
        np.asarray(st.session_state.canvas_roi_display).astype(bool),
        np.asarray(st.session_state.canvas_hair_display).astype(bool),
    )


def _current_masks_for_analysis(target_shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """把累计标记层从显示尺寸映射回原图尺寸，供分析流程使用。"""

    roi_display, hair_display = _current_display_masks()
    return _resize_canvas_masks(roi_display, hair_display, target_shape)


def _render_annotation_canvas(
    display_img: Image.Image,
    roi_mask: np.ndarray,
    hair_mask: np.ndarray,
    draw_mode: str,
    brush_size: int,
    key: str,
) -> dict | None:
    """渲染本地自定义标注画布，并返回前端回传的二值 mask。

    这个组件用浏览器里的多层 canvas 取代 `streamlit-drawable-canvas`：
    - 底层只显示原图，不参与擦除。
    - 可见标记层显示黄色 ROI 和红色毛发。
    - 两个隐藏 mask 层分别保存 ROI 与毛发二值结果。

    橡皮擦在前端使用 canvas 的 `destination-out` 合成模式，只擦除标记层和隐藏
    mask 层，不会覆盖或修改原图像素，因此拖动橡皮擦时能立即看到黄色/红色标记
    被擦掉。
    """

    return colorroi_canvas_component(
        imageDataUrl=_image_to_data_url(display_img),
        roiMaskDataUrl=_mask_to_data_url(roi_mask),
        hairMaskDataUrl=_mask_to_data_url(hair_mask),
        width=int(display_img.width),
        height=int(display_img.height),
        mode=_canvas_component_mode(draw_mode),
        brushSize=int(brush_size),
        key=key,
        default=None,
    )


def _merge_component_value_into_state(value: dict | None, display_shape: tuple[int, int]) -> None:
    """把自定义前端画布回传的 mask 合并到 Streamlit session。

    前端每次完成一笔都会回传完整 ROI/毛发 mask。Python 端只保存二值层，后续
    分析、自动 ROI 优先级判断和导出都继续沿用原来的 mask 流程。
    """

    if not isinstance(value, dict):
        return
    roi_mask = _mask_from_data_url(value.get("roiMaskDataUrl"), display_shape)
    hair_mask = _mask_from_data_url(value.get("hairMaskDataUrl"), display_shape)
    if roi_mask is None or hair_mask is None:
        return

    current_roi, current_hair = _current_display_masks()
    if np.array_equal(current_roi, roi_mask) and np.array_equal(current_hair, hair_mask):
        return

    st.session_state.canvas_roi_display = roi_mask
    st.session_state.canvas_hair_display = hair_mask
    st.session_state.analysis = None


def _canvas_component_mode(draw_mode: str) -> str:
    """把界面中文模式转换为前端组件使用的短模式名。"""

    return DRAW_MODE_OPTIONS.get(draw_mode, "roi")


def _image_to_data_url(image: Image.Image) -> str:
    """把显示图编码成前端组件可直接加载的 PNG data URL。"""

    return _pil_to_png_data_url(image.convert("RGB"))


def _pil_to_png_data_url(image: Image.Image) -> str:
    """把 PIL 图片原样编码为 PNG data URL。

    普通背景图使用 RGB 即可；mask 图必须保留 RGBA 的 alpha 通道，所以这里单独
    提供不强制转 RGB 的底层编码函数。
    """

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _mask_to_data_url(mask: np.ndarray) -> str:
    """把布尔 mask 编码为透明背景、白色前景的 PNG data URL。"""

    mask_arr = np.asarray(mask).astype(bool)
    rgba = np.zeros((*mask_arr.shape, 4), dtype=np.uint8)
    rgba[mask_arr] = np.array([255, 255, 255, 255], dtype=np.uint8)
    return _pil_to_png_data_url(Image.fromarray(rgba, mode="RGBA"))


def _mask_from_data_url(data_url: str | None, expected_shape: tuple[int, int]) -> np.ndarray | None:
    """从前端回传的 PNG data URL 读取二值 mask。

    前端隐藏 mask 层只使用 alpha 通道表示是否被标记；读取时也只看 alpha，避免
    受到浏览器抗锯齿产生的 RGB 差异影响。
    """

    if not isinstance(data_url, str) or ";base64," not in data_url:
        return None
    try:
        encoded = data_url.split(";base64,", 1)[1]
        image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGBA")
    except Exception:
        return None

    expected_h, expected_w = expected_shape
    if image.size != (expected_w, expected_h):
        image = image.resize((expected_w, expected_h), Image.Resampling.NEAREST)
    alpha = np.asarray(image, dtype=np.uint8)[..., 3]
    return alpha > 0


def _make_canvas_background(display_img: Image.Image, roi_mask: np.ndarray, hair_mask: np.ndarray) -> Image.Image:
    """把当前累计标记合成到顶部画布背景图。

    由于 `streamlit-drawable-canvas` 没有真正的局部橡皮擦，应用会把每次笔画先
    合并进 session 中的二值标记层，再把合成后的标记预览作为下一轮画布背景。
    这样用户擦除后，顶部大图也会立刻显示擦除后的黄色/红色标记，而原图像素不变。
    """

    base = np.asarray(display_img, dtype=np.uint8).copy()
    roi = np.asarray(roi_mask).astype(bool)
    hair = np.asarray(hair_mask).astype(bool)
    if roi.shape == base.shape[:2]:
        base[roi] = np.array([255, 220, 0], dtype=np.uint8)
    if hair.shape == base.shape[:2]:
        base[hair] = np.array([230, 45, 24], dtype=np.uint8)
    return Image.fromarray(base, mode="RGB")


def _canvas_has_objects(json_data: dict | None) -> bool:
    """判断当前画布是否有尚未合并进累计层的新对象。"""

    return bool((json_data or {}).get("objects"))


def _merge_canvas_json_into_state(json_data: dict | None, display_shape: tuple[int, int]) -> None:
    """把本轮画布新路径合并到累计标记层，并推进画布版本。

    画布本身只作为“本次笔画采集器”。合并完成后通过递增 key 清空临时对象，
    下一轮画布背景会显示已经合成好的标记结果，因此橡皮擦的视觉效果会同步到
    顶部大图。
    """

    roi_display, hair_display = _current_display_masks()
    roi_display, hair_display = _apply_canvas_json_to_masks(json_data, display_shape, roi_display, hair_display)
    st.session_state.canvas_roi_display = roi_display
    st.session_state.canvas_hair_display = hair_display
    st.session_state.analysis = None
    st.session_state.canvas_version = int(st.session_state.canvas_version) + 1


def _canvas_style(draw_mode: str) -> tuple[str, str]:
    """把中文绘制模式转换为 canvas 画笔颜色和模式。"""

    if draw_mode == "毛发标注（红色）":
        return "rgba(230,45,24,1)", "freedraw"
    if draw_mode == "橡皮擦":
        # 使用透明白色作为“局部橡皮擦”笔刷：Fabric.js 仍会记录这条 path，
        # 后端解析 JSON 时可据此擦除黄色/红色标记；但画布上不会出现白色痕迹，
        # 避免用户误以为原始图片内容被擦掉。
        return "rgba(255,255,255,0)", "freedraw"
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

    roi_small, hair_small = colorroi_core.overlay_masks_from_rgba(image_data)
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
    roi = np.zeros((display_h, display_w), dtype=bool)
    hair = np.zeros((display_h, display_w), dtype=bool)
    return _apply_canvas_json_to_masks(json_data, display_shape, roi, hair)


def _apply_canvas_json_to_masks(
    json_data: dict | None,
    display_shape: tuple[int, int],
    roi_mask: np.ndarray,
    hair_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """按 Fabric.js 对象顺序把画笔路径应用到给定 ROI/毛发 mask。

    该函数同时服务两种场景：
    - 测试和旧逻辑：从空白 mask 重建整张画布的标记。
    - 当前交互：把本轮新画的路径叠加到 session 中的累计标记层。

    橡皮擦必须按对象顺序处理，因为用户可能先画黄色 ROI，再擦掉局部，随后又
    补画一段黄色边界；顺序错了会让最终显示和用户操作不一致。
    """

    display_h, display_w = display_shape
    roi_arr = np.asarray(roi_mask).astype(bool)
    hair_arr = np.asarray(hair_mask).astype(bool)
    if roi_arr.shape != (display_h, display_w):
        roi_arr = np.zeros((display_h, display_w), dtype=bool)
    if hair_arr.shape != (display_h, display_w):
        hair_arr = np.zeros((display_h, display_w), dtype=bool)

    roi_img = Image.fromarray((roi_arr.astype(np.uint8) * 255), mode="L")
    hair_img = Image.fromarray((hair_arr.astype(np.uint8) * 255), mode="L")
    roi_draw = ImageDraw.Draw(roi_img)
    hair_draw = ImageDraw.Draw(hair_img)

    for obj in (json_data or {}).get("objects", []):
        points = _fabric_path_points(obj)
        if len(points) < 2:
            continue

        stroke_width = max(1, int(round(float(obj.get("strokeWidth") or 1))))
        stroke = str(obj.get("stroke") or "")
        if _is_eraser_stroke(stroke):
            # `streamlit-drawable-canvas` 没有真正的局部橡皮擦模式；这里把白色
            # 自由笔画解释为擦除路径，并按用户绘制顺序同时从 ROI 和毛发 mask 中
            # 扣掉对应区域。这样用户不需要整对象删除，也能修正局部误画。
            roi_draw.line(points, fill=0, width=stroke_width, joint="curve")
            hair_draw.line(points, fill=0, width=stroke_width, joint="curve")
        elif _is_roi_stroke(stroke):
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


def _is_eraser_stroke(stroke: str) -> bool:
    """判断画笔颜色是否为局部橡皮擦。

    画布组件无法直接输出“擦除”语义，所以界面把橡皮擦做成白色自由笔画。
    解析 JSON 时将接近白色的路径视为擦除操作，而不是新的 ROI 或毛发标注。
    """

    rgb = _parse_rgb(stroke)
    if rgb is None:
        return False
    red, green, blue = rgb
    return red > 230 and green > 230 and blue > 230


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


def _run_analysis(
    img: np.ndarray,
    roi_boundary: np.ndarray,
    hair_mask: np.ndarray,
    repair_hair: bool,
    hair_source: str | None = None,
    roi_source: str | None = None,
) -> None:
    """执行一次 ROI 分析，并把结果写入 session_state。"""

    try:
        st.session_state.analysis = _analyze_image(img, roi_boundary, hair_mask, repair_hair, hair_source)
        st.session_state.roi_source = roi_source or "unknown"
        st.success("Analysis complete.")
    except Exception as exc:
        st.session_state.analysis = None
        st.warning(str(exc))


def _analyze_image(
    img: np.ndarray,
    roi_boundary: np.ndarray,
    hair_mask: np.ndarray,
    repair_hair: bool,
    hair_source: str | None,
):
    """动态调用分析函数，兼容 Streamlit 热更新保留的旧函数签名。"""

    analyzer = getattr(colorroi_analysis, "analyze_image")
    try:
        return analyzer(
            img,
            roi_boundary,
            hair_mask,
            repair_hair=repair_hair,
            hair_source_hint=hair_source,
        )
    except TypeError as exc:
        if "hair_source_hint" not in str(exc):
            raise

    reloaded_analysis = importlib.reload(colorroi_analysis)
    analyzer = getattr(reloaded_analysis, "analyze_image")
    try:
        return analyzer(
            img,
            roi_boundary,
            hair_mask,
            repair_hair=repair_hair,
            hair_source_hint=hair_source,
        )
    except TypeError as exc:
        if "hair_source_hint" not in str(exc):
            raise
        # 极端情况下，如果运行进程仍拿到旧签名，就退回旧调用，并在返回对象上
        # 动态补充来源字段，保证 UI 能继续展示本轮分析结果。
        result = analyzer(img, roi_boundary, hair_mask, repair_hair=repair_hair)
        try:
            object.__setattr__(result, "hair_source", hair_source or "unknown")
        except Exception:
            pass
        return result


def _prepare_roi_boundary(img: np.ndarray, roi_boundary: np.ndarray, use_auto_lesion: bool) -> tuple[np.ndarray, str]:
    """准备最终 ROI 边界，并标记来源。

    用户手动画出的黄色 ROI 永远优先；只有在没有手动 ROI 且用户启用自动识别时，
    才使用传统图像分割生成的皮损候选。这样自动识别提供的是“初始候选”，用户
    仍可通过手动画黄色边界覆盖它，避免自动结果不准时影响正式分析。
    """

    manual_roi = np.asarray(roi_boundary).astype(bool)
    if manual_roi.any():
        return manual_roi, "manual"
    if not use_auto_lesion:
        return manual_roi, "unknown"

    lesion = _auto_lesion_mask(img)
    if not lesion.any():
        return manual_roi, "unknown"
    return _mask_to_boundary(lesion), "auto"


def _auto_lesion_mask(img: np.ndarray) -> np.ndarray:
    """动态获取自动皮损候选函数，兼容 Streamlit 热更新模块缓存。"""

    detector = getattr(colorroi_core, "auto_lesion_mask", None)
    if detector is None:
        reloaded_core = importlib.reload(colorroi_core)
        detector = getattr(reloaded_core, "auto_lesion_mask")
    return detector(img)


def _mask_to_boundary(mask: np.ndarray) -> np.ndarray:
    """动态获取 mask 转边界函数，兼容旧 Streamlit 进程缓存。"""

    converter = getattr(colorroi_core, "mask_to_boundary", None)
    if converter is None:
        reloaded_core = importlib.reload(colorroi_core)
        converter = getattr(reloaded_core, "mask_to_boundary")
    return converter(mask)


def _prepare_hair_mask_for_analysis(
    img: np.ndarray,
    roi_boundary: np.ndarray,
    hair_mask: np.ndarray,
) -> tuple[np.ndarray, str | None]:
    """按 TXT 需求在界面层准备最终毛发 mask。

    如果用户已经用红色画笔标注毛发，则优先使用手动 mask；如果没有红色标注，
    这里直接执行自动毛发检测，并把结果限制在填充后的 ROI 内。这样 Streamlit
    界面无需等待后端 dataclass 字段热更新，也能立即显示自动检测出的毛发区域。
    """

    manual_hair = np.asarray(hair_mask).astype(bool)
    if manual_hair.any():
        return manual_hair, "manual"

    roi = colorroi_core.fill_roi_from_boundary(roi_boundary)
    if roi.shape != img.shape[:2] or not roi.any():
        return manual_hair, None
    return _auto_hair_mask(img) & roi, "auto"


def _auto_hair_mask(img: np.ndarray) -> np.ndarray:
    """动态获取自动毛发检测函数，兼容 Streamlit 热更新模块缓存。

    旧 Streamlit 进程有时会缓存修改前的 `colorroi_analyzer.core` 模块，导致顶层
    `from ... import auto_hair_mask` 在页面刷新时直接失败。这里把函数获取延迟到
    点击分析时；如果当前模块对象没有该函数，就 reload 一次本地 core 模块再取。
    """

    detector = getattr(colorroi_core, "auto_hair_mask", None)
    if detector is None:
        reloaded_core = importlib.reload(colorroi_core)
        detector = getattr(reloaded_core, "auto_hair_mask")
    return detector(img)


def _render_previews(img: np.ndarray, roi_boundary: np.ndarray, hair_mask: np.ndarray, roi_source: str) -> None:
    """渲染原图、ROI、修复图和热图预览。"""

    analysis = st.session_state.analysis
    display_hair = analysis.hair if analysis is not None else hair_mask
    roi_caption = f"ROI / hair annotation (ROI: {_roi_source_label(roi_source)})"
    cols = st.columns(4)
    _image(cols[0], colorroi_core.to_uint8_image(img), caption="Original image")
    _image(cols[1], _make_overlay_preview(img, roi_boundary, display_hair), caption=roi_caption)
    if analysis is not None:
        _image(cols[2], colorroi_core.to_uint8_image(analysis.clean_image), caption="After hair inpainting")
        _image(cols[3], colorroi_core.to_uint8_image(analysis.heatmap), caption="DMDI heatmap")
    else:
        cols[2].empty()
        cols[3].empty()


def _image(container, image, *, caption: str) -> None:
    """兼容不同 Streamlit 版本的图片渲染参数。

    Streamlit 1.40 以后推荐使用 `use_container_width`，但云端当前依赖约束会安装
    1.39.x，该版本的 `st.image()` 还没有这个参数。这里优先按新版参数调用；
    如果旧版抛出 `TypeError`，再退回旧参数 `use_column_width`，避免上传图片后预览
    区域因为 API 差异直接报错。
    """

    try:
        container.image(image, caption=caption, use_container_width=True)
    except TypeError as exc:
        if "use_container_width" not in str(exc):
            raise
        container.image(image, caption=caption, use_column_width=True)


def _make_overlay_preview(img: np.ndarray, roi_boundary: np.ndarray, hair_mask: np.ndarray) -> Image.Image:
    """生成带黄色 ROI 和红色毛发标注的预览图。"""

    preview = np.asarray(img).copy()
    boundary = np.asarray(roi_boundary).astype(bool)
    hair = np.asarray(hair_mask).astype(bool)
    preview[boundary] = np.array([1.0, 0.86, 0.0], dtype=np.float32)
    preview[hair] = np.array([0.90, 0.18, 0.12], dtype=np.float32)
    return colorroi_core.to_uint8_image(preview)


def _render_metrics() -> None:
    """渲染 ROI 面积、颜色比例和 DMDI。"""

    analysis = st.session_state.analysis
    if analysis is None:
        st.caption("No analysis result yet.")
        return

    ratios = analysis.clusters.ratios
    effective_px = _effective_px(analysis)
    hair_source = _hair_source_label(analysis)
    # Streamlit 的 metric 卡片在右侧结果栏中宽度较窄；把基础像素指标和颜色指标拆成两行，
    # 避免“灰/蓝灰/DMDI”挤在同一格里被浏览器截断成省略号。
    pixel_cols = st.columns(3)
    pixel_cols[0].metric(f"ROI area ({_roi_source_label(st.session_state.roi_source)})", f"{analysis.roi_px} px")
    pixel_cols[1].metric(f"Hair marks ({hair_source})", f"{analysis.hair_px} px")
    pixel_cols[2].metric("Effective area", f"{effective_px} px")

    color_cols = st.columns(5)
    color_cols[0].metric("Black", f"{ratios['black'] * 100:.2f}%")
    color_cols[1].metric("Brown", f"{ratios['brown'] * 100:.2f}%")
    color_cols[2].metric("Gray", f"{ratios['gray'] * 100:.2f}%")
    color_cols[3].metric("Blue-gray", f"{ratios['blue'] * 100:.2f}%")
    color_cols[4].metric("DMDI", f"{analysis.clusters.dmdi:.4f}")


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
        st.warning("Please run the analysis before saving a record.")
        return
    if not sample_name.strip() or not sample_id.strip():
        st.warning("Please enter the name / sample and ID before saving.")
        return

    ratios = analysis.clusters.ratios
    h, w = img_shape[:2]
    effective_px = _effective_px(analysis)
    st.session_state.records.append(
        {
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sample_name": sample_name.strip(),
            "sample_id": sample_id.strip(),
            "gender": gender,
            "hair_clinical": hair_clinical,
            "pattern": pattern,
            "roi_source": _roi_source_label(st.session_state.roi_source),
            "roi_px": analysis.roi_px,
            "roi_percent": round(analysis.roi_px / (h * w) * 100, 4),
            "hair_px": analysis.hair_px,
            "hair_source": _hair_source_label(analysis),
            "effective_px": effective_px,
            "black_percent": round(ratios["black"] * 100, 4),
            "brown_percent": round(ratios["brown"] * 100, 4),
            "gray_percent": round(ratios["gray"] * 100, 4),
            "blue_percent": round(ratios["blue"] * 100, 4),
            "dmdi": analysis.clusters.dmdi,
        }
    )
    st.success("Record saved.")


def _effective_px(analysis) -> int:
    """返回有效分析像素数，并兼容热更新前的旧 AnalysisResult 对象。

    Streamlit 运行中修改依赖模块后，当前进程可能暂时保留旧版 dataclass 实例。
    如果旧对象还没有 `effective_px` 字段，就按需求里的定义 `ROI - 毛发` 做
    兜底计算，避免界面渲染因为热更新状态不一致而报错。
    """

    if hasattr(analysis, "effective_px"):
        return int(analysis.effective_px)
    return max(0, int(getattr(analysis, "roi_px", 0)) - int(getattr(analysis, "hair_px", 0)))


def _hair_source_label(analysis) -> str:
    """返回毛发 mask 来源，用于区分 TXT 需求中的手动标注和自动检测。"""

    source = str(getattr(analysis, "hair_source", "") or "")
    if source == "auto":
        return "Auto"
    if source == "manual":
        return "Manual"
    return "Unknown"


def _roi_source_label(source: str | None) -> str:
    """返回 ROI 来源标签，用于区分手动画和自动皮损候选。"""

    source_text = str(source or "")
    if source_text == "auto":
        return "Auto candidate"
    if source_text == "manual":
        return "Manual"
    return "Unknown"


def _render_records() -> None:
    """渲染已保存记录和 CSV 下载按钮。"""

    st.subheader("Saved Records")
    records = st.session_state.records
    if not records:
        st.caption("No saved records yet.")
        return

    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_bytes = _dataframe_to_csv_bytes(df)
    st.download_button(
        "Export CSV",
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
