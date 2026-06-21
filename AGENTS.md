# ColorROI-Analyzer-py 项目记忆

## 项目目标

将 `C:\Coding\ColorROI-Analyzer\` 中的 R Shiny 版 ColorROI Analyzer 完整迁移为当前目录下的 Python 项目。核心功能保持一致：上传图片、手动画黄色 ROI 边界、红色标注毛发/遮挡、可选局部修复、Lab 四分类、DMDI 计算、结果预览、记录保存和 CSV 导出。

## 技术栈

- Python 3.11+。
- Streamlit 用于交互式 Web 应用。
- NumPy、SciPy、scikit-image、scikit-learn、Pillow、Pandas 和 Plotly 用于图像分析、聚类、可视化和导出。

## 当前架构

当前已建立 `src/colorroi_analyzer/` 核心算法包，并将 R 版的图片读取、ROI 边界填充、毛发局部修复、RGB 到 Lab、KMeans 四分类、DMDI 计算和热图生成迁移到 Python。`app.py` 是 Streamlit 交互界面入口，支持上传图片、画 ROI/毛发、分析、预览、保存记录和 CSV 导出。`scripts/` 中已提供冒烟测试、图片目录检查和人工复核表生成脚本，`tests/` 中已提供核心算法 pytest 测试。

## 开发规范

- 保持最小修改，优先修复和复刻核心行为。
- 新增 Python 代码默认写较详细中文注释，说明用途、关键逻辑和边界情况。
- 编辑文件前先读取相关文件。
- 不直接删除文件。
- 有意义变更后同步更新本文件。

## TODO

- 对比 R 版端到端样例结果，继续校准 Python 版默认 ROI 和颜色标签输出。
- 进行浏览器端人工手绘流程复核，确认 Streamlit 画布标注提取与预览结果一致。

## Current Status

已完成 Python 核心计算层迁移和 Streamlit 应用入口实现，创建本地 `.venv` 并安装项目依赖。`scripts/smoke_test.py` 已跑通，8 张 `pics/` 示例图片均可读取，pytest 核心测试通过。已启动 `.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501`，并确认 `http://127.0.0.1:8501` 返回 200。上传图片时报错 `AttributeError: module 'streamlit.elements.image' has no attribute 'image_to_url'` 以及后续 `AttributeError: 'int' object has no attribute 'width'` 的问题已通过 Streamlit 兼容 shim 修复：shim 会提供 `streamlit-drawable-canvas` 旧签名所需的 `image_to_url(image, width, ...)` 包装器，并把整数宽度转换为新版 Streamlit 需要的 `LayoutConfig`。依赖约束也已收紧为 `streamlit>=1.35,<1.40`，避免新环境自动安装到不兼容版本。

## Recent Changes

- 从原 R 项目复制 `pics/`、`test-artifacts/`、`docs/`、`0.jpg`、`1.jpg` 和早期原型文本。
- 创建 Python 项目初始 `README.md`。
- 创建贴合当前 Python/Streamlit 项目的 `.gitignore`。
- 新增 `pyproject.toml` 和 `requirements.txt`，声明 Python 3.11+ 依赖和开发测试依赖。
- 新增 `src/colorroi_analyzer/core.py` 和 `analysis.py`，迁移 ROI 填充、毛发修复、Lab 四分类、DMDI 和热图生成逻辑。
- 新增 `scripts/smoke_test.py`、`scripts/inspect_images.py` 和 `scripts/create_review_sheet.py`。
- 新增 `tests/test_core.py`，覆盖 ROI 填充和样例图核心分析冒烟流程。
- 使用 `.venv\Scripts\python.exe scripts\smoke_test.py`、`.venv\Scripts\python.exe scripts\inspect_images.py` 和 `.venv\Scripts\python.exe -m pytest` 完成验证。
- 新增 `app.py`，实现 Streamlit 上传、手绘标注、分析、预览、记录保存和 CSV 导出界面。
- 更新 `README.md`，补充应用启动命令和使用说明。
- 启动 Streamlit 本地服务并通过 HTTP 访问验证页面可达。
- 修复上传图片后 `streamlit-drawable-canvas` 与新版 Streamlit 内部 API 不兼容导致的 `image_to_url` 报错。
- 在 `pyproject.toml` 和 `requirements.txt` 中收紧 Streamlit 版本范围，并在 `app.py` 导入画布组件前补齐兼容 API。
- 将 Streamlit 兼容 shim 从简单函数转挂改为旧签名包装器，修复新版 `image_to_url` 把旧版整数 `width` 参数误当作 `LayoutConfig` 导致的 `.width` 报错。

## Next TODO

- 在浏览器中执行一次完整人工流程：上传真实样例、手绘 ROI、红色标注毛发、分析、保存记录和导出 CSV。
- 根据人工流程结果修正 Streamlit 画布擦除/清空交互。

## Open Issues

- 当前 Windows 终端可能以非 UTF-8 编码显示中文脚本输出，计算结果不受影响。
- Python 版核心算法已通过冒烟测试，但尚未完成与 R 版同一手绘 ROI 的逐项端到端对照。
- Streamlit 画布的擦除/清空交互与原 Shiny 自定义 canvas 不完全一致，仍需浏览器端手工复核。
- 当前 `.venv` 因已有 Streamlit 服务占用二进制文件，未完成依赖降级；但应用内兼容 shim 已验证可在 Streamlit 1.58 中补齐缺失 API。若重建全新 `.venv`，依赖约束会安装兼容范围内的 Streamlit。

## Architecture Decisions

- Python 重建采用核心算法包和 Streamlit UI 分离的结构，便于非交互式测试和后续界面维护。
- 原项目资源和测试产物保留为迁移对照资料，不作为 Python 运行入口。
