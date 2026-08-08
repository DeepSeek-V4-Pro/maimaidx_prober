# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.0.0] - 2026-08-08

### 重构（相当于重做插件）

- 将 3700+ 行的单文件 `plugin.py` 拆分为模块化 `core/` 包：
  命令层（`commands/`）、服务层（`services/`）、渲染层（`renderers/`）、
  客户端（`clients/`）、存储（`stores/`）分层管理，便于后续维护。
- 插件入口 `plugin.py` 保持 MaiBot 兼容形态（`create_plugin()` 工厂）。

### 清理落雪（lxns）相关内容

- **移除**全部需要 lxns 账号认证的命令：
  `/mai lxns bind`、`unbind`、`b50`、`my`、`rank`、`history`、
  `comment`、`collections`、`heatmap`、`trend`、`year`。
- 移除 `LxnsBindingStore`、JWT 认证探测等不可用且维护成本高的代码。
- **保留**公开接口数据补全：
  `/mai lxns status`、`/mai lxns song`（增强曲目详情）、
  `/mai lxns alias import`（社区别名导入），以及曲目详情/封面的 lxns 数据补全。

### 问题修复

- **修复每日运势曲绘图片插入失败**：
  根因为 `assets.lxns.net` 对部分客户端（如 Python 3.12 TLS 指纹）返回
  「HTTP 200 + JS 反爬挑战页」，旧版误将 HTML 当作 PNG 内嵌导致曲绘空白。
  新增封面内容魔数校验 + MIME 自动识别 + 水鱼兜底 + 缓存。
- 图片加载等待逻辑由「仅判断 `img.complete`」改为可选的
  「`complete && naturalWidth > 0`」，避免坏图静默通过。
- B50 / 个人成绩中的达成率等字段增加数值容错，避免 `None` 导致渲染失败。
- 渲染器优先使用 MaiBot 宿主 `render.html2png` 能力（宿主统一管理 Chromium、
  并发与沙箱参数），失败时回退内置 Playwright，并默认追加 `--no-sandbox`。

### 容器部署（GitHub issue #1）

- 新增 `requirements.txt` 依赖清单。
- 新增 `install_deps.py` 一键安装脚本（Python 包 + Chromium）。
- 新增 `Dockerfile.example` 容器构建示例。
- 新增 `[plugin].auto_install_deps` 配置：依赖缺失时自动安装。

### 渲染效果优化

- 全部图片默认 2x 设备像素比（高清）输出，可配置。
- 封面缺失时显示「曲绘缺失」占位，不再出现空白/破图。
- 曲目详情、运势、帮助等卡片样式微调（换行、溢出处理）。

### 文档

- 重写 `README.md`：模块结构、容器部署、v2.0 命令表、FAQ 全面更新。
- 新增本文件 `CHANGELOG.md`。

### 命令统一（移除双源前缀）

- 移除 `/mai df` 前缀：`/mai df b50` → `/mai b50`、`/mai df my` → `/mai my`、
  `/mai df bind <Token>` → `/mai bind <Token>`、`/mai df unbind` → `/mai unbind`。
- 移除 `/mai lxns` 前缀与冗余命令：`/mai lxns help`、`/mai lxns status`（已并入
  `/mai status`）、`/mai lxns song`（已并入 `/mai song` 的 lxns 数据补全）；
  `/mai lxns alias import` → `/mai alias import`。
- `/mai help` 帮助图同步改为统一命令表。
- lxns 仅作公开数据补全，不再有独立的命令入口。

### Maidle 猜歌线索格式化修复

- 水鱼 `/maidle/single` 返回的线索为 `{result, value, greater}` 结构
  （`result` 是 green/amber 颜色类），旧版把内部字段原样打印成
  `result= value=xxx`，可读性差。
- 重写线索格式化：显示曲名/作者/类型/分类/版本/BPM/定数，命中标 `✓`、
  接近标 `≈`、不同标 `✗`，BPM/定数/版本附加目标方向提示
  （目标更高/更低/更新/更旧），绿色谱面标签汇总为「目标共有标签」，
  猜中时显示 `🎉 猜中啦！`。
- 开局图片标注「开局线索（系统代猜）」，与玩家主动猜测区分。

### lxns 数据补全修复

- **修复 ID 体系不匹配**：lxns 与新水鱼的歌曲 ID 不同源（老曲一致，新曲
  lxns id = 水鱼 id − 10000，如 11115 → 1115），旧版按 ID 直查只有约 44%
  命中。现按「ID 候选 + 标题交叉确认」匹配，抽样 60/60 全命中。
- **修复分类/版本名称解析**：lxns 歌曲的 `genre` 是代码串（如
  `POPSアニメ`），`version` 是子版本号（如 21001），旧版按 id/精确版本查表
  失败、显示原始编号。现按代码串映射中文分类名，子版本号就近匹配版本名
  （21001 → 舞萌DX 2021）。

---

## [1.1.0] - 2026-06

- 接入 lxns（落雪）双源查分：曲目增强、别名导入、封面 CDN。
- 新增 B50 图片、个人成绩、猜歌（Maidle）、谱面统计、运势、收藏品等命令。
- 修复若干图片渲染与搜索问题。

## [1.0.0] - 2026-05

- 首个正式版本：连接 diving-fish 查分器，提供曲目搜索、B50、个人成绩查询。

[2.0.0]: https://github.com/DeepSeek-V4-Pro/maimaidx_prober/releases/tag/v2.0.0
[1.1.0]: https://github.com/DeepSeek-V4-Pro/maimaidx_prober/releases/tag/v1.1.0
[1.0.0]: https://github.com/DeepSeek-V4-Pro/maimaidx_prober/releases/tag/v1.0.0
