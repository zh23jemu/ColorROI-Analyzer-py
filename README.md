# ColorROI Analyzer Python

ColorROI Analyzer Python 是从原 R Shiny 项目重建的交互式 ROI 颜色分析工具。目标流程保持一致：上传图片、手动画出黄色 ROI 边界、用红色标注毛发等干扰区域、可选修复毛发区域，再在 ROI 内基于 CIELAB 色彩空间输出黑、棕、灰、蓝比例和 DMDI 指标。

当前版本不再提供自动皮损/ROI 候选识别，正式分析只使用用户手动画出的黄色 ROI 边界。若未手动画 ROI，系统会提示有效分析区不足；毛发/遮挡仍可用红色手动标注，若没有手动标注则会在 ROI 内自动检测毛发候选。

## 技术栈

- Python 3.11+
- Streamlit：交互式 Web 应用
- NumPy / SciPy / scikit-image / scikit-learn：图像处理、Lab 转换和聚类
- Pillow：图片读取与导出
- Pandas：记录表和 CSV 导出
- Plotly：Lab 散点图

## 当前内容

- `app.py`：Streamlit 交互式应用入口，支持上传图片、画 ROI/毛发、分析、保存记录和导出 CSV。
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

当前项目建议使用 Python 3.11。本机已用 `.venv` 验证通过。应用使用本地 Streamlit 自定义画布组件完成 ROI、毛发和橡皮擦标注，不再依赖第三方 drawable canvas 包或额外前端构建步骤。

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

## 启动应用

```powershell
.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

启动后访问：

```text
http://127.0.0.1:8501
```

## 使用说明

1. 上传 JPG、PNG、BMP 或 TIFF 图片。
2. 在画布上使用黄色画笔手动画出皮损/ROI 边界，手动画结果会优先生效。
3. 可选：切换到红色画笔标注毛发或遮挡区域；如果不标红色，系统会在 ROI 内自动检测毛发候选。
4. 点击“开始分析”，查看颜色比例、DMDI、修复图、热图和 Lab 散点图。
5. 填写样本信息后点击“保存记录”。
6. 在记录表下方导出 CSV。
