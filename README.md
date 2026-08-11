# MaiMai DX 查分器插件（v3.0.0）

连接 [diving-fish（水鱼）](https://www.diving-fish.com) 查分器 API，并使用
[lxns（落雪）](https://maimai.lxns.net) 查分器 API（公开补全 + 账号能力），在
MaiBot 中提供舞萌 DX 的 B50 成绩图、个人成绩、曲目搜索、猜歌、谱面统计、
今日运势、落雪独有数据（热力图/趋势/历史/排行/年度回顾/收藏品）等功能。

> **水鱼 API**: <https://www.diving-fish.com/api/maimaidxprober>  
> **lxns API**: <https://maimai.lxns.net/api/v0>（公开 + OAuth / 个人密钥 / 开发者密钥）  
> **插件版本**: 3.0.0 | **插件 ID**: `deepseek-v4-pro.maimaidx-prober`

---

## ⚠️ 当前状态：半成品

本项目目前属于**开发中的半成品**，请以「可运行但未打磨」的标准看待：

- **B50 成绩图渲染相对完善**：已完成官方 B50 版式复刻（马卡龙背景、难度配色卡片、
  评级/FC/FS/DX 星官方素材、头像、段位/阶级徽章、渐变 Rating、版本图标），
  是本插件打磨程度最高的部分；
- **其余图片渲染**（个人成绩 / 曲目详情 / 运势 / 帮助 / 热力图 / 趋势 / 猜歌 /
  历史 / 排行 / 年度回顾 / 收藏品 / 选一 / 状态）已统一为 B50 同风格的浅色面板
  （字体、配色一致），但**布局细节与装饰仍在逐步完善中**；
- 部分命令（`/mai charts`、`/mai alias *` 等）仍为纯文本输出，暂未图片化；
- 已知问题与待办见文末「已知问题」与「后续计划」。

## 目录

1. [当前状态](#当前状态半成品)
2. [v3.0 更新要点](#v30-更新要点)
3. [架构说明](#架构说明)
4. [依赖清单](#依赖清单)
5. [安装方式](#安装方式)
6. [容器 / 1Panel 部署](#容器--1panel-部署)
7. [配置说明](#配置说明)
8. [命令列表](#命令列表)
9. [数据存储](#数据存储)
10. [已知问题](#已知问题)
11. [常见问题 (FAQ)](#常见问题-faq)
12. [卸载方式](#卸载方式)
13. [安全说明](#安全说明)
14. [免责声明](#免责声明)
15. [后续计划 (Roadmap)](#后续计划-roadmap)

---

## v3.0 更新要点

- **落雪（lxns）账号功能全面回归**：OAuth 2.0 / 个人 API 密钥 / 开发者 API
  三种接入方式，命令统一走 `PlayerQueryService` 数据服务层自动选源（绑定落雪 →
  开发者密钥+好友码 → 水鱼兜底）。
- **新增落雪独有能力**：`/mai lxns heatmap / trend / history / rank / year /
  collections / comment` 等命令（水鱼无此能力，不做平行实现）。
- **成绩只升不降**：`/mai lxns upload` 把水鱼成绩同步到落雪——缺失补齐、
  水鱼更高则覆盖（保留落雪原游玩时间）、相同或更低跳过。
- **定数与曲绘互补**：落雪成绩自动用水鱼曲库补全定数（DS）与封面 ID，
  修复新曲封面缺失问题。
- **B50 渲染全面重做**：官方 B50 版式（详见下方「B50 渲染」小节），
  其他图片渲染统一为同风格浅色面板。
- **数据目录迁移**：`bindings.json` / `aliases.json` / `lxns_bindings.json`
  迁移到 `data/plugins/deepseek-v4-pro.maimaidx-prober/`（旧目录兼容读取）。

### B50 渲染（当前最完善的部分）

- 版式复刻自 maimai DX 官方 B50 印刷效果图 / LxBot 生成图：
  马卡龙渐变背景（内嵌前端 `logo_background` 纹理）、薄荷绿成绩区、
  青绿分区条（BEST 35 / BEST 15）；
- 卡片按难度取色（Basic 绿 / Advanced 橙 / Expert 红 / Master 紫 /
  Re:Master 淡白 / UTAGE 粉），文字居左、曲绘居右并以半透明渐变衔接，
  右下排名编号框；
- 官方素材 base64 内嵌（`assets/`，MIT / SEGA，见 `assets/NOTICE`）：
  评级徽章、FC/FS/AP 奖牌、DX Score 星标、版本图标、阶级/段位徽章；
- 头部：玩家头像（落雪来源，水鱼自动回退首字母）、白色名字框、
  友人对战阶级 + 段位挑战徽章、按分档渐变变色的 DX Rating、游戏版本图标；
- 内嵌圆体字体 Varela Round（SIL OFL 1.1），中日文回退系统字体。

## 架构说明

### 数据流

```
用户 → MaiBot → 本插件 ─┬→ DivingFishApiClient (diving-fish) → 成绩/曲库/猜歌/运势
                        │
                        └→ LxnsApiClient (lxns) → 公开补全 + OAuth/个人密钥/开发者密钥
                                │
                                └→ PlayerQueryService 统一选源：
                                   绑定落雪 → 开发者密钥+好友码 → 水鱼兜底

封面: 水鱼 covers CDN（B50 主用）→ 落雪 assets.lxns.net 兜底（魔数校验）
曲目: 水鱼曲库 + 落雪公开数据补全（分类名/版本名/谱师/定数/note分布）
头像: 落雪 /maimai/icon/{id}.png（水鱼无头像接口）
```

### 模块结构

```
maimaidx_prober/
├── plugin.py                  # 插件入口（MaiBot 加载点）
├── assets/                    # 游戏官方素材（评级/奖牌/版本/阶级/段位 + 字体）
├── core/
│   ├── plugin.py              # 主类：生命周期 + 组装
│   ├── config.py              # 配置模型（pydantic）
│   ├── constants.py           # 评级/难度/版本常量
│   ├── assets.py              # 素材 base64 内嵌加载（data URI）
│   ├── util.py                # 通用工具
│   ├── clients/
│   │   ├── diving_fish.py     #   水鱼客户端
│   │   └── lxns.py            #   落雪客户端（公开 + 三态鉴权 + OAuth）
│   ├── stores/
│   │   ├── json_store.py
│   │   ├── aliases.py         #   本地别称
│   │   ├── bindings.py        #   水鱼 Token 绑定
│   │   └── lxns_bindings.py   #   落雪绑定（OAuth 令牌 / 个人密钥）
│   ├── services/
│   │   ├── music.py           #   曲库缓存/匹配/落雪补全
│   │   ├── covers.py          #   封面下载（魔数校验 + 兜底）
│   │   ├── renderer.py        #   宿主渲染 + Playwright 回退
│   │   ├── lxns_auth.py       #   授权链接/换 token/单飞刷新
│   │   ├── normalize.py       #   落雪 → 水鱼风格字段归一化
│   │   ├── player.py          #   统一数据服务层（选源/互补/回退）
│   │   ├── maidle.py          #   猜歌会话
│   │   └── deps.py            #   依赖自检/安装
│   ├── renderers/             # 图片渲染（HTML → PNG）
│   │   ├── theme.py           #   B50 设计系统 + 共享浅色面板样式
│   │   ├── b50.py             #   Best 50（最完善）
│   │   ├── my.py / song.py / today.py / help.py / maidle.py
│   │   ├── heatmap.py / trend.py / history.py / rank.py
│   │   ├── year.py / collections.py / pick.py / status.py
│   │   └── common.py          #   公共助手
│   └── commands/
│       ├── basic.py           #   /mai 基础功能
│       ├── score.py           #   /mai 成绩查询（b50/my/bind）
│       ├── lxns.py            #   /mai lxns 落雪独有能力
│       └── maidle.py          #   猜歌
├── requirements.txt / install_deps.py / Dockerfile.example
├── _manifest.json / config.toml / CHANGELOG.md / README.md
```

### 核心组件

| 组件 | 说明 |
|------|------|
| `PlayerQueryService` | 统一数据服务层：绑定落雪 → 开发者好友码 → 水鱼兜底 |
| `LxnsAuthService` | OAuth 授权链接 / 授权码换令牌 / 单飞刷新轮换 |
| `LxnsApiClient` | 落雪客户端：公开 + 个人密钥 + 开发者密钥 + OAuth 全端点 |
| `DivingFishApiClient` | 水鱼异步客户端 |
| `MusicService` | 曲库缓存、模糊搜索、落雪数据补全 |
| `CoverService` | 封面下载（内容校验 + 双源兜底 + 缓存） |
| `HtmlRenderer` | 宿主 `render.html2png` 优先，Playwright 回退 |
| `theme.py` | B50 设计系统：难度配色 / 渐变 Rating 分档 / 字体 / 面板样式 |

## 依赖清单

### Python 包

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| `aiohttp` | ≥3.8 | 异步 HTTP 请求 |
| `playwright` | ≥1.40 | 无头浏览器渲染图片（宿主能力不可用时的回退） |

### 浏览器

推荐启用 MaiBot 宿主的 `plugin_runtime.render`（由宿主自动下载/复用 Chromium）。
若走插件内置 Playwright 回退，需要 `python -m playwright install chromium`
（Windows 缓存于 `%USERPROFILE%\AppData\Local\ms-playwright\`）。

## 安装方式

### 步骤 1：复制插件

```bash
# Linux / macOS
cp -r maimaidx_prober/ /path/to/MaiBot/plugins/

# Windows (PowerShell)
Copy-Item -Recurse maimaidx_prober/ C:\path\to\MaiBot\plugins\
```

### 步骤 2：安装依赖

```bash
python install_deps.py
# 或手动：pip install -r requirements.txt && python -m playwright install chromium
```

插件加载时会自检依赖；若缺失且 `config.toml` 中
`[plugin].auto_install_deps = true`，会自动执行安装。

### 步骤 3：启用并验证

编辑 `plugins/maimaidx_prober/config.toml` 确保 `enabled = true`，然后发送
`/mai help`，收到命令总览图片即安装成功。

## 容器 / 1Panel 部署

容器重建会丢失手动安装的 Python 包，推荐以下方式之一：

**方式 A：Dockerfile 预装（推荐）**

参考仓库内 [Dockerfile.example](Dockerfile.example)，在构建阶段完成
`pip install` 与 `playwright install chromium`，并让 MaiBot 宿主接管渲染
（`plugin_runtime.render.auto_download_chromium = true`）。

**方式 B：依赖自检 + 自动安装**

设置 `config.toml`：

```toml
[plugin]
auto_install_deps = true
```

插件每次启动会检查 `aiohttp` / `playwright`，缺失时自动 `pip install`，
并执行 `playwright install chromium`。注意自动安装需要容器内网络与磁盘空间。

## 配置说明

```toml
[plugin]
enabled = true               # 是否启用插件
config_version = "3.0.0"     # 配置版本（请勿手动修改）
auto_install_deps = false    # 依赖缺失时自动安装
game_version = 25500         # B50 头部版本图标（25500=舞萌DX 2026）

[server]
base_url = "https://www.diving-fish.com/api/maimaidxprober"
request_timeout = 30
music_cache_ttl = 300

[lxns]
enable = true
base_url = "https://maimai.lxns.net/api/v0"
asset_url = "https://assets.lxns.net"
request_timeout = 30
music_cache_ttl = 300
enable_oauth = false         # 是否启用落雪 OAuth 绑定（/mai lxns bind）
oauth_client_id = ""         # 落雪 OAuth 应用 ID（开发者面板创建）
oauth_client_secret = ""     # 应用密钥；公共客户端留空（自动走 PKCE）
oauth_authorize_url = "https://maimai.lxns.net/oauth/authorize"
oauth_redirect_uri = ""      # 留空 = OOB（授权码直接显示，bot 推荐）
oauth_scope = "read_player write_player read_user_profile"
enable_developer_api = false # 好友码查询模式（查分器开发者）
developer_api_key = ""       # 落雪开发者 API 密钥

[render]
device_scale_factor = 2.0    # 渲染缩放（2.0 高清 / 1.0 标准）
image_timeout_ms = 15000
browser_executable = ""      # Playwright 回退时的浏览器路径（留空自动查找）
headless = true
no_sandbox = true
```

## 命令列表

### 基础命令（`/mai`）

| 命令 | 说明 | 输出 |
|------|------|------|
| `/mai help` | 命令总览 | 图片 |
| `/mai song <关键词/ID>` | 搜索曲目，ID 直接查看详情（封面 + 落雪补全） | 图片 |
| `/mai today` | 今日运势 — 宜忌与推荐歌曲 | 图片 |
| `/mai maidle` | 开始 Maidle 猜歌游戏 | 图片 |
| `/mai maidle guess <ID/名称>` | 猜歌 — 提交猜测 | 图片 |
| `/mai maidle answer` | 猜歌 — 查看答案 | 图片 |
| `/mai maidle help` | 猜歌规则说明 | 图片 |
| `/mai charts` | 全谱面难度分布统计 | 文本（待图片化） |
| `/mai status` | 双服状态检测（水鱼 + 落雪） | 图片 |
| `/mai pick <A> <B> [C] [D]` | 随机帮你选一个 | 图片 |
| `/mai alias add/del/list` | 本地别称管理 | 文本 |

### 成绩查询（`/mai`）

| 命令 | 说明 | 输出 |
|------|------|------|
| `/mai b50 [用户] [--lxns\|--df]` | 生成 Best 50 成绩图片（最完善的渲染）；`--lxns`/`--df` 强制指定数据源 | 图片 |
| `/mai my [--lxns\|--df]` | 个人成绩摘要（需绑定 Token）；`--lxns`/`--df` 强制指定数据源 | 图片 |
| `/mai bind <Token>` | 绑定水鱼成绩导入 Token | — |
| `/mai unbind` | 解除绑定 | — |

> **强制数据源**：默认自动选源（绑定落雪 → 开发者好友码 → 水鱼）。在命令后加
> `--lxns` 强制用落雪（未绑定/未配置时会提示），加 `--df` 强制用水鱼
> （需绑定水鱼 Token 或提供用户名）。例：
> `/mai b50 --lxns 430854389938390`、`/mai my --df`。

### 落雪账号（`/mai lxns`）

> 落雪独有能力（水鱼无对应功能）。绑定落雪后，`/mai b50`、`/mai my` 也会自动
> 切换为落雪数据源；未配置/未绑定时这些命令给出引导提示，不影响水鱼功能。

| 命令 | 说明 | 输出 |
|------|------|------|
| `/mai lxns bind` | OAuth 授权绑定（私聊发送授权链接 → 授权码回填） | — |
| `/mai lxns bind token <个人API密钥>` | 个人 API 密钥绑定（快速方式） | — |
| `/mai lxns bind code <授权码>` | 用授权码完成 OAuth 绑定 | — |
| `/mai lxns unbind` / `status` | 解绑 / 查看状态 | 文本 |
| `/mai lxns heatmap` | 成绩上传热力图 | 图片 |
| `/mai lxns trend [版本号]` | DX Rating 趋势 | 图片 |
| `/mai lxns history <曲名/ID>` | 单曲游玩历史（自动遍历全部难度） | 图片 |
| `/mai lxns rank <曲名/ID>` | 单曲分数排行 | 图片 |
| `/mai lxns year [年份]` | 年度回顾 | 图片 |
| `/mai lxns collections` | 收藏品（称号/头像/姓名框/背景） | 图片 |
| `/mai lxns upload` | 水鱼成绩同步到落雪（缺失补齐 / 更高覆盖 / 相同跳过） | 文本 |
| `/mai lxns comment list <曲名>` | 曲目评论（落雪服务端暂未开放该接口） | 文本 |

### AI Tool

| 工具名 | 功能 |
|--------|------|
| `search_mai_songs` | 按名称/艺术家/ID/别称搜索曲库 |

## 数据存储

数据保存在 `data/plugins/deepseek-v4-pro.maimaidx-prober/`（插件运行时标准路径）：

| 文件 | 内容 |
|------|------|
| `bindings.json` | 水鱼 Token 绑定（明文，注意权限；旧插件目录数据会自动迁移） |
| `aliases.json` | 本地别称 |
| `lxns_bindings.json` | 落雪绑定（OAuth 令牌 / 个人密钥，明文，注意权限） |
| 曲库缓存 | 内存 TTL 缓存（水鱼曲库/谱面统计/落雪曲库） |
| Maidle 会话 | 内存会话，15 分钟过期，后台定时清理 |

## 已知问题

1. **半成品状态**：除 B50 外，其余图片渲染已完成风格统一但细节/装饰待完善；
   `/mai charts`、`/mai alias *` 等仍为文本输出。
2. **B15 不满 15 首时最后一行不渲染**：B50 按「有多少歌排多少行」渲染，
   新版本歌曲不足 15 首时 BEST 15 区域会缺行（暂无占位卡补齐，计划中）。
3. **落雪评论接口未开放**：`/mai lxns comment` 相关端点实测全部 404，命令保留并
   给出友好提示，待落雪服务端开放后可用。
4. **版本号接口无返回**：落雪玩家/成绩接口不含版本字段，B50 头部版本图标
   由 `[plugin].game_version` 配置（默认 25500）。
5. **水鱼无头像/段位数据**：水鱼来源的 B50 不显示头像（回退首字母圆形）与
   阶级/段位徽章。
6. **lxns 封面 CDN 反爬**：`assets.lxns.net` 对部分客户端返回 HTTP 200 的
   JS 挑战页，封面已按图片内容校验并回退水鱼；B50 主用水鱼 CDN，小概率仍可能缺图。
7. **首次渲染较慢**：Playwright 回退模式下首次启动浏览器需 10-30 秒；宿主渲染
   模式由宿主预热。

## 常见问题 (FAQ)

### Q1: `/mai today` 图片里没有曲绘

封面按图片内容校验，落雪被反爬时自动回退水鱼。若仍缺失，多为该曲两个 CDN
都没有封面，卡片会显示「曲绘缺失」占位。

### Q2: `/mai b50` 长时间无响应

多为曲库未缓存、浏览器首次启动或目标用户隐私设置导致。稍等 30 秒重试；
可检查 `config.toml` 的 `base_url` 与 `[plugin_runtime.render]` 配置。

### Q3: 图片模糊

确认 `[render].device_scale_factor = 2.0`；若使用宿主渲染，此为默认值。

### Q4: 容器里图片渲染失败

优先启用 MaiBot 宿主 `plugin_runtime.render`（自动下载 Chromium）；若走插件内置
Playwright，请用 `python install_deps.py` 安装并保持 `no_sandbox = true`。

### Q5: Token 提示失效

在 diving-fish 网站重新生成 Token 后执行 `/mai bind <新Token>`。

### Q6: `/mai lxns` 相关命令没了？

v2.0 曾移除需要落雪账号认证的命令；**v3.0 已全部回归**：
`/mai lxns bind`（OAuth / 个人密钥）绑定后即可使用 heatmap / trend / history /
rank / year / collections / upload 等命令，`/mai b50`、`/mai my` 也会自动切换到
落雪数据源。未配置落雪时这些命令会给出引导提示，水鱼功能不受影响。

### Q7: B50 的 BEST 15 为什么少一行？

你的账号新版本歌曲不足 15 首时，渲染按实际数量排行（每行 5 张）。计划中会加入
占位卡补齐网格，当前版本以实际成绩数量为准。

## 卸载方式

1. 在 MaiBot WebUI 中禁用插件。
2. 删除插件目录（会清除 `bindings.json`、`aliases.json`、`config.toml`，请先备份）。
3. 可选：`python -m playwright uninstall chromium`。

## 安全说明

- 水鱼 Import-Token 与落雪令牌/个人密钥以明文存储在本地 JSON，持有者可读写你的
  成绩数据；绑定后建议撤回聊天中的 Token 消息，不要分享 Token。
- 插件目录请限制文件系统权限。
- 所有 API 通信均为 HTTPS。

## 免责声明

1. 本插件按「现状」提供，不提供任何明示或暗示的担保。
2. 使用本插件的行为完全出于用户自愿，由此产生的任何后果由用户自行承担。
3. 本插件连接由第三方维护的 diving-fish 和 lxns 服务，不对其可用性或安全性负责。
4. 图片渲染依赖浏览器环境，在精简容器或受限沙盒中可能无法正常启动。

安装并使用本插件即表示您已阅读、理解并同意上述说明。

---

## 后续计划 (Roadmap)

> 以下为规划中的内容，按优先级排列；不承诺完成时间。

### 近期待办（打磨当前功能）

- **B50 网格占位**：BEST 35 / BEST 15 不满时以「未游玩」占位卡补齐网格，
  保证版面始终完整（对齐官方效果图）；
- **其余渲染器细节与装饰**：my / song / today / heatmap / trend / history /
  rank / year / collections / pick / status 的布局细节、分区装饰、图标点缀；
- **图片化剩余文本命令**：`/mai charts`（谱面难度分布）、`/mai alias *`（别称管理）、
  `/mai lxns status`（绑定状态）；
- **B50 剩余数据入图**：卡片 Lv. 难度文字、单曲游玩时间；
- **收藏品图片输出**：称号/头像/姓名框/背景使用落雪资源 CDN
  （`assets2.lxns.net/maimai/{trophy|plate|icon|frame}/{id}.png`）展示实物图；
- **年度回顾增强**：参照前端 `YearInReviewProps` 加入
  rate_distribute / full_combo_distribute / rating_growth / most_played_genres 等
  维度；
- **评论功能**：等待落雪服务端开放评论接口后启用 `/mai lxns comment *`；
- **水鱼上传接口调研**：水鱼目前无公开上传接口，`/mai lxns upload` 保持
  「水鱼 → 落雪」单向同步（反过来需等待水鱼开放）。

### 中二节奏（chunithm）支持

落雪 API 已提供完整的中二节奏接口（玩家/成绩/收藏品/资源 CDN），纳入本插件需要：

- 命令体系扩展为双游戏命名（如 `/mai` 与 `/chu`）；
- 新增中二数据归一化与渲染（Rating 构成、Clear/FC/Chain 枚举与舞萌不同）；
- 绑定存储增加游戏维度，复用同一套 OAuth / 个人 token；
- 曲库缓存、封面服务、资源 CDN 按游戏分流。

### 多音游插件聚合（远期设想）

规划将 [ongeki_prober](https://github.com/DeepSeek-V4-Pro/ongeki_prober)（音击谱面查询）
与 [phigros-b30-plugin-main](https://github.com/DeepSeek-V4-Pro/phigros-b30-plugin-main)
（Phigros B30 查分）的功能聚合进一个「音游查分全家桶」插件：

- 统一命令前缀、共享渲染 / 存储 / HTTP 客户端基建，按游戏模块化注册；
- 每个游戏独立开关（`config.toml` 分节），未启用的游戏不加载对应命令；
- 该计划大概率遥遥无期，仅作方向性备忘。

---

**插件版本**: 3.0.0  
**插件 ID**: `deepseek-v4-pro.maimaidx-prober`  
**更新日志**: [CHANGELOG.md](CHANGELOG.md)
