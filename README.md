# MaiMai DX 查分器插件

连接 [diving-fish（水鱼）查分器](https://www.diving-fish.com) API，在 MaiBot 中查询舞萌 DX 的成绩数据。支持 B50 图片生成、曲目搜索（含本地别称）、猜歌游戏、谱面统计、今日运势与个人成绩管理。

> **API 来源**: [https://www.diving-fish.com/api/maimaidxprober](https://www.diving-fish.com/api/maimaidxprober)  
> **官方文档**: [https://maimai.diving-fish.com/manual/docs/developer/zh-api-document/](https://maimai.diving-fish.com/manual/docs/developer/zh-api-document/)  
> **后端仓库**: [maimaidx-prober](https://github.com/Diving-Fish/maimaidx-prober)

---

## 目录

1. [架构说明](#一架构说明)
2. [依赖清单](#二依赖清单)
3. [安装方式](#三安装方式)
4. [配置说明](#四配置说明)
5. [命令列表](#五命令列表)
6. [使用流程](#六使用流程)
7. [数据存储](#七数据存储)
8. [卸载方式](#八卸载方式)
9. [安全说明](#九安全说明)
10. [免责声明](#十免责声明)
11. [常见问题 (FAQ)](#十一常见问题-faq)

---

## 一、架构说明

### 数据流

```
用户 → MaiBot → 本插件 → diving-fish API → 返回 JSON
                         │
                         ├─ 曲库缓存 (内存, 5min TTL)
                         ├─ bindings.json (Token 绑定)
                         └─ aliases.json (本地别称)
                         
图片渲染: MaiBot → 本插件 → Playwright (Chromium) → HTML → PNG
```

### 核心组件

| 组件 | 类型 | 功能 |
|------|------|------|
| `MaiMaiDXPlugin` | Plugin | 插件主类，管理配置、缓存、浏览器实例和生命周期 |
| `DivingFishApiClient` | Client | 异步 HTTP 客户端，封装 diving-fish 全部 API |
| `AliasStore` | Store | 本地别称管理，JSON 文件 + 反序索引搜索（线程安全） |
| `BindingStore` | Store | Import-Token 绑定管理，JSON 文件 + 原子写入 |
| `_ensure_browser` | Browser | Playwright Chromium 单例浏览器，懒加载启动 |
| `_render_html_to_png` | Renderer | 统一的 HTML→PNG 图片渲染器，支持 DOM 就绪等待与封面图片加载检测 |

### 认证体系

本插件仅使用 **Import-Token** 认证（无需账号密码），Token 来源为水鱼查分器 personal page 中的「成绩导入 Token」。

| 接口类型 | 认证要求 | 示例 |
|----------|----------|------|
| 公开查询 | 无 | B50、曲目搜索、排行榜等 |
| 成绩读写 | Import-Token Header | 个人成绩、上传、管理等 |

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

插件声明的 SDK **capabilities**：

```
send.text, send.forward, send.image, config.get
```

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
    └── README.md
```

插件初次运行时会在插件目录下自动创建以下文件（如果不存在）：

```
plugins/maimaidx_prober/
    ├── bindings.json     (Token 绑定数据)
    └── aliases.json      (本地别称数据)
```

### 步骤 2：安装 Python 依赖

```bash
pip install aiohttp playwright
```

如果使用 `uv` 管理项目依赖：

```bash
uv pip install aiohttp playwright
```

### 步骤 3：安装 Playwright Chromium 浏览器

**本步骤是必需的**，因为 B50、今日运势、曲目详情、帮助和猜歌功能均依赖 Playwright 渲染图片。

```bash
python -m playwright install chromium
```

> 首次安装需下载约 **300 MB** 的 Chromium 浏览器文件。下载速度取决于网络环境，可能需要几分钟。

如果只使用文本类命令（搜索、状态、绑定等），可跳过此步。但大部分核心功能将不可用。

### 步骤 4：启用插件

编辑 `plugins/maimaidx_prober/config.toml`，确保 `enabled = true`：

```toml
[plugin]
enabled = true
config_version = "1.0.0"
```

或在 MaiBot WebUI 中将插件状态设为「启用」后重载配置。

### 步骤 5：验证安装

在聊天中发送以下命令：

```
/mai help
```

如果收到一幅命令帮助图片，表示安装成功。

---

## 四、配置说明

配置文件位于 `plugins/maimaidx_prober/config.toml`：

```toml
[plugin]
enabled = true               # 是否启用插件
config_version = "1.0.0"     # 配置版本（请勿手动修改）

[server]
base_url = "https://www.diving-fish.com/api/maimaidxprober"
                             # API 服务器地址，一般无需修改
request_timeout = 30         # HTTP 请求超时（秒），B50 等图片渲染建议 ≥30
music_cache_ttl = 300        # 曲库内存缓存时间（秒），默认 5 分钟
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `plugin.enabled` | `true` | 插件开关 |
| `server.base_url` | `https://www.diving-fish.com/api/maimaidxprober` | diving-fish API 地址 |
| `server.request_timeout` | `30` | 单次 HTTP 请求超时秒数 |
| `server.music_cache_ttl` | `300` | 曲库缓存过期时间，减少重复 API 调用 |

---

## 五、命令列表

所有命令以 `/mai` 开头。

### 查询类

| 命令 | 说明 | 认证 |
|------|------|:---:|
| `/mai b50 [用户名/QQ]` | 生成 Best 50 成绩图片（不填则查已绑定账号） | - |
| `/mai song <关键词/ID>` | 搜索曲目，数字 ID 直接查看详情（含封面） | - |
| `/mai my` | 查看个人成绩摘要（含难度分布、Top 10） | Token |

### 娱乐类

| 命令 | 说明 | 认证 |
|------|------|:---:|
| `/mai today` | 今日运势 — 查看宜忌与推荐歌曲 | - |
| `/mai maidle` | 开始 Maidle 猜歌游戏 | - |
| `/mai maidle guess <ID/名称/别称>` | 猜歌游戏 — 提交猜测 | - |
| `/mai maidle answer` | 猜歌游戏 — 查看答案（含封面） | - |
| `/mai maidle help` | Maidle 猜歌游戏规则说明 | - |

### 统计类

| 命令 | 说明 | 认证 |
|------|------|:---:|
| `/mai charts` | 全谱面难度分布统计（FC 率、AP 率） | - |
| `/mai status` | diving-fish 服务器存活检测 | - |

### 管理类

| 命令 | 说明 | 认证 |
|------|------|:---:|
| `/mai bind <Token>` | 绑定水鱼查分器的成绩导入 Token | - |
| `/mai unbind` | 解除当前绑定 | - |

### 别称类

| 命令 | 说明 | 认证 |
|------|------|:---:|
| `/mai alias add <歌曲ID> <别称>` | 为歌曲添加本地别称 | - |
| `/mai alias del <歌曲ID> <别称>` | 删除歌曲别称 | - |
| `/mai alias list <歌曲ID>` | 查看歌曲所有别称 | - |

### 帮助

| 命令 | 说明 |
|------|------|
| `/mai help` 或 `/mai` 或 `/mai 帮助` | 显示命令帮助 |

### AI Tool（模型可调用）

| Tool 名称 | 功能 |
|-----------|------|
| `search_mai_songs` | 按名称/艺术家/ID/别称搜索曲库 |

---

## 六、使用流程

### 1. 获取 Import-Token

1. 登录 [diving-fish 查分器](https://www.diving-fish.com)
2. 进入 personal page（个人中心）
3. 复制「成绩导入 Token」

### 2. 绑定 Token

```
/mai bind <你的Token>
```

绑定成功后返回用户名，可使用 `/mai my` 查看个人成绩。

### 3. 日常使用

```
/mai b50              # 查看自己的 Best 50 图片
/mai b50 某用户QQ      # 查看他人的 B50
/mai song 11115       # 查看歌曲详情（含封面）
/mai song 音楽を辞めた  # 搜索歌曲
/mai today            # 查看今日运势
/mai charts           # 谱面难度统计
```

### 4. 别称使用

```
/mai alias add 11115 yorushika    # 添加别称
/mai song yorushika              # 直接使用别称搜索
```

### 5. Maidle 猜歌

```
/mai maidle                # 开始游戏
/mai maidle guess 11115    # 按歌曲 ID 猜测
/mai maidle guess 音楽      # 按曲名/关键词猜测
/mai maidle answer         # 放弃并查看答案
/mai maidle help           # 查看游戏规则
```

---

## 七、数据存储

所有用户数据存储在插件目录内，不涉及 MaiBot 主程序或其他插件。

| 文件 | 格式 | 内容 | 写入方式 |
|------|------|------|----------|
| `bindings.json` | JSON | `{user_id: {username, import_token, bound_at}}` | 先写 `.tmp` 再 `replace`（原子写入） |
| `aliases.json` | JSON | `{song_id: ["别称1", "别称2"]}` | 同上 |
| 曲库缓存 | 内存 | diving-fish `/music_data` 完整响应 | TTL 5 分钟后过期重取 |
| 谱面统计缓存 | 内存 | diving-fish `/chart_stats` 响应 | TTL 过期后重新获取 |
| Maidle 会话 | 内存 | 猜歌游戏进行中的会话状态 | 后台任务每 60s 清理过期（15分钟）会话 |

> **重要**：`bindings.json` 中包含 Import-Token 明文。该文件位于插件目录内，权限由操作系统文件系统控制。建议确保 MaiBot 插件目录不被未授权用户访问。

---

## 八、卸载方式

### 完整卸载（含依赖清理）

**步骤 1**：在 MaiBot WebUI 中**禁用**（unload）本插件。

**步骤 2**：删除插件目录：

```bash
# Linux / macOS
rm -rf plugins/maimaidx_prober/

# Windows (PowerShell)
Remove-Item -Recurse -Force C:\path\to\MaiBot\plugins\maimaidx_prober\
```

> 删除插件目录会**一并清除** `bindings.json`（Token 绑定数据）、`aliases.json`（别称数据）和 `config.toml`。
> 如需保留数据，请在删除前备份这些文件。

**步骤 3**（可选）：卸载 Chromium 浏览器和 Python 包（如不再需要其他插件使用）：

```bash
# 卸载 Chromium (约 300 MB)
python -m playwright uninstall chromium

# 卸载 Playwright
pip uninstall playwright

# 卸载 aiohttp（仅当无其他插件依赖时）
pip uninstall aiohttp
```

> 如果其他 MaiBot 插件也依赖 `aiohttp` 或 `playwright`，请勿卸载，否则会导致其他插件无法使用。

**步骤 4**（可选）：手动清理 Playwright 缓存目录：

| 操作系统 | 缓存路径 | 删除命令 |
|----------|----------|----------|
| Windows | `%USERPROFILE%\AppData\Local\ms-playwright\` | `Remove-Item -Recurse "$env:USERPROFILE\AppData\Local\ms-playwright"` |
| macOS | `~/Library/Caches/ms-playwright/` | `rm -rf ~/Library/Caches/ms-playwright/` |
| Linux | `~/.cache/ms-playwright/` | `rm -rf ~/.cache/ms-playwright/` |

---

## 九、安全说明

### Import-Token 的性质

Import-Token 是 diving-fish 查分器提供的**成绩写入凭据**。持有此 Token 可以：

- 读取绑定的查分器账号的全部成绩数据
- 向该账号上传新的成绩数据  
- **不能**修改账号密码或其他安全设置
- **不能**删除已有成绩（删除功能需要 JWT Cookie 登录）

### Token 在本插件中的流转

```
用户输入 /mai bind <Token>（聊天消息）
       │
       ▼
Token 传输经过 HTTPS（MaiBot → diving-fish API）
       │
       ▼
Token 仅用于验证有效性，验证后写入 bindings.json
       │
       ▼
后续成绩查询使用 Header: Import-Token = xxx 发送到 diving-fish API（HTTPS）
```

### 本地存储风险

1. **Token 明文存储**：`bindings.json` 以 JSON 明文形式存储 Import-Token
2. **文件权限**：该文件权限由操作系统控制，建议确保插件目录不被其他用户或进程访问
3. **聊天记录泄露**：`/mai bind` 命令中的 Token 参数会出现在聊天记录中

### 安全建议

| 建议 | 说明 |
|------|------|
| **绑定后撤回消息** | 使用 `/mai bind` 后，建议立即撤回包含 Token 的聊天消息 |
| **定期刷新 Token** | 可在 diving-fish 网站 personal page 中重新生成 Token，然后重新绑定 |
| **限制文件访问** | 确保 MaiBot 运行目录的权限设置合理，避免未授权读取 |
| **不要分享 Token** | Import-Token 等同于成绩写入权限，请勿通过任何渠道分享给他人 |
| **使用后删除** | 如不再使用，使用 `/mai unbind` 解绑后删除 `bindings.json` |

### 网络传输

- 本插件与 diving-fish API 之间的所有通信均使用 **HTTPS** 加密
- 封面图片下载同样通过 HTTPS
- 不经过任何第三方代理或中转服务

### Playwright / Chromium 安全

- Chromium 以**无头模式**运行，不显示窗口
- 渲染的 HTML 模板**不加载任何外部网络资源**（CSS/JS/字体均为内联）
- B50 封面的 `<img>` 标签仅加载 diving-fish 官方的封面 CDN
- 浏览器以**单例模式**常驻运行，插件加载时启动一次，卸载时关闭；每次渲染仅创建新页面，渲染完毕后即关闭页面
- 不会修改或使用系统已安装的 Chrome/Edge 浏览器
- Chromium 安装到 Playwright 专用缓存目录，**不会**注册为系统默认浏览器

---

## 十、免责声明

### 1. 无担保（AS IS）

本插件按「现状」提供，不提供任何明示或暗示的担保，包括但不限于：

- 对可用性、准确性、完整性、适用性的担保
- 对功能的持续性或无误性的担保
- 对特定用途适用性的担保

### 2. 使用风险自负

使用本插件查询数据、绑定 Token、上传成绩等行为完全出于用户自愿，由此产生的任何后果（包括但不限于数据丢失、Token 泄露、账号异常）由用户自行承担。

### 3. 第三方服务

本插件连接由第三方维护的 [diving-fish 查分器](https://www.diving-fish.com) 服务。该服务的隐私策略、数据处理方式、可用性和安全性由其运营方（Diving-Fish）自行决定。本插件开发团队：

- 不对 diving-fish 服务的行为、可用性或安全性负责
- 不收集、存储或传输用户的 Token 到任何外部服务器（Token 仅存储在本地插件目录）
- 不对 diving-fish 服务的中断、数据变更或 API 变更负责

### 4. Token 安全

- 本插件将 Token 明文存储在本地 JSON 文件中（`bindings.json`）
- Token 的安全性依赖于所在操作系统的文件权限和运行环境
- 用户应确保 MaiBot 运行环境的安全性，防止未授权访问
- 建议绑定后立即撤回聊天消息中的 Token
- 建议定期在 diving-fish 网站刷新 Token 并重新绑定

### 5. 图片渲染

B50、今日运势、曲目详情等图片渲染功能依赖 Playwright 和 Chromium 浏览器：

- Chromium 浏览器从 Playwright 官方 CDN 下载（约 300 MB）
- 渲染过程在本地完成，不涉及外部网络请求
- Chromium 仅用于 HTML 到图片的转换，不会执行任意 JavaScript 或加载外部脚本
- 由于系统环境差异，Chromium 在某些精简 Docker 镜像或受限沙盒环境中可能无法正常启动

### 6. 责任豁免

在法律允许的最大范围内，插件开发团队对于因使用或无法使用本插件而产生的任何直接或间接损害（包括但不限于数据丢失、Token 泄露、成绩错误、账号异常、服务中断）不承担任何责任。

### 7. 同意与接受

安装并使用本插件即表示您已阅读、理解并同意上述安全说明和免责声明。如果您不同意任何条款，请**停止使用并卸载本插件**。

---

## 十一、常见问题 (FAQ)

### Q1: 发送 `/mai b50` 后长时间无响应或报错

**可能原因**：

1. **曲库数据未缓存**：首次使用时需要从 diving-fish API 下载全曲库（较大），可能需要 10-30 秒
2. **Playwright 未安装**：提示 "playwright 未安装"，执行 `pip install playwright && python -m playwright install chromium`
3. **网络问题**：diving-fish 服务不可达，检查 `https://www.diving-fish.com` 是否可访问
4. **目标用户不存在或设置隐私**：B50 查询可能返回 403（隐私）或 400（用户不存在）

**解决方式**：

- 稍等 30 秒后重试
- 检查网络连接和 `config.toml` 中的 `base_url`
- 如果是隐私限制，请对方在 diving-fish 网站关闭隐私设置

### Q2: B50 图片封面没有加载

**可能原因**：

- 网络波动导致封面下载超时
- 某些歌曲的封面在 diving-fish CDN 上不存在

**说明**：

封面缺失不会影响 B50 卡片的主体数据显示。插件使用了 30 秒超时等待所有封面加载完成，缺失的封面会自动隐藏。

### Q3: `/mai today` 只显示文字没有图片

**可能原因**：

- 封面下载失败（网络波动或 CDN 不可达），此时会回退到文字版输出

**解决方式**：

- 稍后重试，通常封面 CDN 短暂波动后会恢复

### Q4: 猜歌游戏提示「歌曲 ID 不存在」

**可能原因**：

- 输入的歌曲 ID 不在 Maidle 游戏的歌曲库中
- 使用了 music_data 中的 ID 但服务器暂不支持

**解决方式**：

- 使用 `/mai song <关键词>` 查询有效歌曲 ID
- Maidle 游戏允许使用曲名、别称或 ID 进行猜测

### Q5: 绑定的 Token 提示失效

**可能原因**：

- Token 已在 diving-fish 网站被刷新或撤销
- Token 在绑定传输过程中被截断或错误复制

**解决方式**：

1. 登录 diving-fish 网站 personal page
2. 重新复制「成绩导入 Token」
3. 执行 `/mai bind <新Token>` 重新绑定

### Q6: `/mai song <ID>` 返回「未找到歌曲 ID」

**可能原因**：

- 曲库缓存尚未加载或已过期
- 输入的 ID 确实不在曲库中

**解决方式**：

- 稍等后重试（首次使用会触发曲库下载）
- 使用 `/mai song <曲名>` 进行模糊搜索
- 检查 `config.toml` 中 `base_url` 是否正确

### Q7: `/mai charts` 显示空白或数据不全

**可能原因**：

- 谱面统计数据源尚未更新
- 网络请求超时

**解决方式**：

- 稍后重试，数据会自动更新

### Q8: Playwright 安装失败或 Chromium 无法启动

**可能原因**：

- 磁盘空间不足（Chromium 约需 300 MB）
- 系统缺少必要的依赖库（Linux 常见）
- Docker 容器中沙盒限制

**解决方式**：

- **磁盘空间不足**：清理磁盘后重试安装
- **Linux 缺少库**：`python -m playwright install --with-deps chromium`（自动安装系统依赖）
- **Docker 沙盒**：以 `--no-sandbox` 参数启动 MaiBot（安全性降低，仅建议在受信任的容器环境中使用）
- **代理网络**：设置 `PLAYWRIGHT_DOWNLOAD_HOST` 环境变量指向国内镜像

### Q9: 删除插件目录后磁盘仍有大文件

**说明**：

- Chromium 浏览器安装在 Playwright 全局缓存目录，不在插件目录内
- 如要彻底清理，请参照 [卸载方式](#八卸载方式) 中的步骤 3 和步骤 4

### Q10: 可以使用自己的 diving-fish 自建服务器吗

**可以**。修改 `config.toml` 中的 `server.base_url` 为你的自建服务器地址，格式例如：

```toml
base_url = "https://your-server.com/api/maimaidxprober"
```

前提是自建服务器实现了与 diving-fish 兼容的 API 接口。

### Q11: `/mai my` 显示的「总成绩数」和「难度分布」是什么含义

- **总成绩数**：按 `song_id` 去重后的唯一歌曲数量（不重复计算同曲不同难度）
- **SD 曲目 / DX 曲目**：按歌曲类型（SD 标准 / DX 豪华）去重统计
- **难度分布**：每首歌曲取其最佳 RA 所属的难度等级进行归类
- **Top 10**：RA 最高的 10 首歌曲（每首仅显示其最佳难度）

### Q12: 添加的别称在哪里存储？能否迁移

别称存储在插件目录下的 `aliases.json` 中。该文件是标准 JSON 格式，可以直接复制到其他安装同一插件的 MaiBot 实例中。

---

**插件版本**: 1.0.0  
**插件 ID**: `deepseek-v4-pro.maimaidx-prober`  
**最后更新**: 2026-06
