# 迁移包内容说明

推荐迁移包文件名：

```text
ColorROI-Analyzer-migration.zip
```

## 包内目录

- `app.R`：主程序。
- `README.md`：项目使用说明。
- `AGENTS.md`：项目记忆和继续开发上下文。
- `.gitignore`：忽略规则。
- `docs/`：迁移说明、Codex 提示词和打包说明。
- `docs/GIT_STATE.md`：Git 状态快照和恢复说明。
- `scripts/`：检查、测试和辅助脚本。
- `pics/`：示例图片。
- `test-artifacts/`：已通过测试的截图和 CSV 样例。
- `0.jpg`、`1.jpg`：早期样例图。
- `新建 文本文档.txt`：早期原型代码。
- `ColorROI-Analyzer.git.bundle`：完整 Git 历史包。

## 包内不包含

- `.git/` 目录本身不包含，但包含可恢复历史的 `ColorROI-Analyzer.git.bundle`。
- `.Rhistory`
- `.RData`
- `.Ruserdata`
- `rsconnect/`
- Shiny 临时缓存
- 端到端测试失败时的调试截图

## 新电脑恢复顺序

1. 解压迁移包。
2. 安装 R。
3. 安装 README 或 `docs/MIGRATION.md` 中列出的依赖。
4. 运行 `source("scripts/check_dependencies.R")`。
5. 运行 `source("scripts/smoke_test.R")`。
6. 运行 `shiny::runApp("app.R")`。
7. 将 `docs/CODEX_PROMPT.md` 中的提示词发给 Codex，继续开发。
