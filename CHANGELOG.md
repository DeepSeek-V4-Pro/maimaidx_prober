# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## 当前状态（2026-08-11）

> 项目处于**开发中的半成品**状态：功能链路可用，但打磨程度不均衡。

- **B50 成绩图渲染相对完善**：官方版式复刻 + 官方素材 + 头像/段位/版本等头部
  信息齐全，是本插件完成度最高的部分；
- **其余图片渲染**（my / song / today / help / heatmap / trend / maidle /
  history / rank / year / collections / pick / status / charts / alias /
  lxns status / player / plate）已统一为 B50 同风格浅色面板；
- 使用文档见 [README.md](README.md)，开发文档见 [DEVELOPMENT.md](DEVELOPMENT.md)。

## [3.0.0] - 2026-08-11

> v3.0 是双源查分的完整重构版：水鱼 + 落雪统一选源、落雪账号能力全部回归、
> 全部命令图片化、成绩双向同步、开发者权限控制。改动全部归入 3.0（不拆大版本）。

### 落雪（lxns）账号接入

- 三种接入方式：**OAuth 2.0**（OOB 授权码，state + PKCE/密钥模式自适应，access
  15 分钟 / refresh 30 天且刷新轮换、单飞刷新）、**个人 API 密钥**、
  **开发者 API**（好友码查询）；
- 绑定管理：`/mai lxns bind / bind token / bind code / unbind / status`；
- 落雪独有能力命令回归：`/mai lxns heatmap / trend / history / rank / year /
  collections / upload / comment`；
- 新增 `lxns_bindings.json` 与 `[lxns]` 配置节（OAuth / 个人密钥 / 开发者密钥）；
- 评论接口实测落雪服务端全部路径 404，命令保留并给出友好提示。

### 统一数据服务层

- 新增 `PlayerQueryService`：自动选源（绑定落雪 → 开发者好友码 → 水鱼兜底）、
  失败回退、归一化、互补合并；`/mai b50`、`/mai my` 两源只保留一份实现；
- 强制数据源：`--lxns` / `--df`（含 `--落雪` / `--水鱼` 别名）。

### 成绩双向同步

- `/mai lxns upload`：水鱼 → 落雪（缺失补齐、更高覆盖并保留原游玩时间、相同/更低跳过）；
- `/mai df upload`：落雪 → 水鱼（水鱼 `update_records` + Import-Token，
  title+type 按水鱼曲库严格匹配，只升不降；服务层支持 dry_run）；
- 数据互补：定数（DS）补全、封面 ID 修正（新曲 id − 10000）、
  官方 RA 系数表回填（宴会场 utage 除外，RA 恒为 0）。

### 图片渲染

- B50 重做为**官方版式**（马卡龙渐变、难度配色卡片、官方徽章素材、头像、
  段位/阶级、渐变 Rating、版本图标）；BEST 35 / 15 不足补「未游玩」占位卡；
  卡片含 Lv 难度文字与单曲游玩时间；
- 全部交互命令图片化：charts / alias list / lxns status / player / plate /
  hot / ranking / best 等统一为 B50 同风格浅色面板；
- `/mai lxns collections` 收藏品实物图（资源 CDN，称号 `color=image` 用图片）；
- `/mai lxns year` 年度回顾多维度增强（评级/FC/难度分布、常玩分类与 BPM、
  最常时段、Rating 成长对比）。

### 水鱼能力

- `/mai plate <版本代号>`：按版本查询（需 `[server].developer_token`）；
- `/mai hot [N]`：热门歌曲加权统计（新曲 ×2、≥13 级 ×2、≥13.7 ×3）；
- `/mai ranking [N]`：DX Rating 排行榜（公开数据，本地排序）；
- `music_data` / `chart_stats` 自动 ETag / 304 增量缓存；
- `/mai b50`、`/mai my` 检测水鱼查询掩码并提示。

### 开发者能力与权限

- 开发者端点：好友码查询、`/mai lxns ap50`（All Perfect 50）、
  `/mai lxns qq`（按 QQ 查玩家）、`/mai lxns best <好友码>`；
- **`[plugin].developer_qq` 白名单**：只有白名单内 QQ 可触发开发者功能，
  列表为空时全部关闭，防止开发者密钥被陌生人借用。

### 工程与健壮性

- 数据存储迁移到运行时标准目录（旧插件目录自动迁移、兼容读取）；
- 依赖自检 + `install_deps.py` + Dockerfile 示例 + `auto_install_deps`；
- 错误响应非 dict 容错、落雪别名导入翻页上限、`fc_dist` 长度保护、
  封面 ID / 难度索引容错、`/mai my` 按（song_id, 类型）去重；
- 清理死代码与未使用导入。

### 文档

- 文档拆分为用户版 [README.md](README.md) 与开发者版 [DEVELOPMENT.md](DEVELOPMENT.md)；
- 新增「落雪接入」章节、开发者权限说明；修正 FAQ（BEST 15 占位卡等）；
- 扩充「安全说明 / 免责声明」：密钥类型、存储与吊销方式、日志红线、白名单、
  责任边界；开发者文档新增「安全与密钥处理规范」与发布前审查清单。

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
