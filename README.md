# MaiMai DX 双源查分器插件

连接 [diving-fish（水鱼）](https://www.diving-fish.com) 与 [lxns](https://maimai.lxns.net) 双查分器 API，在 MaiBot 中查询舞萌 DX 的成绩与曲目数据。

**注意**：落雪查分目前仅用做数据补充，还有一堆bug没有解决，请等待后续版本

> **水鱼 API**: [https://www.diving-fish.com/api/maimaidxprober](https://www.diving-fish.com/api/maimaidxprober)  
> **lxns API**: [https://maimai.lxns.net/api/v0](https://maimai.lxns.net)  
> **插件版本**: 1.1.0 | **插件 ID**: `deepseek-v4-pro.maimaidx-prober`

---

## 目录

1. [架构说明](#一架构说明)
2. [依赖清单](#二依赖清单)
3. [安装方式](#三安装方式)
4. [配置说明](#四配置说明)
5. [命令列表](#五命令列表)
6. [使用流程](#六使用流程)
7. [数据存储](#七数据存储)
8. [已知问题](#八已知问题)
9. [卸载方式](#九卸载方式)
10. [安全说明](#十安全说明)
11. [免责声明](#十一免责声明)
12. [常见问题 (FAQ)](#十二常见问题-faq)

---

## 一、架构说明

### 数据流

```
用户 → MaiBot → 本插件 ─┬→ DivingFishApiClient (diving-fish API) → B50/成绩/猜歌/运势
                        │
                        └→ LxnsApiClient (lxns API) → 曲目详情/别名/收藏品
                              │
                              ├─ 公开端点（无需认证）
                              └─ 认证端点（需 JWT Token，暂不可用）

封面下载: lxns assets.lxns.net (优先) → diving-fish.com/covers (兜底)
曲目数据: diving-fish 基础数据 + lxns 补充增强（分类名/版本名/谱师/定数注音/note分布）
```

### 命令体系（三层）

| 前缀 | 子系统 | 说明 |
|------|--------|------|
| `/mai` | 基础功能 | 曲目搜索、运势、猜歌、统计、随机选择、双服状态 |
| `/mai df` | 水鱼查分 | B50、个人成绩、Token 绑定 |
| `/mai lxns` | lxns 查分 | 曲目详情增强、别名导入、收藏品（个人数据暂不可用） |

### 核心组件

| 组件 | 类型 | 功能 |
|------|------|------|
| `MaiMaiDXPlugin` | Plugin | 插件主类，管理双源配置、缓存、浏览器实例和生命周期 |
| `DivingFishApiClient` | Client | 异步 HTTP 客户端，封装 diving-fish 全部 API |
| `LxnsApiClient` | Client | 异步 HTTP 客户端，封装 lxns 全部 API |
| `AliasStore` | Store | 本地别称管理，JSON 文件 + 反序索引搜索，支持 lxns 社区别名导入 |
| `BindingStore` | Store | 水鱼 Import-Token 绑定管理 |
| `LxnsBindingStore` | Store | lxns Token 绑定管理 |
| `_ensure_browser` | Browser | Playwright Chromium 单例浏览器，懒加载启动 |
| `_render_html_to_png` | Renderer | 统一的 HTML→PNG 图片渲染器 |

### 认证体系

| 查分器 | 认证方式 | 用途 |
|--------|----------|------|
| diving-fish | Import-Token Header | 成绩查询、B50、个人数据 |
| lxns (公开) | 无需认证 | 曲目详情增强、别名导入、收藏品列表 |
| lxns (个人) | JWT Bearer Token | 个人数据（热力图/趋势/年度回顾等，**暂不可用**） |

---

## 二、依赖清单

### Python 包

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| `aiohttp` | ≥3.8 | 异步 HTTP 请求 |
| `playwright` | ≥1.40 | 无头浏览器渲染图片 |

### 系统依赖

**Playwright 需要下载 Chromium 浏览器**（约 300 MB），与系统已安装的 Chrome/Edge 独立。

| 操作系统 | Chromium 缓存路径 |
|----------|-------------------|
| Windows | `%USERPROFILE%\AppData\Local\ms-playwright\` |
| macOS | `~/Library/Caches/ms-playwright/` |
| Linux | `~/.cache/ms-playwright/` |

### MaiBot 环境依赖

| 依赖 | 版本要求 |
|------|----------|
| MaiBot SDK | ≥2.0.0, <2.99.99 |
| MaiBot 主程序 | ≥1.0.0, <1.99.99 |

插件声明的 SDK **capabilities**：`send.text, send.forward, send.image, config.get`

---

## 三、安装方式

### 步骤 1：复制插件文件

将 `maimaidx_prober` 目录放入 MaiBot 的 `plugins/` 目录下：

```bash
# Linux / macOS
cp -r maimaidx_prober/ /path/to/MaiBot/plugins/

# Windows (PowerShell)
Copy-Item -Recurse maimaidx_prober/ C:\path\to\MaiBot\plugins\
```

最终目录结构：

```
plugins/
└── maimaidx_prober/
    ├── _manifest.json
    ├── config.toml
    ├── plugin.py
    ├── lxns_client.py
    └── README.md
```

插件初次运行时会在插件目录下自动创建：

```
plugins/maimaidx_prober/
    ├── bindings.json       (水鱼 Token 绑定数据)
    ├── lxns_bindings.json  (lxns Token 绑定数据)
    └── aliases.json        (本地别称数据)
```

### 步骤 2：安装 Python 依赖

```bash
pip install aiohttp playwright
# 或
uv pip install aiohttp playwright
```

### 步骤 3：安装 Playwright Chromium 浏览器

```bash
python -m playwright install chromium
```

> 首次安装需下载约 **300 MB**。如果只使用文本类命令可跳过此步，但大部分核心功能将不可用。

### 步骤 4：启用插件

编辑 `plugins/maimaidx_prober/config.toml`，确保 `enabled = true`：

```toml
[plugin]
enabled = true
```

### 步骤 5：验证安装

```
/mai help
```

如果收到命令总览图片，表示安装成功。

---

## 四、配置说明

```toml
[plugin]
enabled = true               # 是否启用插件
config_version = "1.1.0"     # 配置版本（请勿手动修改）

[server]
base_url = "https://www.diving-fish.com/api/maimaidxprober"
                             # 水鱼 API 地址
request_timeout = 30         # HTTP 请求超时（秒）
music_cache_ttl = 300        # 曲库内存缓存时间（秒）

[lxns]
enable = true                # 是否启用 lxns API
base_url = "https://maimai.lxns.net/api/v0"
                             # lxns API 地址
asset_url = "https://assets.lxns.net"
                             # lxns 资源 CDN 地址
request_timeout = 30         # HTTP 请求超时（秒）
music_cache_ttl = 300        # lxns 曲库缓存时间（秒）
```

---

## 五、命令列表

### 基础命令 (`/mai`)

| 命令 | 说明 | 认证 |
|------|------|:---:|
| `/mai help` | 命令总览（三系统） | - |
| `/mai song <关键词/ID>` | 搜索曲目，ID 直接查看详情（含封面） | - |
| `/mai today` | 今日运势 — 查看宜忌与推荐歌曲 | - |
| `/mai maidle` | 开始 Maidle 猜歌游戏 | - |
| `/mai maidle guess <ID/名称>` | 猜歌游戏 — 提交猜测 | - |
| `/mai maidle answer` | 猜歌游戏 — 查看答案 | - |
| `/mai maidle help` | Maidle 猜歌游戏规则说明 | - |
| `/mai charts` | 全谱面难度分布统计（FC 率、AP 率） | - |
| `/mai status` | 服务器状态检测（diving-fish + lxns 双服） | - |
| `/mai pick <A> <B> [C] [D]` | 随机帮你选一个（2~4 选项） | - |
| `/mai alias add <ID> <名称>` | 为歌曲添加本地别称 | - |
| `/mai alias del <ID> <名称>` | 删除歌曲别称 | - |
| `/mai alias list <ID>` | 查看歌曲所有别称 | - |

### 水鱼查分 (`/mai df`)

| 命令 | 说明 | 认证 |
|------|------|:---:|
| `/mai df help` | 水鱼命令帮助 | - |
| `/mai df b50 [用户名/QQ]` | 生成 Best 50 成绩图片 | - |
| `/mai df my` | 查看个人成绩摘要（含难度分布、Top 10） | Token |
| `/mai df bind <Token>` | 绑定水鱼查分器的成绩导入 Token | - |
| `/mai df unbind` | 解除当前绑定 | - |

### lxns 查分 (`/mai lxns`) — 公开可用

| 命令 | 说明 | 认证 |
|------|------|:---:|
| `/mai lxns help` | lxns 命令帮助 | - |
| `/mai lxns status` | lxns 服务器状态 | - |
| `/mai lxns song <ID>` | lxns 增强版曲目详情（谱师/注音/Buddy/note分布） | - |
| `/mai lxns alias import` | 从 lxns 导入社区别名到本地 | - |
| `/mai lxns bind <Token>` | 绑定 lxns Token | - |
| `/mai lxns unbind` | 解除 lxns 绑定 | - |

### lxns 查分 (`/mai lxns`) — 暂不可用（需 JWT Token）

| 命令 | 说明 | 原因 |
|------|------|------|
| `/mai lxns b50` | lxns 版 Best 50（含 FS/累计分数） | 个人密钥无 `/user/*` 权限 |
| `/mai lxns my` | lxns 个人资料与收藏品 | 同上 |
| `/mai lxns rank <ID>` | 单曲全球排行榜 | 同上 |
| `/mai lxns history <ID>` | 单曲成绩进步轨迹 | 同上 |
| `/mai lxns comment <ID>` | 查看歌曲评论区 | 同上 |
| `/mai lxns heatmap` | 游玩热力图 | 同上 |
| `/mai lxns trend [版本]` | Rating 趋势 | 同上 |
| `/mai lxns year [年份]` | 年度回顾 | 同上 |
| `/mai lxns collections <种类>` | 收藏品列表与详情 | 同上 |

### AI Tool（模型可调用）

| Tool 名称 | 功能 |
|-----------|------|
| `search_mai_songs` | 按名称/艺术家/ID/别称搜索曲库 |

---

## 六、使用流程

### 1. 获取水鱼 Import-Token

1. 登录 [diving-fish 查分器](https://www.diving-fish.com)
2. 进入 personal page（个人中心）
3. 复制「成绩导入 Token」

### 2. 绑定水鱼 Token

```
/mai df bind <你的Token>
```

绑定成功后可使用 `/mai df my` 查看个人成绩。

### 3. 日常使用

```
/mai df b50              # 查看自己的 Best 50 图片
/mai df b50 某用户QQ      # 查看他人的 B50
/mai song 11115           # 搜索曲目详情（含封面+lxns增强数据）
/mai song 音楽を辞めた     # 模糊搜索
/mai today                # 查看今日运势
/mai charts               # 谱面难度统计
/mai status               # 双服状态检测
/mai pick 吃饭 睡觉 打机   # 帮你做决定
```

### 4. 别称使用

```
/mai alias add 11115 yorushika     # 添加别称
/mai song yorushika                # 使用别称搜索
/mai lxns alias import             # 从 lxns 导入社区别名
```

### 5. Maidle 猜歌

```
/mai maidle                # 开始游戏
/mai maidle guess 11115    # 按歌曲 ID 猜测
/mai maidle guess 音楽      # 按曲名/关键词猜测
/mai maidle answer         # 放弃并查看答案
```

---

## 七、数据存储

所有用户数据存储在插件目录内，不涉及 MaiBot 主程序或其他插件。

| 文件 | 格式 | 内容 | 写入方式 |
|------|------|------|----------|
| `bindings.json` | JSON | `{user_id: {username, import_token, bound_at}}` | 原子写入 |
| `lxns_bindings.json` | JSON | `{user_id: {token, username, auth_method, bound_at}}` | 原子写入 |
| `aliases.json` | JSON | `{song_id: ["别称1", "别称2"]}` | 原子写入 |
| 水鱼曲库缓存 | 内存 | diving-fish `/music_data` 完整响应 | TTL 5 分钟后过期 |
| 水鱼谱面统计缓存 | 内存 | diving-fish `/chart_stats` 响应 | TTL 过期后重新获取 |
| lxns 曲库缓存 | 内存 | lxns `/maimai/song/list` 响应 | TTL 5 分钟后过期 |
| Maidle 会话 | 内存 | 猜歌游戏进行中的会话状态 | 后台每 60s 清理过期会话 |

---

## 八、已知问题

### 1. lxns 个人数据功能暂不可用

**现象**：`/mai lxns b50`, `/mai lxns my`, `/mai lxns heatmap` 等个人数据命令返回"未经授权"。

**原因**：lxns 的「个人密钥」与网站登录的 JWT Token 是不同的凭据。个人密钥的描述明确指出：

> - 该密钥并不等同于开发者 API 密钥
> - 该密钥对你的查分器用户数据没有访问权限
> - 该密钥对你查分器账号绑定的游戏数据拥有完全访问权限

经过全面测试（Bearer / Import-Token / X-API-Key / URL 参数等 8 种认证方式），个人密钥无法通过 lxns 的 `/user/*` REST API 认证。lxns 网站前端使用的是浏览器登录后的 JWT Token（`localStorage.token`），该 Token 携带 session 信息，与个人密钥不同。

**影响范围**：所有需要 lxns 认证的命令（b50、my、heatmap、trend、year、rank、history、comment、collections）均不可用。

**不影响**：公开端点（曲目列表、别名列表、收藏品列表）无需认证，功能正常。

**可能的解决方案**：从浏览器 DevTools → Application → Local Storage 复制 `token` 值绑定，但该 Token 有过期时间且需要配合 Cookie 使用，Bot 端维护成本高。等待 lxns 官方提供专门的 Bot/API 认证方案。

### 2. lxns 曲目详情接口返回 404

**现象**：`GET /maimai/song/{id}?version=25000` 返回 `resource not found`。

**影响**：lxns 增强版曲目详情暂时使用 diving-fish 基础数据 + lxns 曲库缓存做本地补充，不能实时从 lxns API 获取谱面详情。

**可能原因**：lxns 歌曲详情接口可能需要额外参数或不同路径。

### 3. Playwright 首次启动较慢

**现象**：首次执行图片渲染命令时响应较慢（10-30 秒）。

**原因**：Chromium 浏览器以懒加载方式启动，首次需要初始化浏览器进程。后续命令会复用已启动的浏览器实例。

### 4. 封面图片可能缺失

**现象**：部分歌曲在 B50/曲目详情图片中无封面显示。

**原因**：封面优先从 lxns CDN 获取，失败后回退 diving-fish CDN。两个 CDN 使用不同的文件名映射（lxns: `id % 10000`，diving-fish: `id.zfill(5)`），部分歌曲封面在两边都可能不存在。

### 5. lxns 别名投票功能暂缺

`/mai lxns alias vote` 命令在早期规划中但尚未实现 handler，后续版本补充。

---

## 九、卸载方式

**步骤 1**：在 MaiBot WebUI 中禁用（unload）本插件。

**步骤 2**：删除插件目录：

```bash
# Linux / macOS
rm -rf plugins/maimaidx_prober/

# Windows (PowerShell)
Remove-Item -Recurse -Force C:\path\to\MaiBot\plugins\maimaidx_prober\
```

> 删除插件目录会一并清除 `bindings.json`、`lxns_bindings.json`、`aliases.json` 和 `config.toml`。如需保留数据请先备份。

**步骤 3**（可选）：卸载 Chromium 和 Python 包：

```bash
python -m playwright uninstall chromium
pip uninstall playwright
```

> 如果其他 MaiBot 插件也依赖这些包，请勿卸载。

---

## 十、安全说明

### Import-Token 的性质（水鱼）

持有此 Token 可以读取和写入成绩数据，但不能修改账号密码。Token 以明文存储在 `bindings.json` 中。

### lxns Token 的性质

个人密钥或 JWT Token 以明文存储在 `lxns_bindings.json` 中。个人密钥对游戏数据有完全访问权限且无视隐私设置。

### 安全建议

| 建议 | 说明 |
|------|------|
| 绑定后撤回消息 | Token 会出现在聊天记录中 |
| 定期刷新 Token | 在对应网站重新生成后重新绑定 |
| 限制文件访问 | 确保 MaiBot 插件目录权限合理 |
| 不要分享 Token | Token 等同于数据访问权限 |
| 使用后删除 | 不再使用时解绑并删除对应 JSON 文件 |

### 网络传输

- 本插件与两个 API 之间的所有通信均使用 **HTTPS** 加密
- 封面图片下载同样通过 HTTPS
- 不经过任何第三方代理或中转服务

---

## 十一、免责声明

1. 本插件按「现状」提供，不提供任何明示或暗示的担保。
2. 使用本插件的行为完全出于用户自愿，由此产生的任何后果由用户自行承担。
3. 本插件连接由第三方维护的 diving-fish 和 lxns 服务，不对其可用性或安全性负责。
4. Token 的安全性依赖于所在操作系统的文件权限和运行环境。
5. 图片渲染依赖 Playwright/Chromium，在某些精简 Docker 镜像或受限沙盒环境中可能无法正常启动。

安装并使用本插件即表示您已阅读、理解并同意上述安全说明和免责声明。

---

## 十二、常见问题 (FAQ)

### Q1: 发送 `/mai df b50` 后长时间无响应

**可能原因**：曲库数据未缓存、Playwright 未安装、网络问题、目标用户不存在或设置隐私。

**解决方式**：稍等 30 秒后重试，检查 `config.toml` 中的 `base_url`。

### Q2: B50 图片封面没有加载

封面缺失不会影响 B50 卡片的主体数据显示。插件优先使用 lxns CDN，失败后回退 diving-fish CDN，缺失的封面会自动隐藏。

### Q3: `/mai today` 只显示文字没有图片

封面下载失败时会自动回退到文字版输出，稍后重试通常可恢复。

### Q4: `/mai lxns` 命令全部提示"未经授权"

请确认使用的是浏览器登录后的 JWT Token，而非个人密钥。详见[已知问题](#八已知问题)。

### Q5: 绑定的水鱼 Token 提示失效

在 diving-fish 网站重新生成 Token 后执行 `/mai df bind <新Token>` 重新绑定。

### Q6: Playwright 安装失败或 Chromium 无法启动

- 磁盘空间不足：清理后重试
- Linux 缺少库：`python -m playwright install --with-deps chromium`
- Docker 沙盒：以 `--no-sandbox` 参数启动

### Q7: 可以使用自己的 diving-fish 自建服务器吗

可以。修改 `config.toml` 中的 `server.base_url` 为你的自建服务器地址。

### Q8: `/mai df my` 显示的统计含义

- **总成绩数**：按 `song_id` 去重后的唯一歌曲数量
- **SD 曲目 / DX 曲目**：按歌曲类型去重统计
- **难度分布**：每首歌曲取其最佳 RA 所属的难度等级归类
- **Top 10**：RA 最高的 10 首歌曲

### Q9: 添加的别称如何迁移

别称存储在 `aliases.json` 中，可直接复制到其他安装同一插件的 MaiBot 实例。

---

**插件版本**: 1.1.0  
**插件 ID**: `deepseek-v4-pro.maimaidx-prober`  
**最后更新**: 2026-06
