"""批量复核 pics 样张的自动皮损候选和自动毛发标注结果。

这个脚本用于开发阶段快速检查自动皮损候选和自动毛发检测质量：它会遍历
`pics/` 中的样张，为每张图生成自动 ROI 候选，调用当前核心分析逻辑，并输出：

- `reports/pics_hair_review/index.html`：依赖 `previews/` 目录的本地复核报告；
- `reports/pics_hair_review/index_standalone.html`：图片已内嵌的单文件报告，适合直接发给用户；
- `reports/pics_hair_review/results.csv`：每张图的 ROI、毛发像素和颜色指标；
- `reports/pics_hair_review/previews/`：每张图的原图缩略图、毛发叠加图和热图。

注意：这里的 ROI 是传统图像分割生成的自动候选，只用于观察自动识别效果；
正式结果仍可在 Streamlit 页面中用手动画出的黄色 ROI 覆盖自动候选。
"""

from __future__ import annotations

import base64
import csv
import html
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from colorroi_analyzer.analysis import analyze_image
from colorroi_analyzer.core import auto_lesion_mask, load_rgb_image, mask_to_boundary, to_uint8_image


ROOT = Path(__file__).resolve().parents[1]
PICS_DIR = ROOT / "pics"
REPORT_DIR = ROOT / "reports" / "pics_hair_review"
PREVIEW_DIR = REPORT_DIR / "previews"
MAX_PREVIEW_WIDTH = 900


@dataclass(frozen=True)
class ReviewRow:
    """保存单张样张的批量分析结果，便于同时写 CSV 和 HTML。"""

    file_name: str
    original_preview: str
    overlay_preview: str
    heatmap_preview: str
    width: int
    height: int
    roi_px: int
    hair_px: int
    effective_px: int
    hair_percent_in_roi: float
    black_percent: float
    brown_percent: float
    gray_percent: float
    blue_gray_percent: float
    dmdi: float


def main() -> None:
    """批量处理 `pics/` 并生成复核报告。"""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(
        [
            path
            for path in PICS_DIR.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
        ]
    )
    if not image_paths:
        raise SystemExit(f"没有在 {PICS_DIR} 找到可分析图片。")

    rows = [_analyze_one(path) for path in image_paths]
    _write_csv(rows)
    _write_html(rows, REPORT_DIR / "index.html", inline_assets=False)
    _write_html(rows, REPORT_DIR / "index_standalone.html", inline_assets=True)

    print(f"已生成 {len(rows)} 张样张的毛发标注复核报告：{REPORT_DIR / 'index.html'}")


def _analyze_one(path: Path) -> ReviewRow:
    """分析单张图片并保存对应预览图。

    批量复核没有人工黄色 ROI，因此这里使用自动皮损候选作为 ROI。报告用于让
    用户确认候选范围是否合理；正式页面里仍然允许手动画黄色 ROI 覆盖自动候选。
    """

    img = load_rgb_image(path)
    height, width = img.shape[:2]
    lesion = auto_lesion_mask(img)
    if lesion.any():
        roi_boundary = mask_to_boundary(lesion)
    else:
        roi_boundary = _make_inset_rectangle_boundary(height, width)

    # hair_mask 传 None 时，核心分析函数会按 TXT 需求自动执行 black-hat + Otsu 毛发检测。
    result = analyze_image(
        img,
        roi_boundary,
        hair_mask=None,
        repair_hair=True,
        hair_source_hint="auto",
    )

    stem = _safe_stem(path)
    original_name = f"{stem}_original.jpg"
    overlay_name = f"{stem}_hair_overlay.jpg"
    heatmap_name = f"{stem}_heatmap.jpg"

    _save_preview(to_uint8_image(img), PREVIEW_DIR / original_name)
    _save_preview(_make_hair_overlay(img, result.roi, result.hair), PREVIEW_DIR / overlay_name)
    _save_preview(to_uint8_image(result.heatmap), PREVIEW_DIR / heatmap_name)

    ratios = result.clusters.ratios
    hair_percent = result.hair_px / result.roi_px * 100 if result.roi_px else 0.0
    return ReviewRow(
        file_name=path.name,
        original_preview=f"previews/{original_name}",
        overlay_preview=f"previews/{overlay_name}",
        heatmap_preview=f"previews/{heatmap_name}",
        width=width,
        height=height,
        roi_px=result.roi_px,
        hair_px=result.hair_px,
        effective_px=result.effective_px,
        hair_percent_in_roi=round(hair_percent, 4),
        black_percent=round(ratios["black"] * 100, 4),
        brown_percent=round(ratios["brown"] * 100, 4),
        gray_percent=round(ratios["gray"] * 100, 4),
        blue_gray_percent=round(ratios["blue"] * 100, 4),
        dmdi=round(result.clusters.dmdi, 6),
    )


def _make_inset_rectangle_boundary(height: int, width: int) -> np.ndarray:
    """生成整图内边缘矩形 ROI 边界 mask。

    `fill_roi_from_boundary()` 需要闭合边界而不是实心区域。这里手动构造 2 像素宽
    的闭合矩形，后续由 `analyze_image()` 复用正式应用里的 ROI 填充逻辑。
    """

    inset = max(2, int(min(height, width) * 0.03))
    top = inset
    left = inset
    bottom = max(top + 2, height - inset - 1)
    right = max(left + 2, width - inset - 1)

    boundary = np.zeros((height, width), dtype=bool)
    boundary[top : top + 2, left : right + 1] = True
    boundary[bottom - 1 : bottom + 1, left : right + 1] = True
    boundary[top : bottom + 1, left : left + 2] = True
    boundary[top : bottom + 1, right - 1 : right + 1] = True
    return boundary


def _make_hair_overlay(img: np.ndarray, roi: np.ndarray, hair: np.ndarray) -> Image.Image:
    """生成自动毛发标注叠加图：ROI 用淡黄蒙版，毛发用红色高亮。"""

    base = np.clip(np.asarray(img, dtype=np.float32), 0.0, 1.0).copy()
    roi_mask = np.asarray(roi).astype(bool)
    hair_mask = np.asarray(hair).astype(bool)

    # 先给 ROI 区域加一层很轻的黄色，帮助用户确认本次批量复核的分析范围。
    base[roi_mask] = base[roi_mask] * 0.82 + np.array([1.0, 0.86, 0.18], dtype=np.float32) * 0.18
    # 再把自动检测到的毛发位置用红色突出显示，颜色权重较高，便于肉眼检查漏检/误检。
    base[hair_mask] = base[hair_mask] * 0.30 + np.array([1.0, 0.05, 0.02], dtype=np.float32) * 0.70
    return to_uint8_image(base)


def _save_preview(image: Image.Image, path: Path) -> None:
    """按固定最大宽度保存预览图，控制报告体积并保持可读性。"""

    preview = image.convert("RGB")
    if preview.width > MAX_PREVIEW_WIDTH:
        ratio = MAX_PREVIEW_WIDTH / preview.width
        preview = preview.resize((MAX_PREVIEW_WIDTH, int(preview.height * ratio)), Image.Resampling.LANCZOS)
    preview.save(path, quality=88, optimize=True)


def _write_csv(rows: list[ReviewRow]) -> None:
    """把批量分析指标写入 CSV，方便后续用表格软件查看或对比。"""

    csv_path = REPORT_DIR / "results.csv"
    fieldnames = list(ReviewRow.__dataclass_fields__.keys())
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def _write_html(rows: list[ReviewRow], output_path: Path, inline_assets: bool) -> None:
    """生成 HTML 复核报告。

    参数:
        rows: 批量分析后的样张结果。
        output_path: 报告输出路径。
        inline_assets: 为 True 时把预览图转换成 base64 data URL，生成可以单独发送的
            HTML 文件；为 False 时保留相对路径，方便本地浏览和调试。
    """

    cards = "\n".join(_render_card(row, inline_assets) for row in rows)
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>pics 样张自动皮损和毛发识别复核</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7f9;
      color: #1f2933;
    }}
    header {{
      padding: 24px 28px 12px;
      background: #ffffff;
      border-bottom: 1px solid #dde3ea;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .note {{
      margin: 0;
      max-width: 980px;
      color: #52606d;
      line-height: 1.6;
      font-size: 14px;
    }}
    main {{
      padding: 20px 28px 32px;
    }}
    .card {{
      margin: 0 0 22px;
      background: #ffffff;
      border: 1px solid #dde3ea;
      border-radius: 8px;
      overflow: hidden;
    }}
    .card h2 {{
      margin: 0;
      padding: 14px 16px 8px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
      padding: 0 16px 14px;
    }}
    .metric {{
      border: 1px solid #e4e9ef;
      border-radius: 6px;
      padding: 8px 10px;
      background: #fbfcfd;
    }}
    .label {{
      display: block;
      color: #697586;
      font-size: 12px;
      line-height: 1.4;
    }}
    .value {{
      display: block;
      margin-top: 2px;
      font-weight: 650;
      font-size: 15px;
      line-height: 1.35;
      word-break: break-word;
    }}
    .images {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1px;
      background: #dde3ea;
    }}
    figure {{
      margin: 0;
      background: #ffffff;
    }}
    figcaption {{
      padding: 8px 10px;
      color: #52606d;
      font-size: 13px;
      border-bottom: 1px solid #edf1f5;
    }}
    img {{
      display: block;
      width: 100%;
      height: auto;
    }}
    @media (max-width: 900px) {{
      .images {{
        grid-template-columns: 1fr;
      }}
      header, main {{
        padding-left: 14px;
        padding-right: 14px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>pics 样张自动皮损和毛发识别复核</h1>
    <p class="note">淡黄色区域为当前算法自动生成的皮损/ROI 候选，红色区域为 ROI 内自动识别的毛发/遮挡候选。正式分析时，用户可以直接采用自动 ROI，也可以在页面中手动画黄色边界覆盖自动候选；系统会在最终 ROI 内排除毛发后计算颜色指标。</p>
  </header>
  <main>
{cards}
  </main>
</body>
</html>
"""
    output_path.write_text(html_text, encoding="utf-8")


def _render_card(row: ReviewRow, inline_assets: bool) -> str:
    """渲染单张图片在 HTML 报告中的卡片。"""

    title = html.escape(row.file_name)
    return f"""    <section class="card">
      <h2>{title}</h2>
      <div class="metrics">
        {_metric("尺寸", f"{row.width} x {row.height}")}
        {_metric("ROI 面积", f"{row.roi_px} px")}
        {_metric("毛发标注", f"{row.hair_px} px")}
        {_metric("毛发占 ROI", f"{row.hair_percent_in_roi:.4f}%")}
        {_metric("有效区", f"{row.effective_px} px")}
        {_metric("黑", f"{row.black_percent:.4f}%")}
        {_metric("棕", f"{row.brown_percent:.4f}%")}
        {_metric("灰", f"{row.gray_percent:.4f}%")}
        {_metric("蓝灰", f"{row.blue_gray_percent:.4f}%")}
        {_metric("DMDI", f"{row.dmdi:.6f}")}
      </div>
      <div class="images">
        {_figure(row.original_preview, "原图", inline_assets)}
        {_figure(row.overlay_preview, "自动皮损候选（淡黄）/ 毛发遮挡（红色）", inline_assets)}
        {_figure(row.heatmap_preview, "DMDI 热图", inline_assets)}
      </div>
    </section>"""


def _metric(label: str, value: str) -> str:
    """渲染一个指标块。"""

    return f'<div class="metric"><span class="label">{html.escape(label)}</span><span class="value">{html.escape(value)}</span></div>'


def _figure(src: str, caption: str, inline_assets: bool) -> str:
    """渲染一张报告图片。"""

    image_src = _inline_image_src(src) if inline_assets else src
    return f'<figure><figcaption>{html.escape(caption)}</figcaption><img src="{html.escape(image_src)}" alt="{html.escape(caption)}"></figure>'


def _inline_image_src(src: str) -> str:
    """把报告中的相对图片路径转换成 JPEG data URL。

    这样生成的 `index_standalone.html` 不再依赖 `previews/` 目录，适合通过微信、
    邮件或网盘单文件发送给用户确认。
    """

    image_path = REPORT_DIR / src
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _safe_stem(path: Path) -> str:
    """生成适合做报告资源文件名的图片前缀。"""

    safe_chars = []
    for char in path.stem:
        if char.isalnum() or char in {"-", "_"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    return "".join(safe_chars)


if __name__ == "__main__":
    main()
