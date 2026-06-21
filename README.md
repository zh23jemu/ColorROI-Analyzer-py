# ColorROI Analyzer Python

ColorROI Analyzer Python 是从原 R Shiny 项目重建的交互式 ROI 颜色分析工具。目标流程保持一致：上传图片、手动画出黄色 ROI 边界、用红色标注毛发等干扰区域、可选修复毛发区域，再在 ROI 内基于 CIELAB 色彩空间输出黑、棕、灰、蓝比例和 DMDI 指标。

## 技术栈

- Python 3.11+
- Streamlit：交互式 Web 应用
- NumPy / SciPy / scikit-image / scikit-learn：图像处理、Lab 转换和聚类
- Pillow：图片读取与导出
- Pandas：记录表和 CSV 导出
- Plotly：Lab 散点图

## 当前内容

- `pics/`：从原项目迁移的示例图片。
- `test-artifacts/`：原项目端到端测试截图和 CSV 样例，用于复核迁移结果。
- `docs/`：保留原项目迁移、Git 状态和交付说明，作为 Python 重建的参考资料。
- `0.jpg`、`1.jpg`、`新建 文本文档.txt`：原项目早期样例和原型资料。

Python 应用入口、核心算法和测试会在后续提交中补齐。
