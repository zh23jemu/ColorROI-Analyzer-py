"""ColorROI Analyzer Python 核心分析冒烟测试。

用法：
    .venv\\Scripts\\python.exe scripts\\smoke_test.py

该脚本不启动浏览器，只验证图片读取、ROI 填充、毛发修复、Lab 转换、四分类
和 DMDI 计算是否能在当前 Python 环境中正常执行。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from colorroi_analyzer.analysis import analyze_image
from colorroi_analyzer.core import load_rgb_image


def main() -> int:
    img = load_rgb_image(PROJECT_ROOT / "0.jpg")
    h, w = img.shape[:2]
    yy, xx = np.mgrid[:h, :w]

    # 构造一个位于图片中央的椭圆边界，模拟用户在画布上手动画出的黄色 ROI。
    outer = ((xx - w / 2) ** 2 / (w * 0.28) ** 2 + (yy - h / 2) ** 2 / (h * 0.28) ** 2) <= 1
    inner = ((xx - w / 2) ** 2 / (w * 0.25) ** 2 + (yy - h / 2) ** 2 / (h * 0.25) ** 2) <= 1
    roi_boundary = outer & ~inner

    # 构造一条细长毛发 mask，验证局部补色逻辑不会破坏整体分析流程。
    hair = (np.abs(xx - w / 2) < 3) & (yy > h * 0.35) & (yy < h * 0.65)
    result = analyze_image(img, roi_boundary, hair, repair_hair=True)

    ratios = result.clusters.ratios
    print(
        "核心分析冒烟测试通过："
        f"ROI={result.roi_px} px，毛发={result.hair_px} px，"
        f"黑={ratios['black'] * 100:.3f}%，棕={ratios['brown'] * 100:.3f}%，"
        f"灰={ratios['gray'] * 100:.3f}%，蓝={ratios['blue'] * 100:.3f}%，"
        f"DMDI={result.clusters.dmdi:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
