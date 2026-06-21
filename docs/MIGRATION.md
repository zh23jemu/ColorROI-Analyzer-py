# ColorROI Analyzer 迁移与环境恢复指南

本文档用于把本项目迁移到另一台 Windows 电脑，并继续用 Codex 开发。

## 1. 迁移内容

迁移包应包含以下内容：

- `app.R`：Shiny 主程序。
- `README.md`：项目使用说明。
- `AGENTS.md`：项目记忆、当前状态、风险和下一步计划。
- `.gitignore`：本地缓存和调试中间文件忽略规则。
- `scripts/`：依赖检查、冒烟测试、图片检查和测试服务脚本。
- `pics/`：当前 8 张 1920×1080 示例图片。
- `test-artifacts/`：已通过的端到端验证截图和 CSV 样例。
- `0.jpg`、`1.jpg`、`新建 文本文档.txt`：早期样例和原型代码，保留用于追溯。
- `docs/GIT_STATE.md`：当前 Git 状态、最近提交和恢复 Git 历史的方法。
- `ColorROI-Analyzer.git.bundle`：完整 Git 历史包，可在新电脑上恢复提交记录。

迁移包不包含：

- `.git/` Git 内部目录。
- 本机 R 包缓存。
- Shiny 临时文件。
- 端到端测试失败时产生的调试截图。

## 2. 新电脑安装 R

推荐安装 R 4.6.0 或更新的 4.x 版本。

Windows 推荐从 CRAN 下载：

```text
https://cloud.r-project.org/bin/windows/base/
```

安装完成后，打开 R 或 RStudio，在项目目录中执行后续命令。

## 2.1 可选：恢复 Git 历史

如果你需要继续用 Git 提交开发记录，可以使用迁移包中的：

```text
ColorROI-Analyzer.git.bundle
```

推荐方式是在解压目录的上一级执行：

```powershell
git clone ColorROI-Analyzer.git.bundle ColorROI-Analyzer
```

如果已经解压了项目文件，可以参考 `docs/GIT_STATE.md` 中的恢复方法。

## 3. 安装项目依赖

在 R 控制台中执行：

```r
install.packages(c("shiny", "shinythemes", "jpeg", "png", "plotly", "base64enc", "DT"))

if (!requireNamespace("BiocManager", quietly = TRUE)) {
  install.packages("BiocManager")
}
BiocManager::install("EBImage")
```

如果网络较慢，可以在 R 中设置 CRAN 镜像后再安装。

## 4. 恢复后检查环境

在项目根目录执行：

```r
source("scripts/check_dependencies.R")
```

预期输出：

```text
依赖检查通过：所有必需 R 包均已安装。
```

然后运行核心分析冒烟测试：

```r
source("scripts/smoke_test.R")
```

预期会看到类似输出：

```text
核心分析冒烟测试通过：ROI=... px，毛发=... px，DMDI=...
```

检查样例图片目录：

```r
source("scripts/inspect_images.R")
inspect_images("pics")
```

预期 8 张 JPG 均为 `ok`，尺寸为 `1920 × 1080`。

### Windows R locale 提示

如果在 Windows 上通过自动化终端运行 R 时看到 `Setting LC_* = C.UTF-8 failed`，并且 `inspect_images("pics")` 返回空表，但资源管理器中能看到图片，通常是当前终端给 R 传入了 Windows R 不识别的 `C.UTF-8` locale，导致中文文件名不可见。

可以只在当前 PowerShell 会话中临时清空这些环境变量后再运行检查：

```powershell
$env:LANG=""
$env:LC_ALL=""
$env:LC_CTYPE=""
& "C:\Program Files\R\R-4.6.0\bin\Rscript.exe" -e 'source("scripts/inspect_images.R"); inspect_images("pics")'
```

该设置只影响当前终端会话，不需要写入系统环境变量。

## 5. 启动应用

在 R 控制台中执行：

```r
shiny::runApp("app.R")
```

或使用测试服务脚本：

```r
source("scripts/run_test_server.R")
```

默认测试服务监听：

```text
http://127.0.0.1:3840
```

也可以通过环境变量覆盖端口：

```r
Sys.setenv(COLORROI_TEST_PORT = "3841")
source("scripts/run_test_server.R")
```

## 6. 功能复核流程

迁移完成后，建议至少用一张 `pics/` 中的图片做完整人工流程：

1. 上传图片。
2. 用黄色画笔圈出 ROI。
3. 用红色画笔标注毛发。
4. 点击“开始分析”。
5. 填写样本名和编号。
6. 点击“保存记录”。
7. 点击“导出 CSV”。
8. 检查 CSV 是否包含 `sample_id`、`roi_px`、`hair_px`、颜色比例和 `dmdi`。

## 7. 当前已知风险

- 黑、棕、灰、蓝四类的命名仍是启发式规则，尚未用人工标注真值校准。
- 蓝色标签已加 `b* < 0` 阈值，避免把相对最不黄的皮肤聚类误命名为蓝；仍需结合肉眼判断和人工真值继续校准灰、棕、蓝等标签边界。
- ROI 依赖用户手动画闭合区域，边界没有闭合时可能填充异常。
- 毛发修复适合细小毛发和小遮挡，大面积遮挡仍需人工复核。
