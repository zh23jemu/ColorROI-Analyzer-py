# ColorROI-Analyzer-py 项目记忆

## 项目目标

将 `C:\Coding\ColorROI-Analyzer\` 中的 R Shiny 版 ColorROI Analyzer 完整迁移为当前目录下的 Python 项目。核心功能保持一致：上传图片、手动画黄色 ROI 边界、红色标注毛发/遮挡、可选局部修复、Lab 四分类、DMDI 计算、结果预览、记录保存和 CSV 导出。

## 技术栈

- Python 3.11+。
- Streamlit 用于交互式 Web 应用。
- NumPy、SciPy、scikit-image、scikit-learn、Pillow、Pandas 和 Plotly 用于图像分析、聚类、可视化和导出。

## 当前架构

当前为 Python 重建初始阶段，已迁移必要样例图片、测试产物和文档参考资料。后续计划建立 `src/colorroi_analyzer/` 核心算法包、Streamlit 应用入口和测试脚本。

## 开发规范

- 保持最小修改，优先修复和复刻核心行为。
- 新增 Python 代码默认写较详细中文注释，说明用途、关键逻辑和边界情况。
- 编辑文件前先读取相关文件。
- 不直接删除文件。
- 有意义变更后同步更新本文件。

## TODO

- 建立 Python 包结构和依赖文件。
- 迁移 R 版核心算法到 Python。
- 建立 Streamlit 交互界面。
- 增加冒烟测试、图片检查和复核表生成脚本。
- 运行本地验证并修正文档。

## Current Status

已初始化 Python 重建目录，复制原项目的样例图片、测试产物和参考文档，并创建 Python 项目的 README、.gitignore 和项目记忆文件。

## Recent Changes

- 从原 R 项目复制 `pics/`、`test-artifacts/`、`docs/`、`0.jpg`、`1.jpg` 和早期原型文本。
- 创建 Python 项目初始 `README.md`。
- 创建贴合当前 Python/Streamlit 项目的 `.gitignore`。

## Next TODO

- 添加 Python 依赖声明、核心算法模块和基础测试。
- 将 R 版 ROI 填充、毛发修复、Lab 四分类和 DMDI 计算迁移到 Python。

## Open Issues

- 尚未实现 Python 应用入口。
- 尚未验证 Python 依赖和核心算法输出与 R 版一致性。

## Architecture Decisions

- Python 重建采用核心算法包和 Streamlit UI 分离的结构，便于非交互式测试和后续界面维护。
- 原项目资源和测试产物保留为迁移对照资料，不作为 Python 运行入口。
