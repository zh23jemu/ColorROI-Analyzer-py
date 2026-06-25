# ColorROI-Analyzer-py 项目记忆

## 项目目标

将 `C:\Coding\ColorROI-Analyzer\` 中的 R Shiny 版 ColorROI Analyzer 完整迁移为当前目录下的 Python 项目。核心功能保持一致：上传图片、手动画黄色 ROI 边界、红色标注毛发/遮挡、可选局部修复、Lab 四分类、DMDI 计算、结果预览、记录保存和 CSV 导出。

## 技术栈

- Python 3.11+。
- Streamlit 用于交互式 Web 应用。
- NumPy、SciPy、scikit-image、scikit-learn、Pillow、Pandas 和 Plotly 用于图像分析、聚类、可视化和导出。

## 当前架构

当前已建立 `src/colorroi_analyzer/` 核心算法包，并将 R 版的图片读取、ROI 边界填充、手动/自动毛发检测与局部修复、RGB 到 Lab、KMeans 四分类、DMDI 计算和热图生成迁移到 Python。`app.py` 是 Streamlit 交互界面入口，支持上传图片、画 ROI/毛发、自动毛发兜底分析、预览、保存记录和 CSV 导出。`scripts/` 中已提供冒烟测试、图片目录检查和人工复核表生成脚本，`tests/` 中已提供核心算法 pytest 测试。

## 开发规范

- 保持最小修改，优先修复和复刻核心行为。
- 新增 Python 代码默认写较详细中文注释，说明用途、关键逻辑和边界情况。
- 编辑文件前先读取相关文件。
- 不直接删除文件。
- 有意义变更后同步更新本文件。

## TODO

- 进行浏览器端人工手绘流程复核，确认 Streamlit 画布标注提取与预览结果一致。

## Current Status

已完成 Python 核心计算层迁移和 Streamlit 应用入口实现，创建本地 `.venv` 并安装项目依赖。`scripts/smoke_test.py` 已跑通，8 张 `pics/` 示例图片均可读取，pytest 核心测试通过。已启动 `.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501`，并确认 `http://127.0.0.1:8501` 返回 200。上传图片时报错 `AttributeError: module 'streamlit.elements.image' has no attribute 'image_to_url'` 以及后续 `AttributeError: 'int' object has no attribute 'width'` 的问题已通过 Streamlit 兼容 shim 修复：shim 会提供 `streamlit-drawable-canvas` 旧签名所需的 `image_to_url(image, width, ...)` 包装器，并把整数宽度转换为新版 Streamlit 需要的 `LayoutConfig`。依赖约束也已收紧为 `streamlit>=1.35,<1.40`，避免新环境自动安装到不兼容版本。已修复用户画出闭合黄色 ROI 但程序提示“ROI 内有效像素过少”的问题：应用现在优先从 `canvas_result.json_data` 的 Fabric 手绘路径对象重建 ROI/毛发 mask，不再优先从背景图和标注合成后的截图按颜色猜测。已按 TXT 原始需求补齐自动毛发检测：当用户没有红色手动标注时，分析流程会自动执行 black-hat + Otsu + opening 的毛发候选检测，并在 ROI 内生成毛发 mask。已补充自动皮损/ROI 候选识别：系统会用图像边缘估计背景肤色，在 Lab 空间找出与背景差异较大的连通区域作为自动 ROI 候选；用户手动画出的黄色 ROI 优先级最高，可覆盖自动候选。已修复 Streamlit 热更新后旧 `AnalysisResult` 对象缺少 `effective_px` 字段导致的指标渲染报错，界面会用 `roi_px - hair_px` 兜底计算有效区。已修复自动毛发检测结果在 UI 中不明显的问题：分析结果现在记录 `hair_source`，指标显示“毛发标注（自动/手动）”，预览图使用分析后的 `analysis.hair`，上传文件变化时会清空旧分析结果。为避免 Streamlit 热更新导致后端自动兜底未反映到界面，app 层点击分析前会显式准备最终毛发 mask：手动红色 mask 非空则用手动，否则立刻执行自动毛发检测并传入分析函数。已修复刷新页面时顶层导入 `auto_hair_mask` 失败的问题：`app.py` 不再从 `core` 顶层直接导入该函数，而是通过 `colorroi_core` 模块动态获取；若旧 Streamlit 进程缓存模块缺少函数，会 reload 本地 core 模块再调用。已修复旧 Streamlit 进程缓存 `analyze_image()` 旧签名导致 `hair_source_hint` 参数报错的问题：app 层改为动态调用分析模块，必要时 reload `analysis.py`，极端旧签名下退回旧调用并补充来源字段。结果指标区已拆成两行显示：第一行展示 ROI 面积、毛发标注和有效区，第二行单独展示黑、棕、灰、蓝灰和 DMDI，避免右侧面板中“灰/蓝灰/DMDI”被截断。已生成 `pics/` 8 张样张的自动皮损候选和自动毛发标注批量复核报告，输出到 `reports/pics_hair_review/index.html`、`reports/pics_hair_review/index_standalone.html` 和 `reports/pics_hair_review/results.csv`。已创建 GitHub public repo `https://github.com/zh23jemu/ColorROI-Analyzer-py` 并切换 AWS 部署为 Git 同步：当前 `ap-east-1` 公网测试实例 `i-035e3e54eeef40e32` 为 `t3.small`、Amazon Linux 2023、8GB gp3，从 GitHub clone `master` 分支到 `/opt/colorroi`，通过 `colorroi-git-sync.timer` 每分钟尝试 `git pull --ff-only`，公网测试地址为 `http://95.40.6.145/`，当前直连 HTTP 探测返回 200。已修复橡皮擦只能整对象删除的问题：橡皮擦改为白色自由笔刷，JSON 解析时按绘制顺序把擦除路径从 ROI 和毛发 mask 中局部扣除，并新增回归测试覆盖局部擦除。已修复 Windows 服务器上传图片后自定义画布弹出 `Bad message format: Tried to use SessionInfo before it was initialized` 的兼容问题：组件现在延迟发送 `componentReady`，并只在收到首帧 `streamlit:render` 后回传高度和 mask，避免与 Streamlit 前端会话初始化竞争。

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
- 将 Streamlit 画布 mask 提取改为优先解析 `canvas_result.json_data` 中的 Fabric path 对象，并根据路径颜色重建黄色 ROI 边界和红色毛发 mask，避免背景图片颜色干扰。
- 新增 `tests/test_app_masks.py`，覆盖基于画布 JSON 路径提取 ROI/毛发 mask 并填充 ROI 的流程；当前 pytest 3 项通过。
- 新增 `auto_hair_mask()`，迁移 TXT 原始需求里的自动毛发检测流程：灰度图、closing、black-hat、Otsu 阈值和 opening。
- 更新 `analyze_image()`：红色手动毛发 mask 为空时自动检测 ROI 内毛发；分析像素改为 `ROI - 毛发` 有效区。
- Streamlit 指标和导出记录新增 `effective_px`，用于显示/保存 ROI 有效分析像素数。
- 新增自动毛发检测和空手动 mask 分析测试；当前 pytest 5 项通过，核心冒烟测试通过。
- 修复 Streamlit session 中旧版 `AnalysisResult` 对象缺少 `effective_px` 时的 UI 渲染报错，新增 `_effective_px()` 兜底函数；当前 pytest 5 项通过。
- 分析结果新增 `hair_source`，UI 指标显示毛发 mask 来源；预览图改为显示分析后的自动/手动毛发 mask，并在上传文件变化时清理旧分析状态。命令行模拟 ROI 验证自动毛发来源为 `auto` 且检测到 516 px，pytest 5 项通过。
- app 层新增 `_prepare_hair_mask_for_analysis()`，点击分析前显式生成最终毛发 mask，并通过 `hair_source_hint` 传入 `analyze_image()`；命令行验证返回 `auto 516`，pytest 6 项通过。
- 移除 `app.py` 对 `auto_hair_mask` 的顶层直接导入，改为动态获取并在缺失时 reload `colorroi_analyzer.core`，修复旧 Streamlit 模块缓存导致刷新页面 ImportError；当前 `import app`、pytest 6 项和自动毛发模拟均通过。
- 将 `analyze_image()` 顶层直接导入改为动态模块调用，遇到旧签名 `hair_source_hint` 报错时 reload `analysis.py` 后重试，仍不支持时退回旧调用并补来源字段；当前 app 层模拟输出 `auto 516 auto 516`，pytest 6 项通过。
- 优化 Streamlit 分析结果指标布局，将基础像素指标和颜色/DMDI 指标拆成两行，修复右侧“灰、蓝灰、DMDI”显示被截断的问题。
- 新增 `scripts/batch_review_pics.py`，批量分析 `pics/` 样张并生成 HTML 复核报告、CSV 汇总、原图/毛发叠加/DMDI 热图预览；当前 8 张样张已全部生成报告。
- `scripts/batch_review_pics.py` 新增单文件报告输出 `reports/pics_hair_review/index_standalone.html`，图片以内嵌 base64 形式写入，方便直接发给用户确认。
- 用户已确认该项目可以使用 Python 版实现，不再要求与原 R 版做逐项端到端数值对照。
- 根据用户反馈更新 README 和样张复核报告文案，明确报告只用于确认自动毛发/遮挡识别效果，不做自动皮损分割；正式分析中的皮损/ROI 仍由用户手动画黄色边界。
- 新增 `auto_lesion_mask()` 和 `mask_to_boundary()`，支持传统图像分割生成自动皮损/ROI 候选；Streamlit 页面新增“未手动画 ROI 时自动识别皮损候选”开关，手动画 ROI 优先覆盖自动候选；批量复核报告改为展示自动皮损候选（淡黄）和自动毛发/遮挡（红色）。
- 用户反馈收紧版自动皮损候选效果不如上一版，已回退 `fix: 收紧自动皮损候选范围` 的算法和报告结果，恢复较宽松的上一版自动 ROI 候选。
- 在 AWS `ap-east-1` 创建公网测试部署：使用已有 VPC 子网 `subnet-03781c1b2a13b3e3d`，安全组 `sg-06d20438196dca6f6` 开放 TCP `80` 和 `8501`。由于用户浏览器访问 `8501` 超时，改为 `t3.small` 实例 `i-0a23b365d8517d699` 直接监听 `80`，测试地址 `http://43.198.137.234/` 直连返回 200；旧实例 `i-052190b6f08e3282b` 和 `i-00cd03f5b3cfbafab` 已发起终止。
- 修复云端 Streamlit 1.39 不支持 `st.image(use_container_width=True)` 导致上传图片后报错的问题：新增 `_image()` 兼容封装，旧版自动退回 `use_column_width=True`；已重新打包上传 S3，并部署修复版实例 `i-017b0027602f81aed`，公网地址 `http://18.162.126.69/` 返回 200，旧实例 `i-0a23b365d8517d699` 已发起终止。
- 已创建 GitHub public repo `https://github.com/zh23jemu/ColorROI-Analyzer-py`，本地 `master` 分支跟踪 `origin/master`；新增 `deploy/aws-git-sync-user-data.sh` 模板，用于让 AWS EC2 从 GitHub clone 项目并通过 systemd timer 定期执行 `git pull --ff-only` 同步代码。
- 已用 Git 同步模板重建 AWS 公网测试实例：新实例 `i-035e3e54eeef40e32` 从 GitHub clone 代码并启用 `colorroi-git-sync.timer`，地址 `http://95.40.6.145/` 返回 200；旧 zip 部署实例 `i-017b0027602f81aed` 已发起终止，S3 部署包和 bucket 已删除，安全组已移除 `8501` 入站规则，仅保留 `80/tcp`。
- 修复橡皮擦交互：将“橡皮擦”从 `transform` 模式改为 `freedraw` 白色笔刷，解析 Fabric.js JSON 时识别白色擦除路径并按顺序从黄色 ROI 和红色毛发 mask 中局部扣除；新增 `test_extract_masks_applies_eraser_paths_in_draw_order` 覆盖擦除逻辑，当前 pytest 8 项通过。
- 调整橡皮擦显示方式为透明白色笔刷，避免在画布上覆盖原图像素；后端仍按透明白色路径作为擦除操作处理，并新增透明白色擦除回归测试，当前 pytest 9 项通过。
- 本地修复顶部大图擦除后不变化的问题：新增累计标记层，画布仅采集本轮笔画，合并后以标记预览图作为下一轮画布背景，使橡皮擦后的黄色/红色标记在顶部大图同步变化；当前修改仅本地 commit，暂不 push，等待用户通知后再同步 AWS。
- 本地优化顶部画布刷新体验：去掉额外 `_rerun()`，改为在渲染画布前读取上一轮组件 JSON 并合并到累计标记层，减少每次画笔/橡皮擦操作后的明显二次刷新；当前 pytest 10 项通过，仍未 push 到 GitHub/AWS。
- 已回退“关闭画布实时回传”的交互方案：用户确认手动点击画布左下角应用标记不可接受，因此恢复 `st_canvas(update_streamlit=True)` 自动回传；当前限制是 `streamlit-drawable-canvas` 没有真正的前端局部橡皮擦，橡皮擦只能通过回传到 Python 后扣除累计标记层，若要做到无刷新即时擦除黄色/红色标记，需要后续替换为自定义前端画布组件。当前修改仅本地 commit，暂不 push。
- 本地替换第三方画布组件：新增 `components/colorroi_canvas/index.html` 无构建自定义 Streamlit 前端组件，使用原图层、可见标记层、ROI mask 层和毛发 mask 层实现即时绘制与即时橡皮擦；橡皮擦通过前端 `destination-out` 只擦黄色/红色标记和隐藏 mask，不覆盖原图。`app.py` 改为通过组件回传的 PNG mask 更新 session，`pyproject.toml` 和 `requirements.txt` 已移除 `streamlit-drawable-canvas` 依赖，README 已同步说明。当前修改仅本地，暂不 push。
- 修复自定义画布二次擦除时旧标记复活的问题：`app.py` 现在会在渲染前读取当前组件 key 的上一次 PNG mask 回传并合并到 session，再把最新累计 mask 传回前端，避免第二次擦除时组件被旧后端状态覆盖；新增测试覆盖组件回传格式识别。
- 优化自定义画布橡皮擦闪动：前端组件只在图片或尺寸变化时重建底图，不因 ROI/毛发 mask 变化反复整层清空和重绘，减少第二次及后续橡皮擦时的轻微闪烁感。
- 将 Streamlit 分析界面英文化：侧边栏上传、绘制模式、分析选项、样本信息、预览标题、指标、提示、保存记录、CSV 下载按钮和分析错误信息均改为英文；导出记录中的字段值也改为英文标签。内部中文注释和项目记忆仍保留中文。
- 根据用户反馈调整预览标题，将 `After hair inpainting` 改为 `After hair removal`，更贴近“毛发去除后”的表达。
- 修复 Windows 服务器上传图片后自定义画布组件偶发 `Bad message format` 弹窗：组件通信增加 `componentReady` 防重复、首帧 `streamlit:render` 初始化保护，以及高度和 mask 回传守卫；当前 `.venv\Scripts\python.exe -m pytest` 12 项通过，`import app` 正常。
- 继续修复 Windows 服务器上传图片后页面持续 `Running...` 并重新加载的问题：自定义画布组件现在对重复 `setFrameHeight` 做去重，同一高度不会反复通知 Streamlit；图片和 mask 异步加载增加 render 序号保护，旧加载结果不会覆盖新画布。当前 `.venv\Scripts\python.exe -m pytest` 12 项通过，`import app` 正常。
- 优化自定义画布同步机制：画笔和橡皮擦操作只在浏览器前端即时更新，不再每画一笔或每擦一次就调用 `setComponentValue` 触发 Streamlit rerun；点击 `Analyze` 时通过 `syncToken` 请求组件回传一次完整 ROI/毛发 mask，下一轮自动执行分析。新增 pending token 回归测试，当前 `.venv\Scripts\python.exe -m pytest` 13 项通过。

## Next TODO

- 在浏览器中重新执行一次完整人工流程：上传真实样例、手绘 ROI、不标红色毛发时验证自动毛发检测、再标红色毛发时验证人工 mask 优先、保存记录和导出 CSV。
- 打开 `reports/pics_hair_review/index_standalone.html` 人工查看每张样张淡黄色自动皮损候选和红色毛发候选是否漏检或误检，并据此决定是否继续调自动皮损或自动毛发参数。
- 在浏览器中重点复核自定义前端画布：黄色 ROI、红色毛发、橡皮擦即时擦标记、清空标记、开始分析、保存记录和 CSV 导出。
- 在 Windows 服务器上 `git pull` 更新后，重新上传图片确认 `Bad message format` 弹窗是否消失，并确认画布绘制/橡皮擦/分析流程仍正常。
- 如果 Windows 服务器更新后仍持续 `Running...`，优先检查服务器是否已重启 Streamlit 进程、浏览器是否仍缓存旧组件 HTML，以及服务器实际 Streamlit 版本；Python 3.12 本身不是当前首要怀疑点。
- 在服务器上复核新的 Analyze 同步流程：绘制 ROI、毛发标记和橡皮擦时页面不应再整页刷新；点击 Analyze 后允许出现一次正常 rerun，并应自动完成分析。
- 用户完成公网测试后，终止 AWS 实例 `i-035e3e54eeef40e32` 并清理安全组 `sg-06d20438196dca6f6`，避免持续计费。

## Open Issues

- 当前 Windows 终端可能以非 UTF-8 编码显示中文脚本输出，计算结果不受影响。
- 自定义画布组件为无构建静态 HTML/JS，仍需在真实浏览器里复核 Streamlit component 通信、mask 回传大小和移动端触控体验。
- 自动皮损候选为传统图像分割方法，不是深度学习分割模型；复杂背景、光照不均或皮损接近肤色时可能需要用户手动画 ROI 修正。
- 当前 `.venv` 因已有 Streamlit 服务占用二进制文件，未完成依赖降级；但应用内兼容 shim 已验证可在 Streamlit 1.58 中补齐缺失 API。若重建全新 `.venv`，依赖约束会安装兼容范围内的 Streamlit。
- AWS 公网测试实例当前开放 `80` 到 `0.0.0.0/0`，仅适合短期用户验收。应用没有登录鉴权，不应上传敏感图片，测试结束后应尽快清理云资源。

## Architecture Decisions

- Python 重建采用核心算法包和 Streamlit UI 分离的结构，便于非交互式测试和后续界面维护。
- 原项目资源和测试产物保留为迁移参考资料，不作为 Python 运行入口；后续验收以 Python 版功能和用户确认效果为准。
- 临时公网验收优先采用单台 EC2 直接运行 Streamlit，减少部署复杂度和固定成本；图像依赖在 `t3.micro` 上安装和运行不稳定时，使用 `t3.small` 保证用户验收可用性。生产化再考虑域名、HTTPS、鉴权、容器化或托管平台。
- GitHub 仓库作为本地和 AWS 的代码同步源；AWS 测试实例应从 public repo clone 代码，并通过快进式 `git pull --ff-only` 同步，避免继续依赖 S3 zip 包作为代码来源。
- 自定义画布采用前端本地即时编辑、Analyze 时一次性同步 mask 的交互模型；这是为了避开 Streamlit 组件值回传必然触发 rerun 的机制，提升画笔和橡皮擦连续操作体验。
