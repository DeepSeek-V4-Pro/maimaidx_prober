# MaiMai DX 查分器插件（v2.0）

连接 [diving-fish（水鱼）](https://www.diving-fish.com) 查分器 API，并使用
[lxns（落雪）](https://maimai.lxns.net) **公开接口**做曲目数据补全，在 MaiBot 中提供舞萌 DX
的 B50 成绩图、曲目搜索、猜歌、谱面统计、今日运势与个人成绩查询。

> **水鱼 API**: <https://www.diving-fish.com/api/maimaidxprober>  
> **lxns API**: <https://maimai.lxns.net/api/v0>（仅公开端点，无需认证）  
> **插件版本**: 2.0.0 | **插件 ID**: `deepseek-v4-pro.maimaidx-prober`

---

## 目录

1. [v2.0 更新要点](#v20-更新要点)
2. [架构说明](#架构说明)
3. [依赖清单](#依赖清单)
4. [安装方式](#安装方式)
5. [容器 / 1Panel 部署](#容器--1panel-部署)
6. [配置说明](#配置说明)
7. [命令列表](#命令列表)
8. [数据存储](#数据存储)
9. [已知问题](#已知问题)
10. [常见问题 (FAQ)](#常见问题-faq)
11. [卸载方式](#卸载方式)
12. [安全说明](#安全说明)
13. [免责声明](#免责声明)

---

## v2.0 更新要点

- **模块化重构**：由单一 3700+ 行 `plugin.py` 拆分为 `core/` 包（命令、服务、渲染、客户端、存储分层），便于后续维护。
- **清理落雪（lxns）认证功能**：移除全部需要账号 Token 的命令（bind/unbind、b50、my、heatmap、trend、year、rank、history、comment、collections），只保留公开接口数据补全（曲目增强、社区别名导入、状态检测）。
- **修复运势曲绘缺失**：lxns 封面 CDN 会对部分运行环境返回「HTTP 200 + JS 反爬页」，旧版会把它当作 PNG 内嵌导致曲绘空白。v2.0 增加图片魔数校验、MIME 自动识别与水鱼兜底，运势/曲目详情/猜歌答案的封面稳定显示。
- **渲染链路升级**：优先使用 MaiBot 宿主 `render.html2png` 能力（宿主统一管理浏览器），回退到内置 Playwright；默认 2x 高清输出。
- **容器部署友好**（对应 [issue #1](https://github.com/DeepSeek-V4-Pro/maimaidx_prober/issues/1)）：新增 `requirements.txt`、`install_deps.py`、`Dockerfile.example`。
- **统一命令前缀**：移除 `/mai df`、`/mai lxns` 前缀（lxns 个人功能未实现，区分来源已无必要），成绩/绑定/别名导入全部并入 `/mai`。
- 完整变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 架构说明

### 数据流

```
用户 → MaiBot → 本插件 ─┬→ DivingFishApiClient (diving-fish API) → B50/成绩/猜歌/运势/统计
                        │
                        └→ LxnsApiClient (lxns 公开 API) → 曲目增强/社区别名/封面 CDN

封面下载: lxns assets.lxns.net（魔数校验，失败自动回退）→ diving-fish covers
曲目数据: diving-fish 基础数据 + lxns 公开数据补全（分类名/版本名/谱师/定数/note分布）
```

### 模块结构

```
maimaidx_prober/
├── plugin.py                  # 插件入口（MaiBot 加载点）
├── core/
│   ├── plugin.py              # 主类：生命周期 + 组装
│   ├── config.py              # 配置模型（pydantic）
│   ├── constants.py           # 评级/文案/样式常量
│   ├── util.py                # 通用工具函数
│   ├── clients/               # API 客户端
│   │   ├── diving_fish.py     #   水鱼全量接口
│   │   └── lxns.py            #   落雪公开接口（仅数据补全）
│   ├── stores/                # 本地 JSON 存储（原子写入）
│   │   ├── json_store.py
│   │   ├── aliases.py         #   别称管理
│   │   └── bindings.py        #   水鱼 Token 绑定
│   ├── services/              # 业务服务
│   │   ├── music.py           #   曲库缓存/匹配/lxns 补全
│   │   ├── covers.py          #   封面下载（魔数校验 + 兜底）
│   │   ├── renderer.py        #   宿主渲染 + Playwright 回退
│   │   ├── maidle.py          #   猜歌会话
│   │   └── deps.py            #   依赖自检/安装
│   ├── renderers/             # 图片渲染（HTML → PNG）
│   │   ├── today.py           #   今日运势
│   │   ├── song.py            #   曲目详情
│   │   ├── b50.py             #   Best 50
│   │   ├── my.py              #   个人成绩
│   │   ├── maidle.py          #   猜歌/答案
│   │   └── help.py            #   各类帮助
│   └── commands/              # 命令（mixin，按域拆分）
│       ├── basic.py           #   /mai 基础功能
│       ├── score.py           #   /mai 成绩查询（b50/my/bind）
│       └── maidle.py          #   猜歌
├── requirements.txt           # Python 依赖清单
├── install_deps.py            # 一键依赖安装脚本
├── Dockerfile.example         # 容器部署示例
├── _manifest.json             # 插件清单
├── config.toml                # 插件配置
├── CHANGELOG.md               # 更新日志
└── README.md
```

### 核心组件

| 组件 | 说明 |
|------|------|
| `MaiMaiDXPlugin` | 插件主类，组装各服务并管理生命周期 |
| `DivingFishApiClient` | 水鱼异步 API 客户端 |
| `LxnsApiClient` | 落雪公开 API 客户端 |
| `MusicService` | 曲库缓存、模糊搜索、lxns 数据补全 |
| `CoverService` | 封面下载（内容校验 + 双源兜底 + 缓存） |
| `HtmlRenderer` | 宿主 `render.html2png` 优先，Playwright 回退 |
| `AliasStore` / `BindingStore` | JSON 存储 |

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
config_version = "2.0.0"     # 配置版本（请勿手动修改）
auto_install_deps = false    # 依赖缺失时自动安装

[server]
base_url = "https://www.diving-fish.com/api/maimaidxprober"
request_timeout = 30         # HTTP 请求超时（秒）
music_cache_ttl = 300        # 曲库内存缓存时间（秒）

[lxns]
enable = true                # 是否启用 lxns 公开数据补全
base_url = "https://maimai.lxns.net/api/v0"
asset_url = "https://assets.lxns.net"
request_timeout = 30
music_cache_ttl = 300

[render]
device_scale_factor = 2.0    # 渲染缩放（2.0 高清 / 1.0 标准）
image_timeout_ms = 15000     # 等待图片加载超时
browser_executable = ""      # Playwright 回退时的浏览器路径（留空自动查找）
headless = true
no_sandbox = true            # 容器环境建议保持 true
```

## 命令列表

### 基础命令（`/mai`）

| 命令 | 说明 |
|------|------|
| `/mai help` | 命令总览 |
| `/mai song <关键词/ID>` | 搜索曲目，ID 直接查看详情（含封面 + lxns 补全） |
| `/mai today` | 今日运势 — 宜忌与推荐歌曲（含曲绘图片） |
| `/mai maidle` | 开始 Maidle 猜歌游戏 |
| `/mai maidle guess <ID/名称>` | 猜歌 — 提交猜测 |
| `/mai maidle answer` | 猜歌 — 查看答案 |
| `/mai maidle help` | 猜歌规则说明 |
| `/mai charts` | 全谱面难度分布统计 |
| `/mai status` | 双服状态检测（水鱼 + lxns） |
| `/mai pick <A> <B> [C] [D]` | 随机帮你选一个 |
| `/mai alias add/del/list` | 本地别称管理 |

### 成绩查询（`/mai`）

| 命令 | 说明 |
|------|------|
| `/mai b50 [用户名/QQ]` | 生成 Best 50 成绩图片 |
| `/mai my` | 个人成绩摘要（需绑定 Token） |
| `/mai bind <Token>` | 绑定水鱼成绩导入 Token |
| `/mai unbind` | 解除绑定 |

> 曲目详情已自动合并 lxns 公开数据补全（谱师/注音/Buddy/Note 分布），
> 无需单独的命令区分数据源。

### AI Tool

| 工具名 | 功能 |
|--------|------|
| `search_mai_songs` | 按名称/艺术家/ID/别称搜索曲库 |

## 数据存储

所有用户数据保存在插件目录内：

| 文件 | 内容 |
|------|------|
| `bindings.json` | 水鱼 Token 绑定（明文，注意权限） |
| `aliases.json` | 本地别称 |
| 曲库缓存 | 内存 TTL 缓存（水鱼曲库/谱面统计/lxns 曲库） |
| Maidle 会话 | 内存会话，15 分钟过期，后台定时清理 |

## 已知问题

1. **lxns 封面 CDN 反爬**：`assets.lxns.net` 会对部分客户端（如 Python 3.12 的 TLS
   指纹）返回 HTTP 200 的 JS 挑战页。插件已按图片内容校验并自动回退水鱼封面，
   但 lxns 封面偶尔仍有小概率失败，此时卡片显示「曲绘缺失」占位。
2. **部分老歌无封面**：水鱼/lxns 两个 CDN 都存在少量缺失，会显示占位符而不影响卡片主体。
3. **首次渲染较慢**：Playwright 回退模式下首次启动浏览器需 10-30 秒；宿主渲染模式由宿主预热。
4. **lxns 曲目详情接口**：`/maimai/song/{id}` 部分版本参数返回 404，v2.0 仍使用
   曲库缓存本地补全（分类/版本/谱师/note 分布），不影响使用。

## 常见问题 (FAQ)

### Q1: `/mai today` 图片里没有曲绘

v2.0 已修复：封面按图片内容校验，lxns 被反爬时自动回退水鱼。若仍缺失，多为该曲两个
CDN 都没有封面，卡片会显示「曲绘缺失」占位。

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

v2.0 已统一命令前缀：lxns 公开数据补全并入 `/mai`（曲目详情自动增强、
`/mai alias import` 导入社区别名），需要 lxns 账号认证的命令已移除，详见 CHANGELOG。

## 卸载方式

1. 在 MaiBot WebUI 中禁用插件。
2. 删除插件目录（会清除 `bindings.json`、`aliases.json`、`config.toml`，请先备份）。
3. 可选：`python -m playwright uninstall chromium`。

## 安全说明

- 水鱼 Import-Token 以明文存储在 `bindings.json`，持有者可读写你的成绩数据。
- 绑定后建议撤回聊天中的 Token 消息；不要分享 Token。
- 插件目录请限制文件系统权限。
- 所有 API 通信均为 HTTPS。

## 免责声明

1. 本插件按「现状」提供，不提供任何明示或暗示的担保。
2. 使用本插件的行为完全出于用户自愿，由此产生的任何后果由用户自行承担。
3. 本插件连接由第三方维护的 diving-fish 和 lxns 服务，不对其可用性或安全性负责。
4. 图片渲染依赖浏览器环境，在精简容器或受限沙盒中可能无法正常启动。

安装并使用本插件即表示您已阅读、理解并同意上述说明。

---

**插件版本**: 2.0.0  
**插件 ID**: `deepseek-v4-pro.maimaidx-prober`  
**更新日志**: [CHANGELOG.md](CHANGELOG.md)
