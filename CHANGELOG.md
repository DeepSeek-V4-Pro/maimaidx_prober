# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## 当前状态（2026-08-11）

> 项目处于**开发中的半成品**状态：功能链路可用，但打磨程度不均衡。

- **B50 成绩图渲染相对完善**：官方版式复刻 + 官方素材 + 头像/段位/版本等头部
  信息齐全，是本插件完成度最高的部分；
- **其余图片渲染**（my / song / today / help / heatmap / trend / maidle /
  history / rank / year / collections / pick / status）已统一为 B50 同风格
  浅色面板（字体/配色一致），但布局细节与装饰仍在完善；
- `/mai charts`、`/mai alias *` 等仍为纯文本输出，待图片化；
- 完整待办见 README「后续计划 (Roadmap)」。

## [3.0.0] - 2026-08-11

### 落雪（lxns）账号接入

- 新增统一数据服务层 `PlayerQueryService`：`/mai b50`、`/mai my` 按绑定/配置
  自动选源（绑定落雪 → 开发者密钥+好友码 → 水鱼兜底），两源共有功能只保留一份
  实现；落雪请求失败时自动回退水鱼（强制落雪除外）。
- 新增三种落雪接入方式：
  - **OAuth 2.0**：`/mai lxns bind`（OOB 授权码流程，state + PKCE/密钥模式自适应），
    令牌自动单飞刷新（15 分钟 access / 30 天 refresh 轮换）；
  - **个人 API 密钥**：`/mai lxns bind token <密钥>`；
  - **开发者 API**：`config.toml` 配置密钥后可用好友码查询。
- 新增落雪独有能力命令：`/mai lxns heatmap / trend / history / rank / year /
  collections / upload / comment`（水鱼无对应能力，不重复实现）。
- 新增 `lxns_bindings.json`（OAuth 令牌 / 个人密钥）与 `[lxns]` 配置节扩展
  （`enable_oauth`、`oauth_client_id/secret`、`oauth_authorize_url`、
  `oauth_redirect_uri`、`oauth_scope`、`enable_developer_api`、`developer_api_key`）。
- **强制数据源**：`/mai b50 [用户] [--lxns|--df]`、`/mai my [--lxns|--df]`
  （含 `--落雪`/`--水鱼` 别名）跳过自动选源强制指定数据源；强制落雪未绑定/未配置
  时给出引导，强制水鱼需已绑定 Token 或提供用户名。
- 评论接口实测落雪服务端全部路径 404（接口未开放），命令保留并给出友好提示，
  列表字段已按前端结构（`comment_id`/`uploader`/`comment`/`upload_time`）预留。

### 数据互补

- 落雪成绩自动用水鱼曲库补全定数（DS）与水鱼歌曲 ID，修复新曲封面缺失
  （落雪新曲 ID = 水鱼 ID − 10000）。
- `/mai lxns upload` 水鱼成绩同步到落雪，采用**成绩只升不降**策略：
  缺失补齐、水鱼更高则覆盖（保留落雪原 `play_time`）、相同或更低跳过。

### 图片渲染

- 新增 `core/renderers/theme.py` 设计系统，B50 重做为**官方 B50 版式**
  （马卡龙渐变背景 + 菱形纹理、薄荷绿成绩区、青绿分区条、难度配色卡片
  Basic 绿 / Advanced 橙 / Expert 红 / Master 紫 / Re:Master 淡白 / UTAGE 粉、
  文字居左/曲绘居右半透明渐变衔接/右下编号框、圆润字体栈 Varela Round）。
- 内置游戏官方素材（`assets/`，MIT / SEGA，含 NOTICE），base64 内嵌无网络依赖：
  评级徽章、FC/FS/AP 奖牌、DX Score 星标（`dx_star`，按素材档位截断 1~3）、
  版本图标、阶级/段位徽章，CHUNITHM 全套图标预留。
- B50 头部：玩家头像（落雪来源，水鱼回退首字母）、白色名字框、友人对战阶级 +
  段位挑战徽章（素材白底 multiply 溶白）、分档渐变 DX Rating、版本图标
  （`assets/maimai/version/{version}.webp`，版本号来自 `[plugin].game_version`）。
- 全部指令图片渲染统一为 B50 同风格浅色面板（my / song / today / help / heatmap /
  trend / maidle / history / rank / year / collections / pick / status），
  页脚数据来源统一「数据来源: maimai」；其中 history / rank / year / collections /
  pick / status 为新增图片渲染（原先为纯文本）。
- 细节：DX 星标位于曲名右侧截断空位；评级/FC/FS 徽章放大、成绩字号缩小；
  游玩历史与绑定状态令牌过期时间转北京时间；热力图网格移入面板；
  排行表列名「DX Score」。

### 工程与健壮性

- 数据存储迁移到运行时标准目录 `data/plugins/deepseek-v4-pro.maimaidx-prober/`
  （旧插件目录数据自动迁移，兼容读取）。
- Dockerfile 版本约束加引号（`"aiohttp>=3.8"`、`"playwright>=1.40"`）。
- 宴会场（utage）曲目 `song_type` 判定优先检查 `difficulties.utage`；
  `/mai b50 <用户名>` 已绑定落雪时明确提示改用好友码；
  `/mai lxns trend` 默认版本跟随 `[plugin].game_version`；
  lxns 健康检查改走轻量端点（不再拉全量曲库）。
- 健壮性：曲库排序 ID 容错、谱面统计 `fc_dist` 长度保护、封面 ID 容错、
  my 难度索引类型保护。
- 清理死代码：删除 lxns 客户端 10 个未使用方法、未使用导入、
  `_get_tool_user_id`；入口 docstring 更新为 v3.0。

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
