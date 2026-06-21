"""批量生成图片人工复核 CSV 模板。

该脚本会为每张图片构造一个居中的椭圆 ROI 做程序侧快速分析，输出比例、
DMDI 和人工复核字段。真实研究使用时仍建议人工在应用中圈选准确 ROI。
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from colorroi_analyzer.analysis import analyze_image
from colorroi_analyzer.core import load_rgb_image


def default_ellipse_boundary(height: int, width: int) -> np.ndarray:
    """生成居中椭圆边界，用作批量复核模板的粗略 ROI。"""

    yy, xx = np.mgrid[:height, :width]
    outer = ((xx - width / 2) ** 2 / (width * 0.30) ** 2 + (yy - height / 2) ** 2 / (height * 0.30) ** 2) <= 1
    inner = ((xx - width / 2) ** 2 / (width * 0.27) ** 2 + (yy - height / 2) ** 2 / (height * 0.27) ** 2) <= 1
    return outer & ~inner


def build_rows(image_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(image_dir.glob("*")):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}:
            continue
        base = {
            "file": path.name,
            "status": "ok",
            "black_percent": "",
            "brown_percent": "",
            "gray_percent": "",
            "blue_percent": "",
            "dmdi": "",
            "manual_main_color": "",
            "manual_secondary_color": "",
            "is_reasonable": "",
            "notes": "",
        }
        try:
            img = load_rgb_image(path)
            h, w = img.shape[:2]
            result = analyze_image(img, default_ellipse_boundary(h, w), np.zeros((h, w), dtype=bool))
            ratios = result.clusters.ratios
            base.update(
                {
                    "black_percent": round(ratios["black"] * 100, 4),
                    "brown_percent": round(ratios["brown"] * 100, 4),
                    "gray_percent": round(ratios["gray"] * 100, 4),
                    "blue_percent": round(ratios["blue"] * 100, 4),
                    "dmdi": result.clusters.dmdi,
                }
            )
        except Exception as exc:
            base["status"] = f"error: {exc}"
        rows.append(base)
    return rows


def main() -> int:
    image_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "pics"
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else PROJECT_ROOT / "test-artifacts" / "manual-review-template-python.csv"
    rows = build_rows(image_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["file", "status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"已生成复核表：{output}，共 {len(rows)} 条记录。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
