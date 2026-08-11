# MaiMai DX 查分器插件 · 开发者文档

> 面向**开发者**（本插件维护者 / 想贡献的人）的架构、扩展与测试说明。
> 使用者请阅读 [README.md](README.md)。

本插件基于 [maibot-plugin-sdk](https://github.com/Mai-with-u/maibot-plugin-sdk)（v2.x）
编写，运行在 MaiBot 新版插件运行时（`src/plugin_runtime`）中：宿主按
`_manifest.json + plugin.py` 发现插件，`create_plugin()` 返回
`MaiMaiDXPlugin`（`core/plugin.py`），命令通过 SDK 的 `@Command` 装饰器注册。

---

## 1. 快速开始

```bash
# 1) 代码位置
#    开发源：D:\插件\maimaidx_prober-main
#    部署位：<MaiBot>/plugins/maimaidx_prober

# 2) 语法/导入自检（使用宿主 Python + SDK overrides）
python -m py_compile core/**/*.py
PYTHONPATH=<OneKey-userdata>/python-overrides python -c \
  "import sys; sys.path.insert(0,'.'); from core import plugin; print('OK')"

# 3) 部署（保留线上 config.toml）
robocopy <src> <dst> /E /XD __pycache__ /XF config.toml
```

插件目录被 MaiBot 的 `watchfiles` 监听，文件变化会触发**自动重载**；改完代码观察
`logs/app_*.log.jsonl`，出现「插件 … 加载成功 → 注入 PluginContext → 注册完成」
即重载成功。出错时优先看 `plugin_loader` 与 `<runner>` 日志。

## 2. 架构总览

### 分层

```
命令层 core/commands/     @Command 装饰器 + mixin（basic / score / lxns / maidle）
   │
服务层 core/services/     PlayerQueryService（统一选源）→ 其余业务服务
   │
客户端 core/clients/      DivingFishApiClient / LxnsApiClient（三态鉴权）
存储层 core/stores/       JsonStore 基类 + 绑定/别称
渲染层 core/renderers/    HTML → PNG（宿主 html2png 优先，Playwright 回退）
```

### 数据流

```
用户 → MaiBot → 插件命令 → PlayerQueryService
        ├→ DivingFishApiClient（水鱼：曲库/成绩/猜歌/运势/热门/排行/plate/upload）
        └→ LxnsApiClient（落雪：公开补全 + OAuth/个人密钥/开发者密钥）
           选源规则：绑定落雪 → 开发者密钥+好友码 → 水鱼兜底

渲染：renderers 生成 HTML → HtmlRenderer.render() → 宿主 render.html2png
      （宿主不可用时回退插件内置 Playwright，2x 设备像素比）
```

### 双源选源规则（`PlayerQueryService._resolve`）

1. `--df` 强制水鱼（需绑定或目标用户名）；
2. 目标为好友码（≥12 位数字）→ 开发者模式（**须过 `developer_qq` 白名单**）；
3. 已绑定落雪 → `lxns_user`（查询他人会提示改用好友码）；
4. `--lxns` 强制落雪（须已绑定）；
5. 已绑定水鱼 → `water_fish`；
6. 有目标用户名 → 水鱼无鉴权查询；
7. 否则返回绑定引导。

## 3. 目录结构

```
plugin.py                    # 入口：from .core import create_plugin
_manifest.json               # manifest v2（id / 版本 / capabilities / 依赖）
config.toml                  # 配置模板（部署时保留线上密钥）
install_deps.py              # 依赖自检安装（aiohttp + playwright）
Dockerfile.example           # 容器构建示例
assets/                      # 官方素材（maimai/chunithm）+ Varela Round 字体
core/
├── plugin.py                # MaiMaiDXPlugin：生命周期 + 组装（mixin 挂载）
├── config.py                # pydantic 配置模型（plugin/server/lxns/render）
├── constants.py             # 评级/FC/FS 显示、版本、文案模板
├── rating.py                # 官方 DX Rating 系数表 + compute_ra
├── assets.py                # 素材 base64 data URI（lru_cache）
├── util.py                  # 身份、时间、Maidle 线索格式化等
├── clients/
│   ├── diving_fish.py       # 水鱼客户端（ETag/304、update_records、plate）
│   └── lxns.py              # 落雪客户端（公开 + 三态鉴权 + OAuth 令牌端点）
├── stores/
│   ├── json_store.py        # 原子写 JSON 基类
│   ├── bindings.py          # 水鱼 Import-Token
│   ├── lxns_bindings.py     # 落雪 OAuth/个人密钥
│   └── aliases.py           # 别称 + 反向索引 + 翻页导入（上限 100 页）
├── services/
│   ├── player.py            # 统一数据服务层（选源/归一化/互补/回退/上传）
│   ├── lxns_auth.py         # OAuth 授权链接/PKCE/换 token/单飞刷新
│   ├── music.py             # 曲库缓存/匹配/落雪补全/双向 ID 索引
│   ├── covers.py            # 封面与静态图（魔数校验 + 双源兜底 + 缓存）
│   ├── renderer.py          # 宿主渲染优先，Playwright 回退
│   ├── maidle.py            # 猜歌会话（15 分钟 TTL）
│   └── deps.py              # 依赖自检/安装
├── renderers/
│   ├── theme.py             # B50 设计系统 + 浅色面板样式 + 卡片组件
│   ├── b50.py               # Best 50（占位卡/Lv/游玩时间）
│   ├── charts.py aliases.py lxns_status.py player.py plate.py
│   ├── hot.py ranking.py best.py history.py rank.py trend.py heatmap.py
│   ├── collections.py year.py my.py song.py today.py pick.py status.py
│   ├── help.py maidle.py
│   └── common.py            # doc()/cmd_section()/footer_bar()
└── commands/
    ├── base.py              # SharedHelpersMixin（渲染发送/绑定/详情文本）
    ├── basic.py             # help/song/charts/hot/ranking/status/today/alias
    ├── score.py             # b50/my/bind/unbind/plate
    ├── lxns.py              # 绑定管理 + 落雪独有能力 + 双向上传
    └── maidle.py            # 猜歌
```

## 4. 核心设计细节

### 4.1 数据互补与 ID 映射

- 两个查分器曲目 ID 不同源：老曲 `lxns id == 水鱼 id`，新曲 `lxns id == 水鱼 id − 10000`；
  `MusicService` 维护双向索引（`_lxns_by_id` / `_df_by_lxns_id`），
  `_find_lxns_song` 先 ID 候选再标题交叉确认，避免错配；
- 落雪成绩不含量级（DS）与版本字段，`PlayerQueryService._enrich_with_df`
  用水鱼曲库补 `ds` / `df_song_id` / `title`；
- RA 回填使用 `core/rating.py`（与落雪前端一致）：
  `ra = int(min(acc,100.5)/100 × 系数(acc) × ds)`；
  **宴会场（utage）RA 官方恒为 0，不回填**（`type == "utage"` 直接跳过 RA 计算，
  但保留 ds/封面补全）；
- 水鱼查询掩码（`dxScore` 全 0）用 `_detect_mask` 启发式识别，命令层输出提示。

### 4.2 落雪鉴权（`LxnsAuthService` + `LxnsApiClient`）

- 三种鉴权头：个人密钥 `X-User-Token`、开发者 `Authorization: <key>`、
  OAuth `Authorization: Bearer <token>`；**密钥不可混用**；
- OAuth：OOB（`urn:ietf:wg:oauth:2.0:oob`）或回调；机密客户端带
  `client_secret` 不可用 PKCE，公共客户端必须 PKCE(S256)；
- access token 15 分钟、refresh 30 天且**每次刷新轮换**（旧令牌立即失效），
  因此刷新必须**单飞**（`_refresh_single_flight`），避免并发刷新导致旧令牌失效；
- 令牌只存本地 `lxns_bindings.json`，日志一律不打印令牌；
- 开发者功能统一受 `[plugin].developer_qq` 白名单约束，拦截点在
  `PlayerQueryService`（`_resolve` 的好友码分支、`get_ap50`、`get_lxns_best`、
  `get_lxns_player_by_qq`、`get_plate`），空白名单 = 全部关闭。

### 4.3 渲染链路

- 所有渲染器输出 HTML，经 `HtmlRenderer.render()`：
  1. 优先宿主 `ctx.render.html2png`（宿主管 Chromium/并发/沙箱）；
  2. 宿主不可用回退插件内置 Playwright（`--no-sandbox`，按配置）；
- 图片素材走 `assets.py` base64 内嵌（离线可用）；封面/收藏品等远程图
  走 `CoverService`：**魔数校验**（防 WAF 挑战页）、双源兜底、LRU 缓存；
- 新面板统一用 `theme.panel_style()` + `common.doc()`，页脚标注数据来源。

### 4.4 缓存与限流

- 水鱼 `music_data` / `chart_stats` 支持 ETag/304：客户端自动携带
  `If-None-Match`，304 时刷新 TTL 继续用旧缓存（`DivingFishApiClient._etags`）；
- 曲库为内存 TTL 缓存（`MusicService`，`music_cache_ttl` 秒）；
- 落雪资源 CDN 有频率限制，远程图全部缓存。

## 5. 扩展指南

### 5.1 新增命令

```python
from maibot_sdk import Command

@Command("mai_xxx", description="说明", pattern=r"^/mai xxx$")
async def handle_xxx(self, stream_id: str = "", matched_groups: dict = None, **kwargs):
    user_id = self._get_user_id(kwargs)
    await self._track_user(stream_id, user_id)
    # 业务逻辑放在 PlayerQueryService / 客户端
    ok = await self._render_and_send(stream_id, lambda: render_xxx(self._renderer, ...), "失败提示")
    return ok, "动作说明", True
```

- 命令方法放在对应 mixin（`core/commands/*.py`），返回 `(ok, 动作, 是否结束)`；
- 涉及开发者凭证的命令，鉴权在服务层统一拦截，命令层无需重复；
- 新增命令后同步更新 `core/renderers/help.py` 与用户文档。

### 5.2 新增渲染器

1. 在 `core/renderers/` 新建 `xxx.py`，导出 `async def render_xxx(renderer, ...) -> str`；
2. 使用 `doc(panel_style(extra), body)` 组装（B50 页用 `theme.page_style()`）；
3. 在 `core/renderers/__init__.py` 导入并加入 `__all__`；
4. 冒烟测试：mock `renderer.render` 直接返回 HTML，验证不抛异常。

### 5.3 新增 API 端点

1. `core/clients/*.py` 加客户端方法（统一返回 `{"_error": ..., "_status": ...}` 错误约定）；
2. `core/services/player.py`（或对应服务）加业务方法，错误文案面向用户友好；
3. 命令层接线，必要时新增渲染器；
4. 真实凭证验证后再收尾。

### 5.4 新增配置字段

1. `core/config.py` 对应 pydantic 模型加字段（`Field(default=..., description=...)`）；
2. 同步 `config.toml` 模板与已部署实例的 `config.toml`（**保留线上密钥**）；
3. 配置结构变化时按约定提升 `config_version`（当前 3.0 内不升大版本）；
4. `on_config_update` 会自动重建渲染器与客户端，无需额外处理。

## 6. 数据模型要点

### 归一化（`core/services/normalize.py`）

落雪 `MaimaiScore` → 水鱼风格字段：`song_id/title/level/level_index/achievements/
ra/rate/fc/fs/type(SD|DX|utage)/ds/dx_score/dx_star/play_time...`。
渲染器只消费归一化后的 dict，两源喂同一渲染器。

### RA 系数（`core/rating.py`）

达成率档位 → 系数：`<50→0.0 … ≥100.5→22.2`（完整表见文件，与
`maimai-prober-frontend/src/utils/rating.ts` 一致）。

### 上传负载

- 水鱼 `update_records`：`title + type + level_index` 定位（非 song_id），
  `achievements/fc/fs/dxScore` 可选；**只升不降**在客户端做差异；
- 落雪 `user/maimai/player/scores`：`{scores: Score[]}`，同 key
  （`id, level_index, type`）比较后上传。

## 7. 测试与验证

1. **静态**：`py_compile` 全量通过；检查未使用导入（`__init__.py` 的 re-export 除外）；
2. **导入**：用宿主 Python + SDK overrides 导入 `core`；
3. **渲染冒烟**：FakeRenderer 逐个渲染器生成 HTML；
4. **服务层回归**：fake 客户端验证选源/权限/上传差异逻辑（含 `developer_qq`
   空白名单拒绝、只升不降计数、utage 跳过）；
5. **真实账号**：水鱼 Import-Token + 落雪绑定（personal/OAuth）跑通读接口；
   写接口（`/mai lxns upload`、`/mai df upload`）先 `dry_run` 看差异再执行；
6. **热重载**：部署后看日志「加载成功 → 注册完成」，确认无插件报错。

## 8. 安全与密钥处理规范

插件涉及**收集并本机保存密钥**（水鱼 Import-Token、落雪个人密钥 / OAuth 令牌、
开发者密钥），开发者改动时必须遵守以下红线：

### 密钥类型与存储

| 密钥 | 存储位置 | 写入路径 |
| --- | --- | --- |
| 水鱼 Import-Token | `data/plugins/<id>/bindings.json` | `BindingStore.set` |
| 落雪个人密钥 / OAuth access+refresh | `data/plugins/<id>/lxns_bindings.json` | `LxnsBindingStore.set_*` |
| 落雪开发者密钥（全局） | `plugins/maimaidx_prober/config.toml` | 手工配置 |
| 水鱼 Developer-Token（全局） | `plugins/maimaidx_prober/config.toml` | 手工配置 |

### 代码红线

1. **令牌不进日志**：不得 `logger.info/warning` 或 `print` 任何令牌；错误回执只返回
   服务端 `message`，不拼原始请求头/请求体；
2. **令牌不进异常**：`str(异常)` 可能携带请求上下文，涉及 HTTP 请求的异常处理
   不要直接回传原始异常对象；
3. **令牌只进本地 JSON**：通过 `stores/` 写入运行时数据目录，禁止入库、禁止上传
   到任何外部服务，禁止写进 `config.toml` 模板或文档示例（模板一律空值）；
4. **开发者功能必须过白名单**：新增使用开发者凭证的端点，一律先走
   `PlayerQueryService._developer_allowed`（`[plugin].developer_qq`），
   空白名单 = 关闭；不要在命令层绕开；
5. **部署保护线上密钥**：工作区 → 实例同步使用
   `robocopy <src> <dst> /E /XD __pycache__ /XF config.toml`，
   禁止整目录覆盖（会清掉线上 `developer_api_key` / OAuth 配置）；
6. **OAuth 刷新单飞**：refresh 令牌每次刷新轮换（旧令牌立即失效），并发刷新会
   互相作废，必须走 `_refresh_single_flight`；
7. **dry_run 先行**：涉及写数据的功能（`upload_lxns_to_df` 等）保留
   `dry_run` 参数，先用真实数据看差异，再决定是否写库；
8. **文档同步**：密钥类型/存储/吊销方式变更时，同步更新 README「安全说明」。

### 发布前审查清单

- [ ] 全仓搜索确认无真实密钥（含历史文档/示例）；
- [ ] 新增功能的错误路径不泄露令牌；
- [ ] 新增开发者端点已接入白名单；
- [ ] 部署脚本排除 `config.toml`；
- [ ] README「安全说明 / 免责声明」与实现一致。

## 9. 编码规范（摘录自 MaiBot AGENTS.md）

- 语言：简体中文（注释、日志、提示文案）；
- 导入顺序：`from ... import ...` 在前、`import ...` 在后，字母序；本地模块最后，
  跨包用 `from src`/相对导入；
- 类型注解：函数参数/返回尽量注解，泛型用 `typing`（`List[int]` 等）；
- 注释：保留原有注释，复杂逻辑补充注释；不做无边界重构；
- 依赖：以 `pyproject.toml` 为准并同步 `requirements.txt`；
- 修改配置文件只改模板并升版本号，不擅自新增 `ConfigUpgradeHook`；
- 插件在 `plugins/` 下独立维护，主程序代码改动需先申请许可。

## 10. 发布流程

1. 功能完成 + 回归通过后，更新 `CHANGELOG.md`（按「主要功能 / 细节修复」分组）与
   `README.md` / `DEVELOPMENT.md` 命令表；
2. 版本号与 `_manifest.json` 同步（当前 3.0 内保持 `3.0.0`，不升大版本）；
3. 提交到仓库（插件仓库独立于 MaiBot 主仓库）；
4. 插件市场从仓库拉取新版本后，在线上实例热重载验证。
