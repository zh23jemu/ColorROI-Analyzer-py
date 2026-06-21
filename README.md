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

- `src/colorroi_analyzer/`：Python 核心算法包，包含图片读取、ROI 边界填充、毛发区域修复、Lab 转换、四分类聚类和 DMDI 计算。
- `scripts/smoke_test.py`：核心分析冒烟测试，不启动浏览器即可验证计算链路。
- `scripts/inspect_images.py`：检查图片目录读取状态和尺寸。
- `scripts/create_review_sheet.py`：批量生成图片人工复核 CSV 模板。
- `tests/`：核心算法 pytest 测试。
- `pics/`：从原项目迁移的示例图片。
- `test-artifacts/`：原项目端到端测试截图和 CSV 样例，用于复核迁移结果。
- `docs/`：保留原项目迁移、Git 状态和交付说明，作为 Python 重建的参考资料。
- `0.jpg`、`1.jpg`、`新建 文本文档.txt`：原项目早期样例和原型资料。

## 环境准备

当前项目建议使用 Python 3.11。本机已用 `.venv` 验证通过：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev]
```

## 验证命令

```powershell
.venv\Scripts\python.exe scripts\smoke_test.py
.venv\Scripts\python.exe scripts\inspect_images.py
.venv\Scripts\python.exe -m pytest
```

如 Windows 终端中文输出显示乱码，可在终端启用 UTF-8 后重试；这不影响脚本实际计算结果。

Streamlit 应用入口会在后续提交中补齐。
