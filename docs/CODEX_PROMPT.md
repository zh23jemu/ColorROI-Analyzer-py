# 迁移后继续让 Codex 开发的提示词

把项目迁移到新电脑并在 Codex 中打开 `ColorROI-Analyzer` 后，可以直接把下面这段发给 Codex。

```text
你现在继续维护 ColorROI-Analyzer 项目。请先读取 README.md、AGENTS.md 和 docs/MIGRATION.md，理解项目当前状态，不要覆盖已有文件。

项目背景：
- 这是一个 R Shiny 工具，用于皮肤/色素区域图片的手动 ROI 分析。
- 用户上传图片后，用黄色手动画 ROI，用红色标注毛发。
- 程序先修复红色毛发区域，再在 ROI 内基于 CIELAB 空间做黑、棕、灰、蓝四类聚类。
- 输出颜色比例、DMDI、热图、Lab 散点图和 CSV 记录。

当前状态：
- R 4.6.0 环境验证通过。
- 依赖包括 shiny、shinythemes、EBImage、jpeg、png、plotly、base64enc、DT。
- scripts/check_dependencies.R、scripts/smoke_test.R、scripts/inspect_images.R 已可用。
- 已有 Playwright + 系统 Chrome 的端到端测试产物，上传、手绘 ROI、毛发标注、分析、保存记录和 CSV 导出均已跑通。
- 蓝色标签规则已做初步修正：只有 `b* < 0` 的非黑聚类才命名为蓝。后续重点用更多样本校准灰、棕、蓝边界。

请继续做下一步：
1. 先运行或指导运行 source("scripts/check_dependencies.R") 和 source("scripts/smoke_test.R")。
2. 对 pics/ 中多张图片做复核辅助：生成一个人工复核表模板或批量记录方案。
3. 运行 `scripts/diagnose_color_labels.R`，用多张图片复核 Lab 聚类中心和灰、棕、蓝标签边界。
4. 如果要改代码，保持最小修改，新增中文注释，并同步更新 AGENTS.md。
5. 每完成一组有意义修改，请执行 git commit，提交信息使用中文 Conventional Commits，包含标题和正文。

注意：
- 不要删除用户图片和测试产物。
- 不要重构无关代码。
- 不要把 R 本地缓存、临时调试截图或系统文件加入版本管理。
```

## 可选开发方向

后续可以让 Codex 继续做这些任务：

```text
请帮我给 pics/ 里的图片设计一个人工复核表，字段包括图片名、肉眼主色、程序黑/棕/灰/蓝比例、DMDI、是否合理、问题说明，并生成 CSV 模板。
```

```text
请运行 scripts/diagnose_color_labels.R 复核当前 Lab 四分类标签规则，重点分析灰、棕、蓝边界是否仍需要结合人工真值继续校准。先不要改代码，先解释方案。
```

```text
请给项目增加批量分析记录导入/导出能力，但仍然保留手动 ROI，不要做自动边界识别。
```

```text
请用一张 pics/ 示例图做完整浏览器端到端测试，并检查 CSV 下载文件内容。
```

