# MaiMai DX 查分器插件（v3.1.0）· 用户文档

> 面向**插件使用者**（MaiBot 服主 / 群友）的安装、配置与命令说明。
> 开发者请阅读 [DEVELOPMENT.md](DEVELOPMENT.md)。

本插件连接 [diving-fish（水鱼）](https://www.diving-fish.com) 与
[lxns（落雪）](https://maimai.lxns.net) 两个舞萌 DX 查分平台，在 MaiBot 中提供
B50 成绩图、个人成绩、曲目搜索、猜歌、谱面统计、今日运势、热门/排行，以及落雪独有
的热力图、趋势、历史、排行、年度回顾、收藏品、双向成绩同步等能力。

> **插件版本**: 3.1.0 | **插件 ID**: `deepseek-v4-pro.maimaidx-prober`
> **水鱼 API**: <https://www.diving-fish.com/api/maimaidxprober>
> **lxns API**: <https://maimai.lxns.net/api/v0>

---

## 目录

1. [功能一览](#功能一览)
2. [安装](#安装)
3. [配置说明](#配置说明)
4. [落雪接入（可选）](#落雪接入可选)
5. [命令速查](#命令速查)
6. [数据存储](#数据存储)
7. [常见问题 FAQ](#常见问题-faq)
8. [已知问题](#已知问题)
9. [卸载](#卸载)
10. [安全说明](#安全说明)
11. [免责声明](#免责声明)

---

## 功能一览

- **B50 成绩图**：官方版式复刻（马卡龙渐变背景、难度配色卡片、评级/FC/FS/DX 星
  官方素材、头像、段位/阶级徽章、渐变 Rating、版本图标）；BEST 35 / BEST 15 不足时
  以「未游玩」占位卡补齐网格，卡片含 Lv 难度与单曲游玩时间。
- **个人成绩摘要**：Rating、段位、曲目数、难度分布、Top 10 成绩。
- **曲目搜索与详情**：名称/作者/ID/别称搜索，封面 + 落雪补全（分类/版本/谱师/定数）。
- **猜歌（Maidle）**：水鱼猜歌游戏，图片线索反馈。
- **谱面统计**：全谱面难度分布（均达成率 / FC / AP / 评级分布）。
- **运势 / 选一 / 服务器状态**：今日宜忌、随机选择、双服健康检查。
- **水鱼公共数据**：热门歌曲、DX Rating 排行榜、按版本查询成绩。
- **落雪账号能力**：绑定（OAuth / 个人密钥）后解锁热力图、趋势、历史、排行、
  年度回顾、收藏品实物图、玩家资料卡、AP50、按 QQ 查玩家。
- **成绩双向同步**：水鱼 → 落雪（`/mai lxns upload`）、落雪 → 水鱼（`/mai df upload`），
  均采用**只升不降**策略。
- **全部交互命令图片化**：统一 B50 同风格浅色面板。

## 安装

### 环境要求

- MaiBot ≥ 1.0.0（建议 1.1.x），插件运行时（`plugin_runtime`）已启用；
- Python ≥ 3.12；
- 图片渲染建议启用 MaiBot 宿主 `plugin_runtime.render`（自动管理 Chromium）；
  否则需要插件内置 Playwright 回退。

### 步骤 1：复制插件

```bash
# Linux / macOS
cp -r maimaidx_prober/ /path/to/MaiBot/plugins/

# Windows (PowerShell)
Copy-Item -Recurse maimaidx_prober\ C:\path\to\MaiBot\plugins\
```

### 步骤 2：安装依赖

```bash
python install_deps.py
# 或手动：pip install -r requirements.txt && python -m playwright install chromium
```

插件加载时会自检依赖；若缺失且 `config.toml` 中 `[plugin].auto_install_deps = true`，
会自动执行安装（容器内需要网络与磁盘空间）。

### 步骤 3：启用并验证

1. 编辑 `plugins/maimaidx_prober/config.toml`，确认 `[plugin].enabled = true`；
2. 私聊或群里发送 `/mai help`，收到命令总览图片即安装成功。

### 容器 / 1Panel 部署

容器重建会丢失手动安装的 Python 包，推荐：

- **方式 A（推荐）**：参考 [Dockerfile.example](Dockerfile.example)，构建阶段完成
  `pip install` 与 `playwright install chromium`，并启用宿主渲染
  （`plugin_runtime.render.auto_download_chromium = true`）；
- **方式 B**：设置 `auto_install_deps = true`，由插件启动时自检安装。

## 配置说明

配置文件为插件目录下的 `config.toml`：

```toml
[plugin]
enabled = true               # 是否启用插件
config_version = "3.1.0"     # 配置版本（请勿手动修改）
auto_install_deps = false    # 依赖缺失时自动安装
game_version = 25500         # B50 头部版本图标（25500=舞萌DX 2026）
developer_qq = []            # 允许使用开发者凭证的 QQ 号列表；为空则关闭全部开发者功能

[server]
base_url = "https://www.diving-fish.com/api/maimaidxprober"
request_timeout = 30
music_cache_ttl = 300
developer_token = ""         # 水鱼开发者 API 密钥（/mai plate 按版本查询用）

[lxns]
enable = true                # 是否启用落雪公开数据补全
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

## 落雪接入（可选）

落雪提供三种接入方式，**密钥不可混用**：

| 方式 | 配置 | 绑定命令 | 可用能力 |
| --- | --- | --- | --- |
| OAuth（推荐） | `[lxns].enable_oauth = true` + 应用 ID/密钥 | `/mai lxns bind`（OOB 授权码） | 全量账号能力 |
| 个人 API 密钥 | 无需配置 | `/mai lxns bind token <密钥>` | 全量账号能力（不含评论） |
| 开发者 API | `[lxns].enable_developer_api = true` + `developer_api_key` | 无需绑定，好友码直查 | 好友码查询、AP50、按 QQ 查玩家 |

### OAuth 绑定流程

1. 服主在落雪开发者面板创建 OAuth 应用，填写应用 ID / 密钥到 `[lxns]`
   （无回调地址时勾选「无回调地址」即 OOB）；
2. 用户私聊发送 `/mai lxns bind`，收到授权链接；
3. 浏览器打开链接登录授权，页面显示授权码（形如 `JVJ6-VPTM-MGHZ`）；
4. 把授权码发回：`/mai lxns bind code <授权码>`，绑定完成；
5. 解绑：`/mai lxns unbind`；查看状态：`/mai lxns status`。

### 个人 API 密钥绑定

在落雪「账号详情页」生成个人密钥，私聊 `/mai lxns bind token <密钥>` 即可。
密钥以明文存于 `lxns_bindings.json`，注意撤回聊天消息与文件权限。

### 开发者权限白名单

开发者密钥是全局凭证，只有 `[plugin].developer_qq` 白名单内的 QQ 才能触发
开发者功能（好友码查询、`/mai lxns ap50`、`/mai lxns qq`、`/mai lxns best <好友码>`、
`/mai plate`）。列表为空时这些功能全部关闭。查询他人数据受对方隐私设置
（`allow_third_party_*`）影响，关闭时返回 403；落雪资源 CDN 有频率限制。

## 命令速查

### 基础命令（`/mai`）

| 命令 | 说明 | 输出 |
|------|------|------|
| `/mai help` | 命令总览 | 图片 |
| `/mai song <关键词/ID>` | 搜索曲目；ID 直接查看详情 | 图片 |
| `/mai today` | 今日运势 — 宜忌与推荐歌曲 | 图片 |
| `/mai maidle` | 开始 Maidle 猜歌游戏 | 图片 |
| `/mai maidle guess <ID/名称>` | 猜歌 — 提交猜测 | 图片 |
| `/mai maidle answer` | 猜歌 — 查看答案 | 图片 |
| `/mai maidle help` | 猜歌规则说明 | 图片 |
| `/mai charts` | 全谱面难度分布统计 | 图片 |
| `/mai hot [N]` | 热门歌曲 TOP N（新曲/高难度加权） | 图片 |
| `/mai ranking [N]` | DX Rating 排行榜 TOP N | 图片 |
| `/mai status` | 双服状态检测（水鱼 + 落雪） | 图片 |
| `/mai pick <A> <B> [C] [D]` | 随机帮你选一个 | 图片 |
| `/mai plate <版本代号>` | 按版本查询已绑定账号成绩（需水鱼 Developer-Token） | 图片 |
| `/mai alias add <ID> <名称>` | 添加本地别称 | 文本 |
| `/mai alias del <ID> <名称>` | 删除本地别称 | 文本 |
| `/mai alias list <ID>` | 查看别称 | 图片 |
| `/mai alias import` | 从 lxns 导入社区别名 | 文本 |

### 成绩查询（`/mai`）

| 命令 | 说明 | 输出 |
|------|------|------|
| `/mai b50 [用户] [--lxns\|--df]` | Best 50 成绩图；可强制指定数据源 | 图片 |
| `/mai my [--lxns\|--df]` | 个人成绩摘要（需绑定 Token） | 图片 |
| `/mai bind <Token>` | 绑定水鱼成绩导入 Token | — |
| `/mai unbind` | 解除绑定 | — |

> **强制数据源**：默认自动选源（绑定落雪 → 开发者好友码 → 水鱼兜底）。
> `--lxns` 强制用落雪，`--df` 强制用水鱼。例：`/mai b50 --lxns 430854389938390`、
> `/mai my --df`。强制落雪需先绑定落雪；强制水鱼需绑定 Token 或提供用户名。

### 落雪账号（`/mai lxns`）

> 落雪独有能力。绑定落雪后 `/mai b50`、`/mai my` 自动切换为落雪数据源；
> 未绑定/未配置时命令给出引导提示，不影响水鱼功能。

| 命令 | 说明 | 输出 |
|------|------|------|
| `/mai lxns bind` | OAuth 授权绑定（私聊流程） | — |
| `/mai lxns bind token <个人API密钥>` | 个人 API 密钥绑定 | — |
| `/mai lxns bind code <授权码>` | 用授权码完成 OAuth 绑定 | — |
| `/mai lxns unbind` | 解除绑定 | — |
| `/mai lxns status` | 查看绑定状态与开发者权限 | 图片 |
| `/mai lxns player [好友码]` | 玩家资料卡（头像/段位/装备/同步时间） | 图片 |
| `/mai lxns heatmap` | 成绩上传热力图 | 图片 |
| `/mai lxns trend [版本号]` | DX Rating 趋势 | 图片 |
| `/mai lxns history <曲名/ID>` | 单曲游玩历史（遍历全部难度） | 图片 |
| `/mai lxns rank <曲名/ID>` | 单曲分数排行 | 图片 |
| `/mai lxns year [年份]` | 年度回顾（评级/FC/难度/常玩/Rating 成长） | 图片 |
| `/mai lxns collections` | 收藏品（称号/头像/姓名框/背景实物图） | 图片 |
| `/mai lxns best [好友码] <曲名>` | 单曲所有谱面最佳成绩 | 图片 |
| `/mai lxns upload` | 水鱼成绩同步到落雪（只升不降） | 文本 |
| `/mai df upload` | 落雪成绩同步到水鱼（反向，只升不降） | 文本 |
| `/mai lxns ap50 <好友码>` | All Perfect 50（开发者模式） | 图片 |
| `/mai lxns qq <QQ号>` | 按 QQ 查玩家资料（开发者模式） | 图片 |
| `/mai lxns comment list/post/like` | 曲目评论（落雪服务端暂未开放） | 文本 |

### AI 工具

| 工具名 | 功能 |
|--------|------|
| `search_mai_songs` | 按名称/艺术家/ID/别称搜索舞萌 DX 曲库 |

## 数据存储

数据保存在 `data/plugins/deepseek-v4-pro.maimaidx-prober/`（插件运行时标准路径）：

| 文件 | 内容 |
|------|------|
| `bindings.json` | 水鱼 Import-Token 绑定（明文，注意权限） |
| `lxns_bindings.json` | 落雪绑定（OAuth 令牌 / 个人密钥，明文，注意权限） |
| `aliases.json` | 本地别称 |
| 曲库缓存 | 内存 TTL 缓存（水鱼曲库/谱面统计/落雪曲库，ETag/304 增量） |
| Maidle 会话 | 内存会话，15 分钟过期，后台定时清理 |

旧插件目录（插件根目录）下的 `bindings.json` / `aliases.json` 会在首次加载时自动迁移。

## 常见问题 FAQ

### Q1: `/mai today` 图片里没有曲绘

封面按图片内容校验，落雪 CDN 被反爬时自动回退水鱼。若仍缺失，多为两个 CDN 都没有
该曲封面，卡片显示「曲绘缺失」占位。

### Q2: `/mai b50` 长时间无响应

多为曲库未缓存、浏览器首次启动或目标用户隐私设置导致。稍等 30 秒重试；可检查
`config.toml` 的 `base_url` 与 MaiBot `[plugin_runtime.render]` 配置。

### Q3: 图片模糊

确认 `[render].device_scale_factor = 2.0`；宿主渲染默认为 2.0。

### Q4: 容器里图片渲染失败

优先启用宿主 `plugin_runtime.render`（自动下载 Chromium）；若走插件内置 Playwright，
请运行 `python install_deps.py` 并保持 `no_sandbox = true`。

### Q5: Token 提示失效

在 diving-fish 网站重新生成 Token 后执行 `/mai bind <新Token>`。

### Q6: 提示"开发者功能仅限授权 QQ 使用"？

开发者功能受 `[plugin].developer_qq` 白名单限制，请联系服主把 QQ 加入白名单；
列表为空时开发者功能全部关闭。

### Q7: B50 的 BEST 15 为什么少一行？

不会少行。BEST 35 / BEST 15 不足时以「未游玩」占位卡补齐网格（恒为 7 行 + 3 行）；
若某分区完全没有成绩，则该区整片显示占位卡。

### Q8: 落雪 / 水鱼数据不一样，以哪个为准？

自动选源时优先落雪（已绑定）→ 开发者好友码 → 水鱼兜底；两源数据都可能滞后，
如想固定数据源可用 `--lxns` / `--df` 强制指定。

## 已知问题

1. **渲染打磨中**：各面板布局细节与装饰仍在完善（不影响使用）。
2. **落雪评论接口未开放**：`/mai lxns comment *` 实测服务端 404，命令保留并友好提示。
3. **版本字段缺失**：落雪成绩接口不含版本字段，B50 头部版本图标由
   `[plugin].game_version` 配置（默认 25500）。
4. **水鱼无头像/段位数据**：水鱼来源的 B50 回退首字母头像，不显示阶级/段位徽章。
5. **lxns 资源 CDN 反爬**：封面/头像/收藏品图已改用 `!webp` 后缀规避 WAF
   挑战页（按图片内容校验），极小概率仍可能缺图并回退水鱼。
6. **首次渲染较慢**：Playwright 回退模式首次启动浏览器需 10-30 秒；宿主渲染由宿主预热。

## 卸载

1. 在 MaiBot WebUI 中禁用插件；
2. 删除插件目录（会同时清除 `bindings.json`、`aliases.json`、`config.toml`，先备份）；
3. 可选：`python -m playwright uninstall chromium`。

## 安全说明

本插件会**在本机收集并保存以下密钥**（均为你主动提供，用于查询/同步成绩）：

| 密钥 | 存放位置 | 用途 | 吊销方式 |
| --- | --- | --- | --- |
| 水鱼 Import-Token | `bindings.json` | 读取 / 上传水鱼成绩 | 水鱼「编辑个人资料」重新生成 |
| 落雪个人 API 密钥 | `lxns_bindings.json` | 读取 / 上传落雪成绩 | 落雪「账号详情页」重新生成 |
| 落雪 OAuth 令牌（access / refresh） | `lxns_bindings.json` | 以账号身份访问落雪 | 落雪「已授权应用」撤销授权 |
| 落雪开发者密钥（全局） | `config.toml` | 好友码 / AP50 / 按 QQ 查询 | 落雪开发者面板重置 |
| 水鱼 Developer-Token（全局） | `config.toml` | `/mai plate` 按版本查询 | 水鱼开发者面板重置 |

安全要点：

1. **明文存储**：上述密钥以明文 JSON/TOML 保存在服务器本机，持有插件目录访问权的人
   即可读写你的成绩数据；请严格限制插件目录与
   `data/plugins/deepseek-v4-pro.maimaidx-prober/` 的文件系统权限；
2. **不要在群聊发送密钥**：绑定类命令请在私聊执行，绑定后立即撤回含密钥/授权码的
   消息；授权链接同样不要转发（10 分钟有效）；
3. **日志不记录密钥**：插件不会把令牌写入日志或错误回执；若你在日志中看到密钥，
   请立即到对应平台吊销并重新绑定；
4. **开发者凭证受白名单保护**：`[plugin].developer_qq` 为空时开发者功能全部关闭；
   白名单只拦截 bot 命令入口，密钥文件本身的访问仍依赖文件权限；
5. **HTTPS 与轮换**：所有 API 通信均为 HTTPS，但第三方平台无法保证 100% 安全，
   建议定期轮换密钥、仅在需要时绑定；
6. **上传命令会写数据**：`/mai lxns upload`、`/mai df upload` 会修改你绑定账号的
   成绩（只升不降），执行前请确认绑定账号正确；
7. **备份与卸载**：删除插件目录会同时删除密钥文件，卸载前请先备份；仓库内
   `config.toml` 为不含密钥的模板，密钥不会随插件分发。

## 免责声明

1. 本插件按「现状」提供，不提供任何明示或暗示的担保；
2. **密钥收集说明**：为查询成绩，本插件会在使用者本机保存使用者主动提供的各类
   密钥（详见「安全说明」）。密钥不会上传至插件仓库或任何插件作者服务器；
   使用者应对密钥的保管、使用与泄露风险自行负责；
3. 使用本插件完全出于用户自愿，因使用本插件产生的任何后果（包括但不限于成绩数据
   错误、账号异常、密钥泄露导致的损失）由使用者自行承担；
4. 本插件连接由第三方维护的 diving-fish 与 lxns 服务，不对其可用性、数据准确性、
   隐私与安全性负责；第三方平台可能随时变更接口、关闭功能或停止服务；
5. 图片渲染依赖浏览器环境，在精简容器、受限沙盒或缺失系统库的环境中可能无法
   正常启动或输出异常；
6. 使用者应遵守所在国家/地区法律法规以及所接入平台（MaiBot、diving-fish、lxns）
   的服务条款；因违规使用产生的责任由使用者自行承担；
7. 插件作者不对因使用或无法使用本插件造成的直接、间接、偶然或后果性损害承担
   责任，包括但不限于数据丢失、成绩损坏、服务中断。

安装并使用本插件即表示您已阅读、理解并同意上述全部说明。

---

**插件版本**: 3.1.0  
**插件 ID**: `deepseek-v4-pro.maimaidx-prober`  
**更新日志**: [CHANGELOG.md](CHANGELOG.md)  
**开发者文档**: [DEVELOPMENT.md](DEVELOPMENT.md)
