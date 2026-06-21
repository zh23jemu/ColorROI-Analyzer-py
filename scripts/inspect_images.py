"""检查图片目录中的文件尺寸和读取状态。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from colorroi_analyzer.core import load_rgb_image


def inspect_images(image_dir: Path) -> list[dict[str, object]]:
    """返回目录中常见图片文件的读取状态。"""

    rows: list[dict[str, object]] = []
    for path in sorted(image_dir.glob("*")):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}:
            continue
        try:
            img = load_rgb_image(path)
            h, w = img.shape[:2]
            rows.append({"file": path.name, "status": "ok", "width": w, "height": h})
        except Exception as exc:
            rows.append({"file": path.name, "status": f"error: {exc}", "width": "", "height": ""})
    return rows


def main() -> int:
    image_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "pics"
    rows = inspect_images(image_dir)
    if not rows:
        print(f"未找到可检查的图片：{image_dir}")
        return 1
    for row in rows:
        print(f"{row['file']}\t{row['status']}\t{row['width']}x{row['height']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
