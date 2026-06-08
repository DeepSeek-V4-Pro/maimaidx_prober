"""MaiMai DX 查分器插件 — 连接 diving-fish API，提供 B50 图片、曲目搜索（含别称）、猜歌、谱面统计与个人成绩查询"""

import asyncio
import base64
import hashlib
import html as _html
import json
import logging
import random
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import aiohttp

from maibot_sdk import Command, Field, MaiBotPlugin, PluginConfigBase, Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType

from .lxns_client import LxnsApiClient, LxnsBindingStore

logger = logging.getLogger(__name__)

RATE_DISPLAY: dict[str, str] = {
    "d": "D", "c": "C", "b": "B", "bb": "BB", "bbb": "BBB",
    "a": "A", "aa": "AA", "aaa": "AAA",
    "s": "S", "sp": "S+", "ss": "SS", "ssp": "SS+",
    "sss": "SSS", "sssp": "SSS+",
}
FC_DISPLAY: dict[str, str] = {"": "-", "fc": "FC", "fcp": "FC+", "ap": "AP", "app": "AP+"}
FS_DISPLAY: dict[str, str] = {
    "": "-", "fs": "FS", "fsp": "FS+", "fsd": "FSD", "fsdp": "FSD+", "sync": "SYNC",
}

_BASE_HTML_STYLE = (
    "*{margin:0;padding:0;box-sizing:border-box}"
    "body{background:linear-gradient(180deg,#1c1c30 0%,#222240 100%);"
    "color:#d0d0dc;font-family:'Segoe UI','Microsoft YaHei',sans-serif;"
    "padding:28px 32px}"
)

DIFF_NAMES = ["Basic", "Advanced", "Expert", "Master", "Re:Master"]


def _build_difficulty_detail_text(difficulties: dict, level_names: list) -> str:
    lines: list[str] = []
    for cat_key, cat_label in [("standard", "SD"), ("dx", "DX"), ("utage", "宴")]:
        cat_diffs = difficulties.get(cat_key, [])
        if not cat_diffs:
            continue
        for d in cat_diffs:
            if not isinstance(d, dict):
                continue
            diff_idx = d.get("difficulty", 0)
            level_label = level_names[diff_idx] if diff_idx < len(level_names) else "?"
            kanji = d.get("kanji", "")
            designer = d.get("note_designer", "")
            buddy = " [Buddy]" if d.get("is_buddy", False) else ""
            notes = d.get("notes", {})
            note_parts = []
            if isinstance(notes, dict):
                for nk in ("tap", "hold", "slide", "touch", "break"):
                    if notes.get(nk, 0) > 0:
                        note_parts.append(f"{nk[0].upper()}{notes[nk]}")
            note_str = "/".join(note_parts) if note_parts else ""
            line = f"  [{cat_label}] {level_label}{buddy}"
            if kanji:
                line += f" ({kanji})"
            if designer:
                line += f"  谱师: {_html.escape(designer)}"
            if note_str:
                line += f"  Notes: {note_str}"
            lines.append(line)
    return "\n".join(lines)


class PluginSectionConfig(PluginConfigBase):
    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0
    enabled: bool = Field(default=True, description="是否启用插件")
    config_version: str = Field(default="1.1.0", description="配置版本")


class ServerConfig(PluginConfigBase):
    __ui_label__ = "服务器"
    __ui_icon__ = "server"
    __ui_order__ = 1
    base_url: str = Field(
        default="https://www.diving-fish.com/api/maimaidxprober",
        description="API 服务器地址",
    )
    request_timeout: int = Field(default=30, description="请求超时时间(秒)")
    music_cache_ttl: int = Field(default=300, description="曲库缓存时间(秒)")


class LxnsServerConfig(PluginConfigBase):
    __ui_label__ = "lxns 服务器"
    __ui_icon__ = "cloud"
    __ui_order__ = 2
    enable: bool = Field(default=True, description="是否启用 lxns API")
    base_url: str = Field(
        default="https://maimai.lxns.net/api/v0",
        description="lxns API 服务器地址",
    )
    asset_url: str = Field(
        default="https://assets.lxns.net",
        description="lxns 资源 CDN 地址",
    )
    request_timeout: int = Field(default=30, description="请求超时时间(秒)")
    music_cache_ttl: int = Field(default=300, description="曲库缓存时间(秒)")


class MaiMaiDXConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    lxns: LxnsServerConfig = Field(default_factory=LxnsServerConfig)


class AliasStore:
    def __init__(self, filepath: str) -> None:
        self._filepath = Path(filepath)
        self._lock = asyncio.Lock()
        self._data: dict[str, list[str]] = {}
        self._index: dict[str, str] = {}

    async def load(self) -> None:
        try:
            if self._filepath.exists():
                content = self._filepath.read_text(encoding="utf-8")
                if content.strip():
                    self._data = json.loads(content)
                    self._rebuild_index()
        except (json.JSONDecodeError, OSError):
            self._data = {}
            self._index = {}

    def _rebuild_index(self) -> None:
        self._index.clear()
        for sid, aliases in self._data.items():
            for a in aliases:
                self._index[a.lower()] = sid

    async def _save(self) -> None:
        try:
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._filepath.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(self._filepath)
        except OSError:
            pass

    async def add(self, song_id: str, alias: str) -> tuple[bool, str]:
        async with self._lock:
            normalized = alias.strip()
            if not normalized or len(normalized) > 30:
                return False, "别称无效（长度 1-30）"
            key = normalized.lower()
            if key in self._index and self._index[key] != str(song_id):
                return False, f"别称「{normalized}」已被歌曲 {self._index[key]} 使用"
            sid = str(song_id)
            if sid not in self._data:
                self._data[sid] = []
            if normalized not in self._data[sid]:
                self._data[sid].append(normalized)
                self._index[key] = sid
                await self._save()
                return True, "添加成功"
            return True, "别称已存在"

    async def delete(self, song_id: str, alias: str) -> tuple[bool, str]:
        async with self._lock:
            sid = str(song_id)
            if sid not in self._data:
                return False, f"歌曲 {song_id} 没有别称"
            normalized = alias.strip()
            if normalized not in self._data[sid]:
                return False, f"别称「{normalized}」不存在"
            self._data[sid].remove(normalized)
            if not self._data[sid]:
                del self._data[sid]
            key = normalized.lower()
            if self._index.get(key) == sid:
                del self._index[key]
            await self._save()
            return True, "删除成功"

    async def list_aliases(self, song_id: str) -> list[str]:
        async with self._lock:
            return list(self._data.get(str(song_id), []))

    async def search(self, keyword: str) -> list[str]:
        async with self._lock:
            key = keyword.lower()
            results: list[str] = []
            if key in self._index:
                results.append(self._index[key])
            for alias_lower, sid in self._index.items():
                if key in alias_lower and sid not in results:
                    results.append(sid)
            return results

    async def import_from_lxns(
        self, fetch_page, add_func,
    ) -> tuple[int, int]:
        imported = 0
        skipped = 0
        page = 1
        pending: list[tuple[str, str]] = []
        while True:
            resp = await fetch_page(page)
            if isinstance(resp, dict) and resp.get("_error"):
                break
            aliases = resp.get("aliases", []) if isinstance(resp, dict) else []
            if not aliases:
                break
            for entry in aliases:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("approved", False):
                    continue
                alias_text = entry.get("alias", "")
                song = entry.get("song", {})
                song_id = str(song.get("id", "") if isinstance(song, dict) else "")
                if not alias_text or not song_id:
                    continue
                pending.append((alias_text.strip(), song_id))
            page += 1
            if isinstance(resp, dict):
                page_count = resp.get("page_count", 0)
                if page > page_count:
                    break
        async with self._lock:
            for alias_text, song_id in pending:
                key = alias_text.lower()
                if key in self._index:
                    skipped += 1
                    continue
                self._data.setdefault(song_id, [])
                if alias_text not in self._data[song_id]:
                    self._data[song_id].append(alias_text)
                    self._index[key] = song_id
                    imported += 1
        if imported > 0:
            await self._save()
        return imported, skipped


class BindingStore:
    def __init__(self, filepath: str) -> None:
        self._filepath = Path(filepath)
        self._lock = asyncio.Lock()
        self._data: dict[str, dict[str, Any]] = {}

    async def load(self) -> None:
        try:
            if self._filepath.exists():
                content = self._filepath.read_text(encoding="utf-8")
                if content.strip():
                    self._data = json.loads(content)
        except (json.JSONDecodeError, OSError):
            self._data = {}

    async def _save(self) -> None:
        try:
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._filepath.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(self._filepath)
        except OSError:
            pass

    async def get(self, user_id: str) -> Optional[dict[str, Any]]:
        async with self._lock:
            return self._data.get(user_id)

    async def set(self, user_id: str, username: str, import_token: str) -> None:
        async with self._lock:
            self._data[user_id] = {
                "username": username,
                "import_token": import_token,
                "bound_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._save()

    async def delete(self, user_id: str) -> bool:
        async with self._lock:
            if user_id in self._data:
                del self._data[user_id]
                await self._save()
                return True
            return False


class DivingFishApiClient:
    def __init__(
        self, base_url: str, timeout: int, session: aiohttp.ClientSession
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session

    @staticmethod
    def _error(message: str, status: int = 0) -> dict:
        return {"_error": True, "_status": status, "message": message}

    async def _get(
        self, path: str, params: dict = None, headers: dict = None
    ) -> dict:
        url = f"{self._base_url}{path}"
        kw: dict[str, Any] = {"timeout": self._timeout}
        if headers:
            kw["headers"] = headers
        if params:
            kw["params"] = params
        try:
            async with self._session.get(url, **kw) as resp:
                if resp.status == 304:
                    return {"_not_modified": True}
                if resp.status == 404:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {}
                    return self._error(data.get("message", "not found"), 404)
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    return self._error(data.get("message", str(data)), resp.status)
                return data
        except asyncio.TimeoutError:
            return self._error("请求超时")
        except aiohttp.ClientError as e:
            return self._error(f"网络错误: {e}")
        except Exception as e:
            return self._error(f"未知错误: {e}")

    async def _post(
        self, path: str, json_data: dict = None, headers: dict = None
    ) -> dict:
        url = f"{self._base_url}{path}"
        kw: dict[str, Any] = {"timeout": self._timeout}
        if headers:
            kw["headers"] = headers
        if json_data is not None:
            kw["json"] = json_data
        try:
            async with self._session.post(url, **kw) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    return self._error(data.get("message", str(data)), resp.status)
                return data
        except asyncio.TimeoutError:
            return self._error("请求超时")
        except aiohttp.ClientError as e:
            return self._error(f"网络错误: {e}")
        except Exception as e:
            return self._error(f"未知错误: {e}")

    async def get_music_data(self, etag: str = None) -> dict:
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        return await self._get("/music_data", headers=headers)

    async def query_player(self, target: str) -> dict:
        body: dict[str, Any] = {"b50": "1"}
        if target.isdigit():
            body["qq"] = target
        else:
            body["username"] = target
        return await self._post("/query/player", json_data=body)

    async def get_player_records(self, import_token: str) -> dict:
        return await self._get("/player/records", headers={"Import-Token": import_token})

    async def token_available(self, token: str) -> dict:
        return await self._get("/token_available", params={"token": token})

    async def alive_check(self) -> dict:
        return await self._get("/alive_check")

    async def get_chart_stats(self, etag: str = None) -> dict:
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        return await self._get("/chart_stats", headers=headers)

    async def get_maidle_data(self, etag: str = None) -> dict:
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        return await self._get("/maidle/data", headers=headers)

    async def maidle_single(
        self, guess_id: int, uuid: str = "", lists: list = None
    ) -> dict:
        body: dict[str, Any] = {"guess_id": guess_id}
        if uuid:
            body["uuid"] = uuid
        body["lists"] = lists if lists is not None else []
        return await self._post("/maidle/single", json_data=body)

    async def maidle_answer(self, uuid: str) -> dict:
        return await self._post("/maidle/answer", json_data={"uuid": uuid})


class MaiMaiDXPlugin(MaiBotPlugin):
    config_model = MaiMaiDXConfig

    _BLESSINGS = [
        "出勤辛苦了…要来CAFE MiLK坐坐吗？ソルトなのです",
        "打机加油…ソルト也会努力揉面团的なのです",
        "今天的面包…烤得和您的手感一样好呢",
        "推分顺利…ソルト在柜台后面偷偷看着喵",
        "成绩不错…要奖励自己一块刚出炉的面包なのです",
        "累了的话…ソルト这里有热牛奶和可颂",
        "AP了呢…ソルト开心得尾巴都翘起来了",
        "紫谱也好红谱也好…都比不上刚烤好的吐司香なのです",
        "出勤完毕…来CAFE MiLK享受安静的午后吧",
        "金框闪闪…比ソルト烤的焦糖面包还亮呢",
        "每次打机回来…ソルト都会准备好热茶等您",
        "分数不重要…开心才重要…ソルト是这样想的なのです",
        "今天也辛苦了…ソルト给您留了限定草莓蛋糕",
        "手感不好也没关系…休息一下再来…ソルト陪你",
        "看到您努力推分…ソルト揉面团的力气也更大了",
        "选曲品味真好…ソルト也喜欢这首的旋律喵",
        "夜深了…打完这局要来一块宵夜面包吗",
        "绝赞全中的感觉…就像面包刚出炉那一刻なのです",
        "ソルト虽然胆小…但看到您的成绩也忍不住鼓掌了",
        "午睡醒来…发现您还在出勤…ソルト给您续杯",
    ]

    async def on_load(self) -> None:
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._api_client: Optional[DivingFishApiClient] = None
        self._client_lock = asyncio.Lock()

        self._lxns_client: Optional[LxnsApiClient] = None
        self._lxns_bindings: Optional[LxnsBindingStore] = None
        self._lxns_song_cache: Optional[dict] = None
        self._lxns_song_cache_time: float = 0

        self._playwright_inst = None
        self._browser = None
        self._browser_lock = asyncio.Lock()

        base = Path(__file__).parent
        self._bindings = BindingStore(str(base / "bindings.json"))
        await self._bindings.load()
        self._aliases = AliasStore(str(base / "aliases.json"))
        await self._aliases.load()

        self._lxns_bindings = LxnsBindingStore(str(base / "lxns_bindings.json"))
        await self._lxns_bindings.load()

        self._song_cache: Optional[list[dict]] = None
        self._song_cache_time: float = 0

        self._chart_stats_cache: Optional[dict] = None
        self._chart_stats_cache_time: float = 0

        self._stream_users: OrderedDict[str, str] = OrderedDict()
        self._stream_users_lock = asyncio.Lock()

        self._maidle_sessions: dict[str, dict] = {}
        self._maidle_sessions_lock = asyncio.Lock()
        self._maidle_cleanup_task: Optional[asyncio.Task] = None

        try:
            loop = asyncio.get_running_loop()
            self._maidle_cleanup_task = loop.create_task(self._cleanup_maidle_sessions())
        except RuntimeError:
            pass

    async def on_unload(self) -> None:
        if self._maidle_cleanup_task:
            self._maidle_cleanup_task.cancel()
            try:
                await self._maidle_cleanup_task
            except asyncio.CancelledError:
                pass
            self._maidle_cleanup_task = None

        async with self._browser_lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    logger.debug("关闭 browser 时出错", exc_info=True)
                self._browser = None
            if self._playwright_inst:
                try:
                    await self._playwright_inst.stop()
                except Exception:
                    logger.debug("关闭 playwright 时出错", exc_info=True)
                self._playwright_inst = None

        if self._http_session:
            await self._http_session.close()
            self._http_session = None
        self._api_client = None
        self._lxns_client = None
        self._lxns_bindings = None
        self._lxns_song_cache = None

    async def on_config_update(
        self, scope: str, config_data: dict[str, object], version: str
    ) -> None:
        if scope == "self":
            async with self._client_lock:
                if self._http_session:
                    await self._http_session.close()
                    self._http_session = None
                self._api_client = None
                self._lxns_client = None
            self._song_cache = None
            self._song_cache_time = 0
            self._chart_stats_cache = None
            self._chart_stats_cache_time = 0
            self._lxns_song_cache = None
            self._lxns_song_cache_time = 0
        del scope, config_data, version

    # ---- Playwright helpers ----

    async def _ensure_browser(self):
        if self._browser is None:
            async with self._browser_lock:
                if self._browser is None:
                    try:
                        from playwright.async_api import async_playwright
                    except ImportError:
                        raise RuntimeError(
                            "playwright 未安装，请执行: pip install playwright && python -m playwright install chromium"
                        )
                    self._playwright_inst = await async_playwright().start()
                    self._browser = await self._playwright_inst.chromium.launch()
        return self._browser

    async def _render_html_to_png(
        self,
        html: str,
        width: int = 680,
        height: int = 500,
        wait_for_images: bool = False,
        image_timeout: int = 15000,
    ) -> str:
        browser = await self._ensure_browser()
        page = await browser.new_page(viewport={"width": width, "height": height})
        try:
            await page.set_content(html)
            await page.wait_for_load_state("domcontentloaded")
            if wait_for_images:
                try:
                    await page.wait_for_function(
                        "() => [...document.querySelectorAll('img')].every(i => i.complete)",
                        timeout=image_timeout,
                    )
                except Exception:
                    logger.debug("等待封面图片加载超时或失败，继续渲染")
            await page.wait_for_timeout(500)
            screenshot = await page.screenshot(full_page=True, type="png")
        finally:
            await page.close()
        return base64.b64encode(screenshot).decode()

    # ---- helpers ----

    async def _get_client(self) -> DivingFishApiClient:
        if self._api_client is None:
            async with self._client_lock:
                if self._api_client is None:
                    self._http_session = aiohttp.ClientSession()
                    self._api_client = DivingFishApiClient(
                        self.config.server.base_url,
                        self.config.server.request_timeout,
                        self._http_session,
                    )
        return self._api_client

    async def _get_lxns_client(self) -> Optional[LxnsApiClient]:
        if not self.config.lxns.enable:
            return None
        if self._lxns_client is None:
            async with self._client_lock:
                if self._lxns_client is None:
                    if self._http_session is None:
                        self._http_session = aiohttp.ClientSession()
                    self._lxns_client = LxnsApiClient(
                        self.config.lxns.base_url,
                        self.config.lxns.asset_url,
                        self.config.lxns.request_timeout,
                        self._http_session,
                    )
        return self._lxns_client

    async def _get_lxns_binding(self, kwargs: dict) -> Optional[dict[str, Any]]:
        user_id = self._get_user_id(kwargs)
        if not user_id or not self._lxns_bindings:
            return None
        return await self._lxns_bindings.get(user_id)

    async def _lxns_auth_call(
        self, client: LxnsApiClient, path: str, binding: dict,
        params: dict = None, json_data: dict = None, method: str = "GET",
    ) -> dict:
        token = binding["token"]
        methods = [binding.get("auth_method", "Bearer")]
        for m in ("Bearer", "Token", "Raw", "Import-Token", "X-API-Key", "param:token", "param:key", "param:import_token"):
            if m not in methods:
                methods.append(m)
        last_err = None
        for auth_hdr in methods:
            if method == "POST":
                resp = await client._post(
                    path, token=token, auth_header=auth_hdr, json_data=json_data,
                )
            else:
                resp = await client._get(
                    path, token=token, auth_header=auth_hdr, params=params,
                )
            result = LxnsApiClient._unwrap_auth(resp)
            if not LxnsApiClient._is_error(result):
                return result
            last_err = result
        if last_err and isinstance(last_err, dict):
            last_err["message"] = (
                f"{last_err.get('message', '请求失败')}\n"
                "⚠ 个人密钥无法访问用户数据，此功能需浏览器登录后的 JWT Token"
            )
        return last_err or {"_error": True, "message": "请求失败"}

    async def _get_lxns_songs_cached(self) -> Optional[dict]:
        now = time.time()
        ttl = self.config.lxns.music_cache_ttl
        if self._lxns_song_cache and (now - self._lxns_song_cache_time) < ttl:
            return self._lxns_song_cache
        client = await self._get_lxns_client()
        if not client:
            return None
        resp = await client.get_song_list()
        if isinstance(resp, dict) and not LxnsApiClient._is_error(resp):
            self._lxns_song_cache = resp
            self._lxns_song_cache_time = now
            return resp
        if self._lxns_song_cache is not None:
            return self._lxns_song_cache
        logger.warning("lxns 曲库数据获取失败且无本地缓存可用")
        return None

    def _resolve_lxns_genre_name(self, genre_id: Any) -> str:
        cache = self._lxns_song_cache
        if not cache:
            return str(genre_id)
        genres = cache.get("genres", [])
        for g in genres:
            if isinstance(g, dict) and g.get("id") == genre_id:
                return str(g.get("title", "") or g.get("genre", str(genre_id)))
        return str(genre_id)

    def _resolve_lxns_version_name(self, version: Any) -> str:
        cache = self._lxns_song_cache
        if not cache:
            return str(version)
        versions = cache.get("versions", [])
        for v in versions:
            if isinstance(v, dict) and v.get("version") == version:
                return str(v.get("title", str(version)))
        return str(version)

    @staticmethod
    def _get_user_id(kwargs: dict) -> str:
        uid = str(kwargs.get("user_id", "") or "")
        if not uid:
            msg = kwargs.get("message")
            if isinstance(msg, dict):
                try:
                    uid = str(
                        msg.get("message_info", {})
                        .get("user_info", {})
                        .get("user_id", "")
                        or ""
                    )
                except AttributeError:
                    pass
        return uid

    async def _get_binding(self, kwargs: dict) -> Optional[dict[str, Any]]:
        user_id = self._get_user_id(kwargs)
        if not user_id:
            return None
        return await self._bindings.get(user_id)

    @staticmethod
    def _is_error(resp: Any) -> bool:
        return isinstance(resp, dict) and resp.get("_error", False)

    @staticmethod
    def _error_msg(resp: dict) -> str:
        return str(resp.get("message", "未知错误"))

    async def _track_user(self, stream_id: str, user_id: str) -> None:
        async with self._stream_users_lock:
            if len(self._stream_users) >= 5000:
                for _ in range(min(1000, len(self._stream_users))):
                    self._stream_users.popitem(last=False)
            self._stream_users[stream_id] = user_id

    def _get_tool_user_id(self, stream_id: str) -> str:
        return self._stream_users.get(stream_id, stream_id)

    @staticmethod
    def _stable_user_uid(user_id: str) -> int:
        digest = hashlib.sha256(user_id.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big")

    async def _get_songs_cached(self) -> Optional[list[dict]]:
        now = time.time()
        ttl = self.config.server.music_cache_ttl
        if self._song_cache and (now - self._song_cache_time) < ttl:
            return self._song_cache
        client = await self._get_client()
        resp = await client.get_music_data()
        if isinstance(resp, list):
            self._song_cache = resp
            self._song_cache_time = now
            return resp
        if self._song_cache is not None:
            return self._song_cache
        logger.warning("曲库数据获取失败且无本地缓存可用")
        return None

    async def _match_songs(self, keyword: str) -> list[dict]:
        if not self._song_cache:
            return []
        kw = keyword.lower()
        results: list[dict] = []
        seen_ids: set[str] = set()

        alias_sids = await self._aliases.search(keyword)

        for music in self._song_cache:
            if not isinstance(music, dict):
                continue
            sid = str(music.get("id", "") or "")
            if not sid or sid in seen_ids:
                continue
            title = str(music.get("title", "")).lower()
            bi = music.get("basic_info", {})
            artist = str(bi.get("artist", "")).lower() if isinstance(bi, dict) else ""
            match = (
                kw in title
                or kw in artist
                or kw == sid
                or sid in alias_sids
            )
            if match:
                seen_ids.add(sid)
                results.append(music)

        if not results:
            words = [
                w.strip(" '\"/-()[]{}")
                for w in kw.split()
                if len(w.strip(" '\"/-()[]{}")) > 1
            ]
            for music in self._song_cache:
                if not isinstance(music, dict):
                    continue
                sid = str(music.get("id", "") or "")
                if not sid or sid in seen_ids:
                    continue
                title = str(music.get("title", "")).lower()
                bi = music.get("basic_info", {})
                artist = str(bi.get("artist", "")).lower() if isinstance(bi, dict) else ""
                if any(w in title or w in artist for w in words):
                    seen_ids.add(sid)
                    results.append(music)

        results.sort(key=lambda m: int(str(m.get("id", "0") or "0")))
        return results

    async def _enrich_with_lxns(self, music: dict) -> dict:
        sid_val = music.get("id", 0)
        try:
            sid_int = int(sid_val)
        except (TypeError, ValueError):
            sid_int = 0
        if not sid_int:
            return {}
        lxns_cache = await self._get_lxns_songs_cached()
        if not lxns_cache:
            return {}
        lxns_songs = lxns_cache.get("songs", [])
        lxns_song = None
        for s in lxns_songs:
            if isinstance(s, dict) and s.get("id") == sid_int:
                lxns_song = s
                break
        if not lxns_song:
            return {}
        result: dict[str, Any] = {
            "genre_name": self._resolve_lxns_genre_name(
                lxns_song.get("genre", "")
            ),
            "version_name": self._resolve_lxns_version_name(
                lxns_song.get("version", 0)
            ),
            "map_name": lxns_song.get("map", ""),
            "difficulties": lxns_song.get("difficulties", {}),
        }
        return result

    async def _build_song_detail_text(self, music: dict) -> str:
        sid = str(music.get("id", "") or "?")
        title = str(music.get("title", "") or "?")
        tp = str(music.get("type", "") or "?")
        bi = music.get("basic_info", {})
        artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
        version = str(bi.get("from", "") or "?") if isinstance(bi, dict) else "?"
        genre = str(bi.get("genre", "") or "?") if isinstance(bi, dict) else "?"
        bpm = bi.get("bpm", "?") if isinstance(bi, dict) else "?"
        ds_list = music.get("ds", [])
        level_list = music.get("level", [])
        diffs_parts = [f"{lvl}({ds})" for lvl, ds in zip(level_list, ds_list)]
        lines = [
            "【曲目详情】",
            f"[{_html.escape(tp)}] {_html.escape(title)}  (ID: {_html.escape(sid)})",
            f"作者: {_html.escape(artist)}  |  BPM: {bpm}",
        ]
        extra = await self._enrich_with_lxns(music)
        if extra:
            genre_display = extra.get("genre_name", "") or genre
            version_display = extra.get("version_name", "") or version
            lines.append(
                f"分类: {_html.escape(str(genre_display))}  |  版本: {_html.escape(str(version_display))}"
            )
            map_name = extra.get("map_name", "")
            if map_name:
                lines.append(f"原曲出处: {_html.escape(str(map_name))}")
            diffs = extra.get("difficulties", {})
            if diffs:
                lines.append(_build_difficulty_detail_text(diffs, level_list))
        else:
            lines.append(f"版本: {_html.escape(version)}  |  分类: {_html.escape(genre)}")
        lines.append(f"定数: {' / '.join(diffs_parts)}")
        aliases = await self._aliases.list_aliases(sid)
        if aliases:
            lines.append(f"别称: {', '.join(aliases)}")
        return "\n".join(lines)

    async def _render_song_detail_image(self, music: dict, cover_b64: str) -> str:
        sid = str(music.get("id", "") or "?")
        title = str(music.get("title", "") or "?")
        tp = str(music.get("type", "") or "?")
        bi = music.get("basic_info", {})
        artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
        version = str(bi.get("from", "") or "?") if isinstance(bi, dict) else "?"
        genre = str(bi.get("genre", "") or "?") if isinstance(bi, dict) else "?"
        bpm = bi.get("bpm", "?") if isinstance(bi, dict) else "?"
        ds_list = music.get("ds", [])
        level_list = music.get("level", [])
        diffs_parts = [f"{lvl}({ds})" for lvl, ds in zip(level_list, ds_list)]
        ds_str = " / ".join(diffs_parts)

        aliases = await self._aliases.list_aliases(sid)
        alias_text = ", ".join(aliases) if aliases else "无"

        extra = await self._enrich_with_lxns(music)
        genre_display = _html.escape(str(extra.get("genre_name", "") or genre))
        version_display = _html.escape(str(extra.get("version_name", "") or version))
        map_name = _html.escape(str(extra.get("map_name", "")))
        map_row = f'<div class="row"><span class="label">出处</span>{map_name}</div>' if map_name else ""

        diff_rows_html = ""
        if extra:
            diffs = extra.get("difficulties", {})
            for cat_key, cat_label in [("standard", "SD"), ("dx", "DX"), ("utage", "宴")]:
                cat_diffs = diffs.get(cat_key, [])
                if not cat_diffs:
                    continue
                for d in cat_diffs:
                    if not isinstance(d, dict):
                        continue
                    diff_idx = d.get("difficulty", 0)
                    level_label = level_list[diff_idx] if diff_idx < len(level_list) else "?"
                    kanji = _html.escape(d.get("kanji", ""))
                    designer = _html.escape(d.get("note_designer", ""))
                    buddy = " [Buddy]" if d.get("is_buddy", False) else ""
                    notes = d.get("notes", {})
                    note_parts = []
                    if isinstance(notes, dict):
                        for nk in ("tap", "hold", "slide", "touch", "break"):
                            v = notes.get(nk, 0)
                            if v > 0:
                                note_parts.append(f"{nk[0].upper()}{v}")
                    note_str = "/".join(note_parts) if note_parts else ""
                    diff_rows_html += (
                        f'<div class="diff-row">'
                        f'<span class="diff-type">[{cat_label}]</span>'
                        f'<span class="diff-lvl">{_html.escape(level_label)}{buddy}</span>'
                    )
                    if kanji:
                        diff_rows_html += f'<span class="diff-kanji">({kanji})</span>'
                    if designer:
                        diff_rows_html += f'<span class="diff-designer">{designer}</span>'
                    if note_str:
                        diff_rows_html += f'<span class="diff-notes">Notes: {note_str}</span>'
                    diff_rows_html += "</div>"

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:28px 32px 14px 32px}}
.header{{margin-bottom:24px}}
.header .type-badge{{font-size:13px;color:#8888b0;margin-right:10px;vertical-align:middle}}
.header .title{{font-size:22px;color:#e8e8f0;font-weight:600;vertical-align:middle;letter-spacing:1px}}
.header .id{{font-size:13px;color:#6868a0;margin-top:6px}}
.body2{{display:flex;gap:28px;margin-top:20px}}
.cover2{{flex-shrink:0;width:200px;height:200px;border-radius:10px;overflow:hidden;border:2px solid #444460;box-shadow:0 2px 10px rgba(0,0,0,.3)}}
.cover2 img{{width:100%;height:100%;object-fit:cover}}
.info{{flex:1;display:flex;flex-direction:column;gap:10px}}
.info .row{{font-size:15px;color:#c8c8d8}}
.info .row .label{{color:#7878a8;margin-right:8px}}
.info .ds{{font-size:14px;color:#9090b8;line-height:1.8}}
.aliases{{margin-top:22px;padding-top:14px;border-top:1px solid #333350;font-size:13px;color:#7878a0}}
.diff-section{{margin-top:14px}}
.diff-section .sec-label{{font-size:14px;color:#9090b8;margin-bottom:6px}}
.diff-row{{font-size:12px;color:#a0a0c0;padding:2px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.diff-type{{color:#6868a0;font-size:11px;min-width:28px}}
.diff-lvl{{color:#c8c8d8;font-weight:600;min-width:80px}}
.diff-kanji{{color:#9090b8;font-size:11px}}
.diff-designer{{color:#7878a0;font-size:11px}}
.diff-notes{{color:#707098;font-size:11px}}
.footer-bar{{display:flex;align-items:center;margin-top:18px;padding-top:10px;border-top:1px solid #333350;font-size:12px}}
.footer-source{{color:#7878a8;flex:1;text-align:left}}
.footer-mai{{color:#585878;flex:1;text-align:right}}
</style></head>
<body>
<div class="header">
<div><span class="type-badge">{_html.escape(tp)}</span><span class="title">{_html.escape(title)}</span></div>
<div class="id">ID: {_html.escape(sid)}</div>
</div>
<div class="body2">
<div class="cover2"><img src="data:image/png;base64,{cover_b64}" /></div>
<div class="info">
<div class="row"><span class="label">作者</span>{_html.escape(artist)}</div>
<div class="row"><span class="label">BPM</span>{_html.escape(str(bpm))}</div>
<div class="row"><span class="label">分类</span>{genre_display}</div>
<div class="row"><span class="label">版本</span>{version_display}</div>
{map_row}
<div class="ds">定数: {_html.escape(ds_str)}</div>
</div>
</div>
<div class="diff-section">
<div class="sec-label">谱面详情</div>
{diff_rows_html}
</div>
<div class="aliases">别称: {_html.escape(alias_text)}</div>
<div class="footer-bar">
<span class="footer-source">{'数据来源: lxns + diving-fish' if extra else '数据来源: diving-fish'}</span>
<span class="footer-mai">MaiBot</span>
</div>
</body></html>"""

        return await self._render_html_to_png(html, width=680, height=100, wait_for_images=True)

    async def _render_my_image(
        self, username: str, nickname: str, rating: int,
        additional_rating: int, plate: str, records: list[dict],
    ) -> str:
        seen_sd: set[str] = set()
        seen_dx: set[str] = set()
        best_per_song: dict[str, dict] = {}
        for r in records:
            sid = str(r.get("song_id", "") or "")
            if not sid:
                continue
            tp = r.get("type", "SD")
            ra = r.get("ra", 0)
            if tp == "SD":
                seen_sd.add(sid)
            else:
                seen_dx.add(sid)
            if sid not in best_per_song or ra > best_per_song[sid]["ra"]:
                best_per_song[sid] = {"level_index": r.get("level_index", 0),
                                        "ra": ra, "record": r}

        total = len(best_per_song)
        sd_count = len(seen_sd)
        dx_count = len(seen_dx)

        diff_names = ["Basic", "Advanced", "Expert", "Master", "Re:Master"]
        diff_counts = [0, 0, 0, 0, 0]
        for info in best_per_song.values():
            li = info["level_index"]
            if 0 <= li < 5:
                diff_counts[li] += 1

        top_items = sorted(best_per_song.values(), key=lambda x: x["ra"], reverse=True)[:10]
        top_rows = "".join(
            f'<tr><td class="td-rank">#{i+1}</td>'
            f'<td class="td-title">{_html.escape(str(x["record"].get("title","") or "?"))}</td>'
            f'<td class="td-lvl">{_html.escape(str(x["record"].get("level","") or "?"))}</td>'
            f'<td class="td-ach">{x["record"].get("achievements",0):.4f}%</td>'
            f'<td class="td-ra">{x["ra"]}</td></tr>'
            for i, x in enumerate(top_items)
        )

        diff_rows = "".join(
            f'<div class="diff-row"><span class="diff-name">{diff_names[i]}</span>'
            f'<span class="diff-bar"><span class="diff-fill" style="width:{min(diff_counts[i]*100//max(total,1),100)}%"></span></span>'
            f'<span class="diff-cnt">{diff_counts[i]}</span></div>'
            for i in range(5)
        )

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
.header{{text-align:center;margin-bottom:20px}}
.header .nick{{font-size:24px;color:#e8e8f0;font-weight:600;letter-spacing:2px}}
.header .user{{font-size:14px;color:#7878a8;margin-top:4px}}
.rating{{text-align:center;margin:16px 0}}
.rating .val{{font-size:42px;font-weight:700;color:#f0c060}}
.rating .label{{font-size:13px;color:#8888a8}}
.stats{{display:flex;gap:20px;justify-content:center;margin:16px 0;flex-wrap:wrap}}
.stat-box{{background:#24243a;border-radius:8px;padding:14px 20px;text-align:center;min-width:80px;box-shadow:0 2px 6px rgba(0,0,0,.2)}}
.stat-box .s-val{{font-size:22px;font-weight:600;color:#e4e4f0}}
.stat-box .s-label{{font-size:11px;color:#7878a8;margin-top:2px}}
.section-title{{font-size:16px;color:#c0c0d8;font-weight:600;margin:18px 0 10px;padding-bottom:4px;border-bottom:1px solid #333350}}
.diff-row{{display:flex;align-items:center;gap:10px;margin:6px 0}}
.diff-name{{width:80px;font-size:13px;color:#a0a0c0;text-align:right}}
.diff-bar{{flex:1;height:12px;background:#2a2a42;border-radius:6px;overflow:hidden}}
.diff-fill{{height:100%;background:linear-gradient(90deg,#5b8fd4,#9b59b6);border-radius:6px;transition:width .3s}}
.diff-cnt{{width:36px;font-size:13px;color:#8888a8;text-align:right}}
.table{{width:100%;border-collapse:collapse;margin-top:6px}}
.table th{{font-size:12px;color:#7878a8;padding:4px 6px;text-align:left;border-bottom:1px solid #2a2a42}}
.table td{{font-size:13px;color:#c0c0d0;padding:3px 6px}}
.td-rank{{width:32px;color:#6868a0}}
.td-title{{max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.td-lvl{{width:52px}}
.td-ach{{width:80px;color:#f0d060}}
.td-ra{{width:52px;color:#c0c0d4;text-align:right}}
</style></head>
<body>
<div class="header">
<div class="nick">{_html.escape(nickname or username)}</div>
<div class="user">@{_html.escape(username)}</div>
</div>
<div class="rating">
<div class="val">{rating}</div>
<div class="label">DX Rating</div>
</div>
<div class="stats">
<div class="stat-box"><div class="s-val">{_html.escape(str(plate or "-"))}</div><div class="s-label">牌子</div></div>
<div class="stat-box"><div class="s-val">{additional_rating}</div><div class="s-label">段位</div></div>
<div class="stat-box"><div class="s-val">{total}</div><div class="s-label">总成绩数</div></div>
<div class="stat-box"><div class="s-val">{sd_count}</div><div class="s-label">SD 曲目</div></div>
<div class="stat-box"><div class="s-val">{dx_count}</div><div class="s-label">DX 曲目</div></div>
</div>
<div class="section-title">难度分布</div>
{diff_rows}
<div class="section-title">Top 10 成绩</div>
<table class="table">
<tr><th>#</th><th>曲目</th><th>难度</th><th>达成率</th><th>RA</th></tr>
{top_rows}
</table>
<div style="text-align:right;margin-top:16px;font-size:12px;color:#585878">数据来源: diving-fish &middot; MaiBot</div>
</body></html>"""
        return await self._render_html_to_png(html, width=680, height=600)

    @staticmethod
    def _get_cover_url(song_id: str) -> str:
        sid = int(song_id)
        if 10001 <= sid <= 11000:
            padded = str(sid - 10000).zfill(5)
        else:
            padded = str(sid).zfill(5)
        return f"https://www.diving-fish.com/covers/{padded}.png"

    async def _download_cover_base64(self, song_id: str) -> Optional[str]:
        client = await self._get_client()
        if not client:
            return None
        session = client._session
        sid = int(song_id)

        lxns_client = await self._get_lxns_client()
        if lxns_client:
            lxns_url = LxnsApiClient.get_cover_url(
                self.config.lxns.asset_url, sid,
            )
            for attempt in range(3):
                try:
                    async with session.get(
                        lxns_url, timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            return base64.b64encode(data).decode()
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(0.5)

        url = self._get_cover_url(song_id)
        for attempt in range(3):
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return base64.b64encode(data).decode()
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(0.5)
        logger.debug(f"封面下载失败 (lxns + diving-fish 双源): song_id={song_id}")
        return None

    KEY_LABELS = {
        "type": "类型", "genre": "分类", "version": "版本",
        "artist": "作者", "bpm": "BPM", "title": "曲名",
        "level": "难度", "ds": "定数", "from": "版本",
        "is_new": "新曲", "name": "曲名", "song_id": "歌曲ID",
    }

    _VAL_TRANSLATIONS = {
        "higher": "↑ 更高", "lower": "↓ 更低", "equal": "= 相同",
        "close": "≈ 接近", "far": "↔ 较远", "very_close": "≈≈ 极近",
        "match": "✓ 匹配", "mismatch": "✗ 不匹配",
        "true": "✓", "false": "✗",
        "exact": "✓✓ 精确",
    }

    @staticmethod
    def _fmt_val(v: Any) -> str:
        if isinstance(v, str):
            return MaiMaiDXPlugin._VAL_TRANSLATIONS.get(v.lower(), v)
        if isinstance(v, bool):
            return "✓" if v else "✗"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, dict):
            return " ".join(f"{k}={MaiMaiDXPlugin._fmt_val(sv)}" for k, sv in v.items())
        if isinstance(v, (list, tuple)):
            return "[ " + " | ".join(MaiMaiDXPlugin._fmt_val(sv) for sv in v) + " ]"
        return str(v) if v is not None else "-"

    @staticmethod
    def _format_maidle_test(test: Any) -> str:
        if isinstance(test, bool):
            return "🎯 正确!" if test else "❌ 不正确"
        if isinstance(test, dict):
            parts = []
            for k, v in test.items():
                label = MaiMaiDXPlugin.KEY_LABELS.get(k, k)
                val = MaiMaiDXPlugin._fmt_val(v)
                parts.append(f"{label}: {val}")
            return "\n".join(parts) if parts else "(无数据)"
        if isinstance(test, list):
            return "\n".join(MaiMaiDXPlugin._fmt_val(v) for v in test)
        return str(test) if test is not None else ""

    async def _render_maidle_image(self, guess_id: int, test: dict) -> str:
        clues = self._format_maidle_test(test)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
.header{{text-align:center;margin-bottom:20px}}
.header h2{{font-size:20px;color:#e8e8f0;letter-spacing:2px;margin-bottom:4px}}
.header .guess{{font-size:14px;color:#7878a8}}
.sep{{border-top:1px solid #333350;margin:18px 0}}
.clues{{font-size:15px;color:#c8c8d8;line-height:1.8;padding:8px 16px;background:#24243a;border-radius:8px;white-space:pre-wrap}}
.tips{{margin-top:18px;font-size:13px;color:#6868a0;text-align:center}}
</style></head>
<body>
<div class="header">
<h2>Maidle 猜歌</h2>
<div class="guess">猜测: ID.{guess_id}</div>
</div>
<div class="sep"></div>
<div class="clues">{_html.escape(clues)}</div>
<div class="tips">继续: /mai maidle guess &lt;ID&gt;  |  放弃: /mai maidle answer</div>
<div style="text-align:right;margin-top:16px;font-size:12px;color:#585878">MaiBot</div>
</body></html>"""
        return await self._render_html_to_png(html, width=480, height=400)

    async def _render_maidle_answer_image(self, title: str, artist: str,
                                          sid: str, cover_b64: str) -> str:
        cover_html = (
            f'<div class="cover"><img src="data:image/png;base64,{cover_b64}" /></div>'
            if cover_b64 else ""
        )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
.header{{text-align:center;margin-bottom:22px}}
.header h2{{font-size:20px;color:#e8e8f0;letter-spacing:2px}}
.body2{{display:flex;gap:24px;align-items:flex-start}}
.cover{{flex-shrink:0;width:160px;height:160px;border-radius:10px;overflow:hidden;border:2px solid #444460;box-shadow:0 2px 10px rgba(0,0,0,.3)}}
.cover img{{width:100%;height:100%;object-fit:cover}}
.info{{flex:1;display:flex;flex-direction:column;gap:8px;padding-top:4px}}
.info .song{{font-size:20px;color:#e4e4f0;font-weight:600;letter-spacing:1px}}
.info .artist{{font-size:15px;color:#a0a0c0}}
.info .sid{{font-size:13px;color:#6868a0}}
.footer{{margin-top:22px;text-align:center;font-size:13px;color:#6868a0}}
</style></head>
<body>
<div class="header"><h2>Maidle 答案</h2></div>
<div class="body2">
{cover_html}
<div class="info">
<div class="song">{_html.escape(title)}</div>
<div class="artist">{_html.escape(artist)}</div>
<div class="sid">ID: {_html.escape(sid)}</div>
</div>
</div>
<div class="footer">使用 /mai maidle 开始新游戏</div>
<div style="text-align:right;margin-top:16px;font-size:12px;color:#585878">MaiBot</div>
</body></html>"""
        return await self._render_html_to_png(
            html, width=560, height=350,
            wait_for_images=bool(cover_b64),
        )

    def _format_music_summary(self, music: dict) -> str:
        sid = str(music.get("id", "") or "?")
        title = str(music.get("title", "") or "?")
        tp = str(music.get("type", "") or "?")
        bi = music.get("basic_info", {})
        artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
        version = str(bi.get("from", "") or "?") if isinstance(bi, dict) else "?"
        ds_list = music.get("ds", [])
        max_ds = max(ds_list) if ds_list else 0
        return f"[{tp}] {title} — {artist}  |  ID: {sid}  |  {version}  |  定数: {max_ds}"

    async def _render_help_image(self) -> str:
        sections = [
            ("基础功能 (/mai)",
             [("/mai song <关键词>", "搜索曲目，ID 直接查看详情"),
              ("/mai today", "今日运势 — 随机推荐歌曲"),
              ("/mai maidle", "猜歌游戏 (Maidle)"),
              ("/mai charts", "全谱面难度分布统计"),
              ("/mai status", "服务器状态检测 (双服)"),
              ("/mai pick <A> <B> [C] [D]", "随机帮你选一个"),
              ("/mai help", "显示本帮助")]),
            ("别称管理 (/mai alias)",
             [("/mai alias add <ID> <名称>", "添加别称"),
              ("/mai alias del <ID> <名称>", "删除别称"),
              ("/mai alias list <ID>", "查看别称")]),
            ("水鱼查分 (/mai df)",
             [("/mai df help", "水鱼命令帮助"),
              ("/mai df b50 [用户]", "生成 Best 50 成绩图片"),
              ("/mai df my", "查看个人成绩摘要"),
              ("/mai df bind <Token>", "绑定成绩导入 Token"),
              ("/mai df unbind", "解除绑定")]),
            ("lxns 查分 (/mai lxns)",
             [("/mai lxns help", "lxns 命令帮助 (含公开/需JWT)"),
              ("/mai lxns bind <Token>", "绑定 lxns Token"),
              ("/mai lxns unbind", "解除绑定")]),
        ]
        sec_html_parts = []
        for label, cmds in sections:
            items = "".join(
                f'<div class="cmd"><span class="cmd-name">{_html.escape(c[0])}</span><span class="cmd-desc">{_html.escape(c[1])}</span></div>'
                for c in cmds
            )
            sec_html_parts.append(
                f'<div class="section"><div class="sec-label">{_html.escape(label)}</div>{items}</div>'
            )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:36px 48px}}
.header{{text-align:center;margin-bottom:30px}}
.header h2{{font-size:40px;color:#e8e8f0;letter-spacing:4px;margin-bottom:8px}}
.header .sub{{font-size:18px;color:#7878a8}}
.section{{margin-bottom:24px}}
.sec-label{{font-size:24px;color:#c0c0d8;font-weight:600;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #2e2e48}}
.cmd{{display:flex;padding:8px 0}}
.cmd-name{{flex-shrink:0;width:380px;font-size:22px;color:#5b8fd4;font-family:'Consolas','Courier New',monospace}}
.cmd-desc{{font-size:22px;color:#9090b8}}
.footer-bar{{display:flex;margin-top:20px;padding-top:10px;border-top:1px solid #333350;font-size:14px}}
.footer-source{{color:#7878a8;flex:1}}
.footer-mai{{color:#585878;text-align:right}}
</style></head>
<body>
<div class="header">
<h2>MaiMai DX 查分器</h2>
<div class="sub">diving-fish + lxns 双源 · /mai /mai df /mai lxns</div>
</div>
{''.join(sec_html_parts)}
<div class="footer-bar">
<span class="footer-source">数据来源: diving-fish + lxns</span>
<span class="footer-mai">MaiBot</span>
</div>
</body></html>"""
        return await self._render_html_to_png(html, width=1060, height=760)

    async def _render_df_help_image(self) -> str:
        sections = [
            ("查分",
             [("/mai df b50 [用户]", "生成 Best 50 成绩图片"),
              ("/mai df my", "查看个人成绩摘要 (需绑定)")]),
            ("管理",
             [("/mai df bind <Token>", "绑定水鱼查分器的成绩导入 Token"),
              ("/mai df unbind", "解除账号绑定")]),
            ("说明",
             [("Token 获取", "diving-fish 网站 → personal page → 成绩导入Token"),
              ("B50 不填参数", "使用已绑定账号查询"),
              ("B50 填用户名/QQ", "查询他人公开成绩")]),
        ]
        sec_html_parts = []
        for label, cmds in sections:
            items = "".join(
                f'<div class="cmd"><span class="cmd-name">{_html.escape(c[0])}</span><span class="cmd-desc">{_html.escape(c[1])}</span></div>'
                for c in cmds
            )
            sec_html_parts.append(
                f'<div class="section"><div class="sec-label">{_html.escape(label)}</div>{items}</div>'
            )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:36px 48px}}
.header{{text-align:center;margin-bottom:36px}}
.header h2{{font-size:42px;color:#e8e8f0;letter-spacing:4px;margin-bottom:8px}}
.header .sub{{font-size:18px;color:#7878a8}}
.section{{margin-bottom:28px}}
.sec-label{{font-size:26px;color:#c0c0d8;font-weight:600;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #2e2e48}}
.cmd{{display:flex;padding:10px 0}}
.cmd-name{{flex-shrink:0;width:400px;font-size:24px;color:#5b8fd4;font-family:'Consolas','Courier New',monospace}}
.cmd-desc{{font-size:24px;color:#9090b8}}
.footer-bar{{display:flex;margin-top:24px;padding-top:10px;border-top:1px solid #333350;font-size:14px}}
.footer-source{{color:#7878a8;flex:1}}
.footer-mai{{color:#585878;text-align:right}}
</style></head>
<body>
<div class="header">
<h2>MaiMai DX / diving-fish</h2>
<div class="sub">水鱼查分器 · 命令帮助</div>
</div>
{''.join(sec_html_parts)}
<div class="footer-bar">
<span class="footer-source">数据来源: diving-fish</span>
<span class="footer-mai">MaiBot</span>
</div>
</body></html>"""
        return await self._render_html_to_png(html, width=1060, height=720)

    async def _render_b50_image(
        self, charts: dict, username: str, nickname: str, rating: int,
        query_time: str = "", blessing: str = "",
    ) -> str:
        sd = charts.get("sd", [])
        dx = charts.get("dx", [])
        total_ra = rating

        diff_colors = {
            0: ("#4caf50", "#162316"),
            1: ("#e0b040", "#262016"),
            2: ("#e05050", "#261816"),
            3: ("#9b59b6", "#1c1626"),
            4: ("#a0a0d0", "#1a1a28"),
        }

        def _cards_html(recs: list[dict], section_label: str) -> str:
            parts = [
                f'<div class="section-title">{section_label}  ({len(recs)} 首)</div>'
                '<div class="grid">'
            ]
            for i, r in enumerate(recs):
                title = r.get("title", "???")
                level = r.get("level", "?")
                tp = r.get("type", "SD")
                li = r.get("level_index", 2)
                song_id = r.get("song_id", 0)
                achievements = r.get("achievements", 0)
                ra_val = r.get("ra", 0)
                rate = RATE_DISPLAY.get(r.get("rate", ""), r.get("rate", "-"))
                fc = FC_DISPLAY.get(r.get("fc", ""), r.get("fc", "-"))
                ds_val = r.get("ds", 0)
                border_color, bg_color = diff_colors.get(
                    li, diff_colors[2]
                )
                cover_url = self._get_cover_url(str(song_id))
                parts.append(
                    f'<div class="card" style="border-left-color:{border_color};background:{bg_color}">'
                    f'<div class="tl">'
                    f'<div class="rank">#{i + 1}</div>'
                    f'<div class="type-badge">{_html.escape(str(tp))}</div>'
                    f'<div class="level">Lv.{_html.escape(str(level))}</div>'
                    f'</div>'
                    f'<div class="tr">'
                    f'<div class="title">{_html.escape(str(title))}</div>'
                    f'<div class="achievements">{achievements:.4f}</div>'
                    f'</div>'
                    f'<div class="bl">'
                    f'<div class="ra">RA:{ra_val}</div>'
                    f'<div class="meta">{_html.escape(rate)} | {_html.escape(fc)} | DS:{ds_val}</div>'
                    f'</div>'
                    f'<div class="br">'
                    f'<img class="cover" src="{cover_url}" onerror="this.style.display=\'none\'" />'
                    f'</div>'
                    f'</div>'
                )
            parts.append("</div>")
            return "".join(parts)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:36px 48px 18px 48px}}
.header{{text-align:center;margin-bottom:40px}}
.header h2{{font-size:44px;color:#e8e8f0;margin-bottom:6px;letter-spacing:3px}}
.header .sub{{font-size:20px;color:#8888a8}}
.header .total{{font-size:32px;color:#f0c060;margin-top:10px;font-weight:600}}
.section-title{{font-size:28px;color:#d0d0e0;margin:30px 0 18px;padding-bottom:8px;border-bottom:1px solid #333350}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:18px}}
.card{{display:grid;grid-template-columns:105px 1fr;grid-template-rows:auto auto;gap:6px 8px;padding:14px 16px 14px 14px;border-radius:10px;border-left:5px solid;min-height:280px;box-shadow:0 2px 8px rgba(0,0,0,.3)}}
.tl{{display:flex;flex-direction:column;gap:3px;align-items:flex-start}}
.tr{{display:flex;flex-direction:column;gap:6px;overflow:hidden;padding-right:2px}}
.bl{{display:flex;flex-direction:column;gap:4px;justify-content:center}}
.br{{display:flex;align-items:center;justify-content:center}}
.rank{{font-size:21px;color:#6868a0}}
.title{{font-size:22px;color:#e4e4f0;font-weight:600;min-height:60px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:break-word}}
.cover{{width:130px;height:130px;border-radius:6px;object-fit:cover;opacity:0.92;box-shadow:0 2px 6px rgba(0,0,0,.4)}}
.type-badge{{font-size:17px;color:#8888b0}}
.level{{font-size:21px;color:#9090b8}}
.achievements{{font-size:28px;color:#f0d060;font-weight:700}}
.ra{{font-size:25px;color:#c0c0d4}}
.meta{{font-size:19px;color:#7878a0}}
.footer-bar{{display:flex;align-items:center;margin-top:44px;padding-top:18px;border-top:1px solid #333350;font-size:20px}}
.footer-time{{color:#7878a8;flex:1;text-align:left}}
.mai-bot{{font-size:13px;color:#585878;flex:1;text-align:center}}
.blessing{{color:#c0c0d8;flex:1;text-align:right}}
</style></head>
<body>
<div class="header">
<h2>MaiMai DX / Best 50</h2>
<div class="sub">{_html.escape(nickname)}  (@{_html.escape(username)})</div>
<div class="total">DX Rating: {total_ra}</div>
</div>
{_cards_html(sd, "B35 / 旧曲")}
{_cards_html(dx, "B15 / 新曲")}
<div class="footer-bar">
<span class="footer-time">查询时间: {_html.escape(query_time)}</span>
<span class="footer-source">数据来源: diving-fish</span>
<span class="blessing">{_html.escape(blessing)}</span>
</div>
</body></html>"""

        sd_rows = (len(sd) + 4) // 5 if sd else 0
        dx_rows = (len(dx) + 4) // 5 if dx else 0
        total_rows = sd_rows + dx_rows
        card_h = 280
        header_h = 175
        section_h = 55
        row_gap = 18
        pad = 36
        height = header_h + section_h * 2 + total_rows * card_h + (total_rows - 2) * row_gap + pad * 2 + 100

        return await self._render_html_to_png(
            html, width=1600, height=height, wait_for_images=True, image_timeout=30000,
        )

    # ---- 今日运势图片渲染 ----

    async def _render_today_image(
        self, rp: int, yi_parts: list[str], ji_parts: list[str],
        music: dict, cover_b64: str, blessing: str = "",
    ) -> str:
        title = str(music.get("title", "") or "???")
        sid = str(music.get("id", "") or "???")
        tp = str(music.get("type", "") or "?")
        bi = music.get("basic_info", {})
        artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
        ds_list = music.get("ds", [])
        level_list = music.get("level", [])
        diffs_parts = [f"{lvl}({ds})" for lvl, ds in zip(level_list, ds_list)]
        ds_str = " / ".join(diffs_parts)

        yi_text = ", ".join(yi_parts) if yi_parts else "无"
        ji_text = ", ".join(ji_parts) if ji_parts else "无"

        rp_color = "#e06060" if rp < 30 else "#f0c860" if rp < 70 else "#60c060"

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:36px 48px}}
.header{{text-align:center;margin-bottom:40px}}
.header h2{{font-size:36px;color:#d0d0e0;margin-bottom:14px;letter-spacing:3px}}
.header .rp{{font-size:64px;font-weight:700;color:{rp_color}}}
.section{{margin:28px 0}}
.section .label{{font-size:20px;color:#8888a8;margin-bottom:6px}}
.section .value{{font-size:22px;color:#c8c8d8}}
.sep{{border-top:1px solid #333350;margin:32px 0}}
.rec{{display:flex;gap:32px;align-items:flex-start}}
.rec .cover{{flex-shrink:0;width:220px;height:220px;border-radius:10px;overflow:hidden;border:2px solid #444460;box-shadow:0 2px 8px rgba(0,0,0,.3)}}
.rec .cover img{{width:100%;height:100%;object-fit:cover}}
.rec .info{{flex:1;display:flex;flex-direction:column;gap:12px;padding-top:6px}}
.rec .info .song{{font-size:26px;color:#e4e4f0;font-weight:600}}
.rec .info .artist{{font-size:20px;color:#a0a0c0}}
.rec .info .type-badge{{font-size:15px;color:#8888b0;width:fit-content}}
.rec .info .ds{{font-size:18px;color:#8080a8}}
.footer{{margin-top:34px;text-align:center;font-size:17px;color:#6868a0}}
</style></head>
<body>
<div class="header">
<h2>今日运势</h2>
<div class="rp">{rp}</div>
</div>
<div class="section">
<div class="label">宜</div><div class="value">{_html.escape(yi_text)}</div>
</div>
<div class="section">
<div class="label">忌</div><div class="value">{_html.escape(ji_text)}</div>
</div>
<div class="sep"></div>
<div class="rec">
<div class="cover"><img src="data:image/png;base64,{cover_b64}" /></div>
<div class="info">
<div class="song">{_html.escape(title)}</div>
<div class="artist">{_html.escape(artist)}</div>
<div><span class="type-badge">{_html.escape(tp)}</span></div>
<div class="ds">定数: {ds_str}</div>
<div style="font-size:15px;color:#6868a0">ID: {_html.escape(sid)}</div>
</div>
</div>
<div class="footer">{_html.escape(blessing)}</div>
<div style="text-align:right;margin-top:12px;font-size:12px;color:#585878">数据来源: diving-fish &middot; MaiBot</div>
</body></html>"""

        return await self._render_html_to_png(
            html, width=880, height=760, wait_for_images=True,
        )

    async def _render_maidle_help_image(self) -> str:
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{width:520px;padding:32px}}
h2{{font-size:20px;color:#e8e8f0;text-align:center;letter-spacing:2px;margin-bottom:16px}}
p{font-size:14px;color:#c0c0d0;line-height:1.7;margin-bottom:12px}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.legend span{font-size:13px;background:#24243a;padding:3px 10px;border-radius:4px;color:#c8c8d8}
.legend .hl{color:#5b8fd4}
.sep{border-top:1px solid #333350;margin:16px 0}
.cmds{font-size:13px;color:#9090b8;line-height:2;text-align:center}
</style></head>
<body>
<h2>Maidle 猜歌说明</h2>
<p>系统从曲库中随机选取一首隐藏歌曲，玩家通过不断输入歌曲 ID 进行猜测。每次猜测后，系统会返回线索，指示猜测曲目与目标曲目的属性差异。</p>
<div class="legend">
<span class="hl">&#10003; 匹配</span><span>&#10007; 不匹配</span>
<span>&#8593; 更高</span><span>&#8595; 更低</span>
<span>&#8776; 接近</span><span>&#8596; 较远</span>
</div>
<p>推测属性可能包括：类型(SD/DX)、分类、版本、作者、BPM 等。通过不断缩小范围，最终找到目标歌曲!</p>
<div class="sep"></div>
<div class="cmds">
开始游戏: /mai maidle<br/>
提交猜测: /mai maidle guess &lt;歌曲ID&gt;<br/>
查看答案: /mai maidle answer
</div>
<div style="text-align:right;margin-top:16px;font-size:12px;color:#585878">MaiBot</div>
</body></html>"""
        return await self._render_html_to_png(html, width=520, height=400)

    async def _cleanup_maidle_sessions(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)
                now = time.time()
                async with self._maidle_sessions_lock:
                    expired = [
                        uid for uid, s in self._maidle_sessions.items()
                        if now - s["started_at"] > 900
                    ]
                    for uid in expired:
                        del self._maidle_sessions[uid]
                    if expired:
                        logger.debug(f"清理 {len(expired)} 个过期 maidle session")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("maidle session 清理异常", exc_info=True)

    # ---- Commands ----

    @Command(
        "mai_help",
        description="MaiMai DX 查分器帮助",
        pattern=r"^/mai(\s+(help|帮助))?$",
    )
    async def handle_help(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        try:
            img_b64 = await self._render_help_image()
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"帮助图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"帮助图片生成失败: {e}", stream_id)
            return False, "渲染失败", True
        return True, "显示帮助", True

    @Command(
        "mai_df_help",
        description="水鱼查分器帮助",
        pattern=r"^/mai df(\s+(help|帮助))?$",
    )
    async def handle_df_help(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        try:
            img_b64 = await self._render_df_help_image()
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"水鱼帮助图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
            return False, "渲染失败", True
        return True, "显示水鱼帮助", True

    @Command(
        "mai_pick",
        description="随机选择 — 帮你在 2~4 个选项中做决定",
        pattern=r"^/mai (pick|choose|选|选择)\s+(?P<options>.+)$",
    )
    async def handle_pick(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("options"):
            await self.ctx.send.text("用法: /mai pick <选项1> <选项2> [选项3] [选项4]", stream_id)
            return False, "参数错误", True
        raw = matched_groups["options"].strip()
        opts = raw.split()
        if len(opts) < 2:
            await self.ctx.send.text("至少需要 2 个选项，用空格分隔", stream_id)
            return False, "选项不足", True
        if len(opts) > 4:
            opts = opts[:4]
        opts = [o for o in opts if 1 <= len(o) <= 10]
        if len(opts) < 2:
            await self.ctx.send.text("每个选项 1~10 字，请重新输入", stream_id)
            return False, "选项无效", True
        chosen = random.choice(opts)
        display = "  ·  ".join(opts)
        await self.ctx.send.text(
            f"【帮你选】\n{display}\n\n→ 就决定是「{_html.escape(chosen)}」了！", stream_id,
        )
        return True, "随机选择", True

    @Command(
        "mai_b50",
        description="查询舞萌 DX Best 50 成绩，生成图片",
        pattern=r"^/mai df b50(\s+(?P<target>.+))?$",
    )
    async def handle_b50(
        self,
        stream_id: str = "",
        matched_groups: dict = None,
        **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))

        target = ""
        if matched_groups and matched_groups.get("target"):
            target = matched_groups["target"].strip()

        if not target:
            binding = await self._get_binding(kwargs)
            if not binding:
                await self.ctx.send.text(
                    "未提供查询目标，且未绑定账号。\n"
                     "用法: /mai df b50 <用户名或QQ>\n"
                     "或先绑定: /mai df bind <Token>",
                    stream_id,
                )
                return False, "无目标", True
            target = binding["username"]

        client = await self._get_client()
        resp = await client.query_player(target)
        if self._is_error(resp):
            status = resp.get("_status", 0)
            msg = self._error_msg(resp)
            if status == 403:
                await self.ctx.send.text(
                    f"查询被拒绝: {target} 已设置隐私或未同意用户协议", stream_id
                )
            elif status == 400 and "not exists" in msg.lower():
                await self.ctx.send.text(f"用户不存在: {target}", stream_id)
            else:
                await self.ctx.send.text(f"查询失败: {msg}", stream_id)
            return False, "查询失败", True

        charts = resp.get("charts", {})
        if not charts or (not charts.get("sd") and not charts.get("dx")):
            await self.ctx.send.text(f"{target} 暂无成绩记录", stream_id)
            return False, "无记录", True

        nickname = resp.get("nickname", target)
        rating = resp.get("rating", 0)
        username = resp.get("username", target)
        plate = resp.get("plate", "")

        await self.ctx.send.text("正在生成 B50 图片，请稍候...", stream_id)

        query_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        blessing = random.choice(self._BLESSINGS)

        try:
            img_b64 = await self._render_b50_image(
                charts, username, nickname, rating,
                query_time=query_time_str, blessing=blessing,
            )
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"B50 图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
            return False, "渲染失败", True

        await self.ctx.send.image(img_b64, stream_id)
        return True, "发送B50图片", True

    @Command(
        "mai_song",
        description="搜索舞萌 DX 曲目",
        pattern=r"^/mai song\s+(?P<keyword>.+)$",
    )
    async def handle_song(
        self,
        stream_id: str = "",
        matched_groups: dict = None,
        **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("keyword"):
            await self.ctx.send.text("用法: /mai song <关键词或歌曲ID>", stream_id)
            return False, "参数错误", True

        keyword = matched_groups["keyword"].strip()
        if not keyword:
            await self.ctx.send.text("请输入搜索关键词或歌曲ID", stream_id)
            return False, "参数为空", True

        songs = await self._get_songs_cached()
        if not songs:
            await self.ctx.send.text("获取曲目列表失败，请稍后重试", stream_id)
            return False, "获取失败", True

        if keyword.isdigit():
            for music in songs:
                if isinstance(music, dict) and str(music.get("id", "") or "") == keyword:
                    sid = str(music.get("id", ""))
                    cover_b64 = await self._download_cover_base64(sid)
                    if cover_b64:
                        await self.ctx.send.text("正在生成详情图片...", stream_id)
                        try:
                            img_b64 = await self._render_song_detail_image(music, cover_b64)
                            await self.ctx.send.image(img_b64, stream_id)
                            return True, "显示详情", True
                        except RuntimeError:
                            await self.ctx.send.text("图片渲染失败，请确认已安装 playwright", stream_id)
                            return False, "渲染失败", True
                        except Exception:
                            logger.debug("曲目详情图片渲染失败，回退到文本模式", exc_info=True)
                    detail = await self._build_song_detail_text(music)
                    await self.ctx.send.text(detail, stream_id)
                    return True, "显示详情", True

        matches = await self._match_songs(keyword)
        if not matches:
            await self.ctx.send.text(
                f"未找到匹配的曲目: \"{keyword}\"\n"
                "可使用部分关键词、作者名或别称搜索",
                stream_id,
            )
            return False, "无匹配", True

        limit = min(len(matches), 15)
        matches = matches[:limit]

        if len(matches) == 1:
            music = matches[0]
            sid = str(music.get("id", "") or "")
            cover_b64 = await self._download_cover_base64(sid)
            if cover_b64:
                await self.ctx.send.text("正在生成详情图片...", stream_id)
                try:
                    img_b64 = await self._render_song_detail_image(music, cover_b64)
                    await self.ctx.send.image(img_b64, stream_id)
                    return True, "显示详情", True
                except RuntimeError:
                    await self.ctx.send.text("图片渲染失败，请确认已安装 playwright", stream_id)
                    return False, "渲染失败", True
                except Exception:
                    logger.debug("曲目详情图片渲染失败，回退到文本模式", exc_info=True)
            detail = await self._build_song_detail_text(music)
            await self.ctx.send.text(detail, stream_id)
            return True, "显示详情", True

        if len(matches) <= 5:
            lines = [f"搜索 \"{keyword}\" ({len(matches)} 条):"]
            for m in matches:
                lines.append("  " + self._format_music_summary(m))
            await self.ctx.send.text("\n".join(lines), stream_id)
        else:
            nodes: list[dict] = [
                {
                    "user_id": "0",
                    "nickname": f"搜索 \"{keyword}\" ({len(matches)} 条)",
                    "segments": [
                        {
                            "type": "text",
                            "content": "使用 /mai song <ID> 查看详情",
                        }
                    ],
                }
            ]
            for idx, m in enumerate(matches, 1):
                sid = str(m.get("id", "") or "?")
                title = str(m.get("title", "") or "?")
                tp = str(m.get("type", "") or "?")
                bi = m.get("basic_info", {})
                artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
                version = str(bi.get("from", "") or "?") if isinstance(bi, dict) else "?"
                ds_list = m.get("ds", [])
                max_ds = max(ds_list) if ds_list else 0
                nodes.append(
                    {
                        "user_id": "0",
                        "nickname": f"#{idx} [{_html.escape(tp)}] {_html.escape(title)}",
                        "segments": [
                            {
                                "type": "text",
                                "content": (
                                    f"{_html.escape(artist)} | ID:{_html.escape(sid)} | {_html.escape(version)}\n"
                                    f"max DS: {max_ds}"
                                ),
                            }
                        ],
                    }
                )
            await self.ctx.send.forward(nodes, stream_id)
        return True, "搜索完成", True

    @Command(
        "mai_charts",
        description="查看全谱面难度分布统计",
        pattern=r"^/mai charts$",
    )
    async def handle_charts(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))

        now = time.time()
        ttl = self.config.server.music_cache_ttl
        if self._chart_stats_cache and (now - self._chart_stats_cache_time) < ttl:
            data = self._chart_stats_cache
        else:
            client = await self._get_client()
            resp = await client.get_chart_stats()
            if self._is_error(resp):
                if self._chart_stats_cache is not None:
                    data = self._chart_stats_cache
                else:
                    await self.ctx.send.text(f"获取谱面统计失败: {self._error_msg(resp)}", stream_id)
                    return False, "获取失败", True
            else:
                data = resp
                self._chart_stats_cache = data
                self._chart_stats_cache_time = now

        if not data or not isinstance(data, dict):
            await self.ctx.send.text("暂无谱面统计数据", stream_id)
            return False, "无数据", True

        diff_data = data.get("diff_data", {})
        if not diff_data:
            await self.ctx.send.text("暂无谱面统计数据", stream_id)
            return False, "无数据", True

        diff_order = [(0, "Basic"), (1, "Advanced"), (2, "Expert"), (3, "Master"), (4, "Re:Master")]
        lines = ["【全谱面难度分布统计】"]
        for diff_idx, diff_label in diff_order:
            key = str(diff_idx)
            if key in diff_data:
                d = diff_data[key]
                ach = d.get("achievements", 0)
                fc_dist = d.get("fc_dist", [0, 0, 0, 0, 0])
                total = sum(fc_dist) if fc_dist else 1
                ap_rate = ((fc_dist[3] + fc_dist[4]) / total * 100) if total > 0 else 0
                fc_rate = ((sum(fc_dist[1:])) / total * 100) if total > 0 else 0
                lines.append(
                    f"{diff_label:12s}  均达成率: {ach:.2f}%  "
                    f"FC 率: {fc_rate:.1f}%  AP 率: {ap_rate:.1f}%"
                )

        lines.append(f"\n数据来源: diving-fish.com  (共 {len(data.get('charts', {}))} 首歌曲)")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "显示统计", True

    @Command(
        "mai_status",
        description="查看 diving-fish 和 lxns 服务器状态",
        pattern=r"^/mai status$",
    )
    async def handle_status(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        lines = []
        client = await self._get_client()
        resp = await client.alive_check()
        if self._is_error(resp):
            lines.append(f"diving-fish: 异常 ({self._error_msg(resp)})")
        elif isinstance(resp, dict) and resp.get("message") == "ok":
            lines.append("diving-fish: 正常 ✅")
        else:
            lines.append("diving-fish: 未知")
        if self.config.lxns.enable:
            lxns_client = await self._get_lxns_client()
            if lxns_client:
                lxns_resp = await lxns_client.alive_check()
                if LxnsApiClient._is_error(lxns_resp):
                    lines.append(f"lxns: 异常 ({lxns_resp.get('message','')})")
                else:
                    lines.append("lxns: 正常 ✅")
            else:
                lines.append("lxns: 未初始化")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "状态检测", True

    @Command(
        "mai_today",
        description="今日运势 — 查看今日宜忌与推荐歌曲",
        pattern=r"^/mai today$",
    )
    async def handle_today(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        wm_list = [
            "拼机", "推分", "越级", "下埋", "夜勤",
            "练底力", "练手法", "打旧框", "干饭", "抓绝赞", "收歌",
        ]
        uid_int = self._stable_user_uid(user_id)
        t = time.localtime()
        days = t.tm_mday + 31 * t.tm_mon + 77
        h = (days * uid_int) >> 8

        rp = h % 100
        wm_value = []
        for _ in range(11):
            wm_value.append(h & 3)
            h >>= 2

        yi_parts: list[str] = []
        ji_parts: list[str] = []
        for i in range(11):
            if wm_value[i] == 3:
                yi_parts.append(wm_list[i])
            elif wm_value[i] == 0:
                ji_parts.append(wm_list[i])

        songs = await self._get_songs_cached()
        if not songs:
            await self.ctx.send.text("获取曲目列表失败，请稍后重试", stream_id)
            return False, "获取失败", True

        seed = h % len(songs)
        music = songs[seed]
        if not isinstance(music, dict):
            await self.ctx.send.text("获取推荐曲目失败", stream_id)
            return False, "数据异常", True

        sid = str(music.get("id", "") or "")
        cover_b64 = await self._download_cover_base64(sid)

        yi_text = ", ".join(yi_parts) if yi_parts else "无"
        ji_text = ", ".join(ji_parts) if ji_parts else "无"
        title = str(music.get("title", "") or "???")
        tp = str(music.get("type", "") or "?")
        bi = music.get("basic_info", {})
        artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
        ds_list = music.get("ds", [])
        ds_str = " / ".join(str(d) for d in ds_list)

        blessing = random.choice(self._BLESSINGS)

        if cover_b64:
            await self.ctx.send.text("正在生成运势图片...", stream_id)
            try:
                img_b64 = await self._render_today_image(
                    rp, yi_parts, ji_parts, music, cover_b64, blessing=blessing,
                )
                await self.ctx.send.image(img_b64, stream_id)
                return True, "今日运势", True
            except RuntimeError as e:
                await self.ctx.send.text(str(e), stream_id)
                return False, "渲染失败", True
            except Exception:
                logger.debug("运势图片渲染失败，回退到文本模式", exc_info=True)

        lines = [
            f"【今日运势】\n人品值: {rp}",
            f"宜: {yi_text}",
            f"忌: {ji_text}",
            f"━━━━━━━━━━━━━━",
            f"推荐曲目: [{_html.escape(tp)}] {_html.escape(title)} — {_html.escape(artist)}",
            f"ID: {_html.escape(sid)}  |  定数: {ds_str}",
            blessing,
        ]
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "今日运势", True

    @Command(
        "mai_maidle_start",
        description="开始 Maidle 猜歌游戏",
        pattern=r"^/mai maidle$",
    )
    async def handle_maidle_start(
        self, stream_id: str = "", **kwargs: Any
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        async with self._maidle_sessions_lock:
            existing = self._maidle_sessions.get(user_id)
            if existing and time.time() - existing["started_at"] < 900:
                await self.ctx.send.text(
                    "当前已有进行中的猜歌游戏\n"
                    "继续猜测: /mai maidle guess <ID/名称>\n"
                    "放弃答案: /mai maidle answer",
                    stream_id,
                )
                return True, "已有会话", True
            if existing:
                del self._maidle_sessions[user_id]

        client = await self._get_client()
        maidle_data_resp = await client.get_maidle_data()
        song_ids: list[int] = []

        if isinstance(maidle_data_resp, list):
            for item in maidle_data_resp:
                sid = item.get("id", "") if isinstance(item, dict) else str(item)
                if sid and str(sid).isdigit():
                    song_ids.append(int(sid))
        elif isinstance(maidle_data_resp, dict) and not maidle_data_resp.get("_error"):
            for key in ("songs", "data", "list"):
                val = maidle_data_resp.get(key)
                if isinstance(val, list):
                    for item in val:
                        sid = item.get("id", "") if isinstance(item, dict) else str(item)
                        if sid and str(sid).isdigit():
                            song_ids.append(int(sid))
                    break
            if not song_ids:
                for key in maidle_data_resp:
                    if str(key).isdigit():
                        song_ids.append(int(key))

        if not song_ids:
            songs = await self._get_songs_cached()
            if songs:
                for m in songs:
                    if isinstance(m, dict):
                        sid = str(m.get("id", "") or "")
                        if sid and sid.isdigit():
                            song_ids.append(int(sid))

        if not song_ids:
            await self.ctx.send.text("无法获取歌曲列表，请稍后重试", stream_id)
            return False, "无数据", True

        first_guess = random.choice(song_ids)
        resp = await client.maidle_single(first_guess, lists=song_ids)
        if self._is_error(resp):
            await self.ctx.send.text(
                f"开始游戏失败: {self._error_msg(resp)}", stream_id
            )
            return False, "失败", True

        uuid_val = resp.get("uuid", "")
        if not uuid_val:
            await self.ctx.send.text("开始游戏失败: 未获取到会话 ID", stream_id)
            return False, "失败", True

        async with self._maidle_sessions_lock:
            self._maidle_sessions[user_id] = {
                "uuid": uuid_val,
                "started_at": time.time(),
            }

        test = resp.get("test", {})
        try:
            img_b64 = await self._render_maidle_image(first_guess, test)
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
        except Exception as e:
            logger.warning(f"Maidle 图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
        return True, "游戏开始", True

    @Command(
        "mai_maidle_guess",
        description="Maidle 猜歌 — 提交猜测",
        pattern=r"^/mai maidle guess\s+(?P<guess>.+)$",
    )
    async def handle_maidle_guess(
        self,
        stream_id: str = "",
        matched_groups: dict = None,
        **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        async with self._maidle_sessions_lock:
            session = self._maidle_sessions.get(user_id)
            if not session:
                await self.ctx.send.text(
                    "请先使用 /mai maidle 开始游戏", stream_id
                )
                return False, "无会话", True

            if time.time() - session["started_at"] > 900:
                del self._maidle_sessions[user_id]
                await self.ctx.send.text("游戏会话已过期 (15分钟)，请重新开始", stream_id)
                return False, "过期", True

        if not matched_groups or not matched_groups.get("guess"):
            await self.ctx.send.text("用法: /mai maidle guess <歌曲ID/名称/别称>", stream_id)
            return False, "参数错误", True

        raw = matched_groups["guess"].strip()
        if raw.isdigit():
            guess_id = int(raw)
        else:
            songs = await self._get_songs_cached()
            if not songs:
                await self.ctx.send.text("获取曲目列表失败，请稍后重试", stream_id)
                return False, "获取失败", True
            matches = await self._match_songs(raw)
            if not matches:
                await self.ctx.send.text(f"未找到匹配的曲目: \"{raw}\"\n可使用 /mai song 先行查询", stream_id)
                return False, "无匹配", True
            if len(matches) > 1:
                names = " | ".join(
                    f"ID.{str(m.get('id','') or '?')} {str(m.get('title','') or '?')[:12]}"
                    for m in matches[:5]
                )
                await self.ctx.send.text(f"找到多个匹配: {names}\n请使用 ID 重新猜测", stream_id)
                return False, "多匹配", True
            guess_id = int(str(matches[0].get("id", "0") or "0"))

        client = await self._get_client()
        async with self._maidle_sessions_lock:
            session = self._maidle_sessions.get(user_id)
        if not session:
            await self.ctx.send.text("游戏会话已不存在，请重新开始", stream_id)
            return False, "无会话", True

        resp = await client.maidle_single(guess_id, uuid=session["uuid"])
        if self._is_error(resp):
            await self.ctx.send.text(f"猜测失败: {self._error_msg(resp)}", stream_id)
            return False, "失败", True

        test = resp.get("test", {})
        try:
            img_b64 = await self._render_maidle_image(guess_id, test)
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
        except Exception as e:
            logger.warning(f"Maidle 图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
        return True, "猜测提交", True

    @Command(
        "mai_maidle_help",
        description="Maidle 猜歌游戏说明",
        pattern=r"^/mai maidle help$",
    )
    async def handle_maidle_help(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        try:
            img_b64 = await self._render_maidle_help_image()
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"Maidle 帮助图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
            return False, "渲染失败", True
        return True, "显示说明", True

    @Command(
        "mai_maidle_answer",
        description="Maidle 猜歌 — 查看答案",
        pattern=r"^/mai maidle answer$",
    )
    async def handle_maidle_answer(
        self, stream_id: str = "", **kwargs: Any
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        async with self._maidle_sessions_lock:
            session = self._maidle_sessions.pop(user_id, None)
        if not session:
            await self.ctx.send.text(
                "请先使用 /mai maidle 开始游戏", stream_id
            )
            return False, "无会话", True

        client = await self._get_client()
        resp = await client.maidle_answer(session["uuid"])

        if self._is_error(resp):
            await self.ctx.send.text(f"获取答案失败: {self._error_msg(resp)}", stream_id)
            return False, "获取失败", True

        title = str(resp.get("title", "") or "?")
        artist = str(resp.get("artist", "") or "?")
        sid = str(resp.get("id", "") or "?")

        cover_b64 = await self._download_cover_base64(sid) or ""

        try:
            img_b64 = await self._render_maidle_answer_image(
                title, artist, sid, cover_b64,
            )
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
        except Exception:
            logger.debug("Maidle 答案图片生成失败，回退到文本模式", exc_info=True)
            await self.ctx.send.text(
                f"【Maidle 答案】\n歌曲: {_html.escape(title)} — {_html.escape(artist)}  (ID: {_html.escape(sid)})",
                stream_id,
            )
        return True, "显示答案", True

    @Command(
        "mai_bind",
        description="绑定水鱼查分器的成绩导入Token",
        pattern=r"^/mai df bind\s+(?P<token>\S+)$",
    )
    async def handle_bind(
        self,
        stream_id: str = "",
        matched_groups: dict = None,
        **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        if not matched_groups or not matched_groups.get("token"):
            await self.ctx.send.text(
                "用法: /mai df bind <Token>\n"
                "Token 为水鱼查分器 personal page 中的「成绩导入Token」",
                stream_id,
            )
            return False, "参数错误", True

        token = matched_groups["token"].strip()
        client = await self._get_client()
        check = await client.token_available(token)
        if self._is_error(check):
            status = check.get("_status", 0)
            if status == 404 or "non-exist" in str(check.get("message", "")).lower():
                await self.ctx.send.text("Token 无效，请检查后重试", stream_id)
            else:
                await self.ctx.send.text(f"验证 Token 失败: {self._error_msg(check)}", stream_id)
            return False, "Token无效", True

        try:
            recs = await client.get_player_records(token)
        except Exception:
            await self.ctx.send.text("Token 验证失败，无法获取账号信息", stream_id)
            return False, "获取失败", True

        username = "unknown"
        if isinstance(recs, dict) and not recs.get("_error"):
            username = str(recs.get("username", "") or "unknown")

        await self._bindings.set(user_id, username, token)
        logger.warning(
            f"用户 {user_id} 绑定了 Import-Token (用户名: {username})，"
            "Token 将以明文存储在 bindings.json 中，请确保插件目录权限合理"
        )
        await self.ctx.send.text(
            f"【账号绑定】\n"
            f"状态: 绑定成功\n"
            f"用户名: {_html.escape(username)}\n"
            f"可使用 /mai df my 查看个人成绩\n\n"
            f"⚠ 建议撤回刚才的消息，避免 Token 泄露",
            stream_id,
        )
        return True, "绑定完成", True

    @Command(
        "mai_unbind",
        description="解除水鱼查分器账号绑定",
        pattern=r"^/mai df unbind$",
    )
    async def handle_unbind(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        deleted = await self._bindings.delete(user_id)
        if deleted:
            await self.ctx.send.text("已解除账号绑定", stream_id)
        else:
            await self.ctx.send.text("当前未绑定账号", stream_id)
        return True, "解绑完成", True

    @Command(
        "mai_my",
        description="查看个人成绩摘要",
        pattern=r"^/mai df my$",
    )
    async def handle_my(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        binding = await self._get_binding(kwargs)
        if not binding:
            await self.ctx.send.text(
                "请先绑定 Token: /mai df bind <Token>\n"
                "Token 为水鱼查分器 personal page 中的「成绩导入Token」",
                stream_id,
            )
            return False, "未绑定", True

        client = await self._get_client()
        resp = await client.get_player_records(binding["import_token"])
        if self._is_error(resp):
            msg = self._error_msg(resp)
            if resp.get("_status") == 400 and "token" in msg.lower():
                await self.ctx.send.text(
                    f"Token 已失效: {msg}\n请重新绑定: /mai df bind <Token>",
                    stream_id,
                )
            else:
                await self.ctx.send.text(f"获取数据失败: {msg}", stream_id)
            return False, "获取失败", True

        username = str(resp.get("username", "") or binding["username"])
        nickname = str(resp.get("nickname", "") or "未设置")
        rating = resp.get("rating", 0)
        additional = resp.get("additional_rating", 0)
        plate = resp.get("plate", "无")
        records = resp.get("records", [])
        if not isinstance(records, list):
            records = []

        try:
            img_b64 = await self._render_my_image(
                username, nickname, rating, additional, plate, records,
            )
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"个人成绩图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
            return False, "渲染失败", True

        return True, "显示摘要", True

    @Command(
        "mai_alias_add",
        description="为歌曲添加别称",
        pattern=r"^/mai alias add\s+(?P<song_id>\S+)\s+(?P<alias>.+)$",
    )
    async def handle_alias_add(
        self,
        stream_id: str = "",
        matched_groups: dict = None,
        **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai alias add <歌曲ID> <别称>", stream_id)
            return False, "参数错误", True

        song_id = matched_groups["song_id"].strip()
        alias = matched_groups.get("alias", "").strip()
        if not alias:
            await self.ctx.send.text("用法: /mai alias add <歌曲ID> <别称>", stream_id)
            return False, "参数错误", True

        songs = await self._get_songs_cached()
        if not songs:
            await self.ctx.send.text("获取曲目列表失败，请稍后重试", stream_id)
            return False, "获取失败", True

        found = False
        for music in songs:
            if isinstance(music, dict) and str(music.get("id", "") or "") == song_id:
                found = True
                break
        if not found:
            await self.ctx.send.text(
                f"歌曲 ID {song_id} 不存在于曲库中\n"
                "可使用 /mai song <关键词> 搜索歌曲ID",
                stream_id,
            )
            return False, "ID不存在", True

        ok, msg = await self._aliases.add(song_id, alias)
        if ok:
            title = "?"
            for music in songs:
                if isinstance(music, dict) and str(music.get("id", "") or "") == song_id:
                    title = str(music.get("title", "") or "?")
                    break
            await self.ctx.send.text(
                f"【别称管理】\n状态: 添加成功\n{_html.escape(title)} (ID: {_html.escape(song_id)}) ← \"{_html.escape(alias)}\"",
                stream_id,
            )
        else:
            await self.ctx.send.text(
                f"【别称管理】\n状态: 添加失败\n原因: {msg}", stream_id
            )

        return True, "添加别称", True

    @Command(
        "mai_alias_del",
        description="删除歌曲别称",
        pattern=r"^/mai alias del\s+(?P<song_id>\S+)\s+(?P<alias>.+)$",
    )
    async def handle_alias_del(
        self,
        stream_id: str = "",
        matched_groups: dict = None,
        **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai alias del <歌曲ID> <别称>", stream_id)
            return False, "参数错误", True

        song_id = matched_groups["song_id"].strip()
        alias = matched_groups.get("alias", "").strip()
        if not alias:
            await self.ctx.send.text("用法: /mai alias del <歌曲ID> <别称>", stream_id)
            return False, "参数错误", True

        ok, msg = await self._aliases.delete(song_id, alias)
        if ok:
            await self.ctx.send.text(
                f"【别称管理】\n状态: 删除成功\n歌曲 {_html.escape(song_id)} 不再使用 \"{_html.escape(alias)}\"",
                stream_id,
            )
        else:
            await self.ctx.send.text(f"【别称管理】\n状态: 删除失败\n原因: {msg}", stream_id)
        return True, "删除别称", True

    @Command(
        "mai_alias_list",
        description="查看歌曲所有别称",
        pattern=r"^/mai alias list\s+(?P<song_id>\S+)$",
    )
    async def handle_alias_list(
        self,
        stream_id: str = "",
        matched_groups: dict = None,
        **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai alias list <歌曲ID>", stream_id)
            return False, "参数错误", True

        song_id = matched_groups["song_id"].strip()
        songs = await self._get_songs_cached()
        title = song_id
        if songs:
            for music in songs:
                if isinstance(music, dict) and str(music.get("id", "") or "") == song_id:
                    title = str(music.get("title", "") or "?")
                    break
        aliases = await self._aliases.list_aliases(song_id)
        if not aliases:
            await self.ctx.send.text(
                f"【别称管理】\n{_html.escape(title)} (ID: {_html.escape(song_id)}) 暂无比称", stream_id
            )
        else:
            lines = [
                f"【别称管理】",
                f"{_html.escape(title)} (ID: {_html.escape(song_id)}) 的别称:"
            ]
            for i, a in enumerate(aliases, 1):
                lines.append(f"  {i}. {_html.escape(a)}")
            await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "列出别称", True

    # ---- lxns 图片渲染 ----

    async def _render_lxns_help_image(self) -> str:
        sections = [
            ("公开查询 (无需绑定)",
             [("/mai lxns song <ID>", "增强版曲目详情 (谱师/注音/Buddy)"),
              ("/mai lxns status", "lxns 服务器状态"),
              ("/mai lxns alias import", "导入 lxns 社区别名到本地")]),
            ("排行与社交 (需 JWT Token)",
             [("/mai lxns rank <ID>", "🔒 单曲全球排行榜"),
              ("/mai lxns history <ID>", "🔒 单曲成绩进步轨迹"),
              ("/mai lxns comment <ID>", "🔒 查看歌曲评论区")]),
            ("收藏品 (需 JWT Token)",
             [("/mai lxns collections <种类>", "🔒 收藏品列表与详情")]),
            ("管理",
             [("/mai lxns bind <Token>", "绑定 Token (JWT 完整/个人密钥公开)"),
              ("/mai lxns unbind", "解除绑定")]),
        ]
        sec_html_parts = []
        for label, cmds in sections:
            items = "".join(
                f'<div class="cmd"><span class="cmd-name">{_html.escape(c[0])}</span><span class="cmd-desc">{_html.escape(c[1])}</span></div>'
                for c in cmds
            )
            sec_html_parts.append(
                f'<div class="section"><div class="sec-label">{_html.escape(label)}</div>{items}</div>'
            )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:36px 48px}}
.header{{text-align:center;margin-bottom:44px}}
.header h2{{font-size:46px;color:#e8e8f0;letter-spacing:5px;margin-bottom:10px}}
.header .sub{{font-size:20px;color:#7878a8}}
.section{{margin-bottom:32px}}
.sec-label{{font-size:30px;color:#c0c0d8;font-weight:600;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #2e2e48}}
.cmd{{display:flex;padding:10px 0}}
.cmd-name{{flex-shrink:0;width:460px;font-size:26px;color:#60a0d0;font-family:'Consolas','Courier New',monospace}}
.cmd-desc{{font-size:26px;color:#9090b8}}
</style></head>
<body>
<div class="header">
<h2>MaiMai DX / lxns</h2>
<div class="sub">🔒 = 需绑定 lxns JWT Token（非个人密钥）</div>
</div>
{''.join(sec_html_parts)}
<div class="footer-bar" style="display:flex;align-items:center;margin-top:24px;padding-top:12px;border-top:1px solid #333350;font-size:14px">
<span style="color:#7878a8;flex:1">数据来源: lxns</span>
<span style="color:#585878;flex:1;text-align:right">MaiBot</span>
</div>
</body></html>"""
        return await self._render_html_to_png(html, width=1060, height=760)

    async def _render_lxns_b50_image(
        self, bests: dict, username: str, rating: int,
        query_time: str = "", blessing: str = "",
    ) -> str:
        standard = bests.get("standard", []) or []
        dx = bests.get("dx", []) or []
        if not isinstance(standard, list):
            standard = []
        if not isinstance(dx, list):
            dx = []

        lxns_cache = await self._get_lxns_songs_cached()
        lxns_songs = lxns_cache.get("songs", []) if lxns_cache else []
        ds_map: dict[int, int] = {}
        if lxns_songs:
            for s in lxns_songs:
                if isinstance(s, dict):
                    sid = s.get("id", 0)
                    diffs = s.get("difficulties", {})
                    all_diffs = (
                        diffs.get("standard", [])
                        + diffs.get("dx", [])
                        + diffs.get("utage", [])
                    )
                    for d in all_diffs:
                        if isinstance(d, dict):
                            key = sid * 10 + d.get("difficulty", 0)
                            ds_map[key] = d.get("level_value", 0)

        def _sort_key(rec):
            return -(rec.get("dx_rating", 0) or 0)

        standard.sort(key=_sort_key)
        dx.sort(key=_sort_key)
        sd35 = standard[:35]
        dx15 = dx[:15]

        diff_colors = {
            0: ("#4caf50", "#162316"),
            1: ("#e0b040", "#262016"),
            2: ("#e05050", "#261816"),
            3: ("#9b59b6", "#1c1626"),
            4: ("#a0a0d0", "#1a1a28"),
        }

        def _cards_html(recs: list, section_label: str) -> str:
            parts = [
                f'<div class="section-title">{section_label} ({len(recs)} 首)</div>'
                '<div class="grid">'
            ]
            for i, r in enumerate(recs):
                if not isinstance(r, dict):
                    continue
                song_name = r.get("song_name", "???")
                level = r.get("level", "?")
                tp = r.get("type", "SD")
                li = r.get("level_index", 2)
                song_id = r.get("id", 0)
                achievements = r.get("achievements", 0)
                dx_rating = r.get("dx_rating", 0)
                rate = RATE_DISPLAY.get(r.get("rate", ""), r.get("rate", "-"))
                fc = FC_DISPLAY.get(r.get("fc", ""), r.get("fc", "-"))
                fs = FS_DISPLAY.get(r.get("fs", ""), r.get("fs", "-"))
                dx_score = r.get("dx_score", 0)
                ds_key = int(song_id) * 10 + int(li)
                ds_val = ds_map.get(ds_key, 0)
                border_color, bg_color = diff_colors.get(
                    li, diff_colors[2]
                )
                lxns_client = self._lxns_client
                asset_url = self.config.lxns.asset_url if self.config.lxns.enable else ""
                if lxns_client and asset_url:
                    cover_url = LxnsApiClient.get_cover_url(asset_url, int(song_id))
                else:
                    cover_url = self._get_cover_url(str(song_id))
                parts.append(
                    f'<div class="card" style="border-left-color:{border_color};background:{bg_color}">'
                    f'<div class="tl">'
                    f'<div class="rank">#{i + 1}</div>'
                    f'<div class="type-badge">{_html.escape(str(tp))}</div>'
                    f'<div class="level">Lv.{_html.escape(str(level))}</div>'
                    f'</div>'
                    f'<div class="tr">'
                    f'<div class="title">{_html.escape(str(song_name))}</div>'
                    f'<div class="achievements">{achievements:.4f}</div>'
                    f'</div>'
                    f'<div class="bl">'
                    f'<div class="ra">RT:{dx_rating}</div>'
                    f'<div class="meta">{_html.escape(rate)} | {_html.escape(fc)} | {_html.escape(fs)}</div>'
                    f'<div class="dxscore">分数:{dx_score}  DS:{ds_val}</div>'
                    f'</div>'
                    f'<div class="br">'
                    f'<img class="cover" src="{cover_url}" onerror="this.style.display=\'none\'" />'
                    f'</div>'
                    f'</div>'
                )
            parts.append("</div>")
            return "".join(parts)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:36px 48px 18px 48px}}
.header{{text-align:center;margin-bottom:40px}}
.header h2{{font-size:44px;color:#e8e8f0;margin-bottom:6px;letter-spacing:3px}}
.header .sub{{font-size:20px;color:#8888a8}}
.header .total{{font-size:32px;color:#f0c060;margin-top:10px;font-weight:600}}
.section-title{{font-size:28px;color:#d0d0e0;margin:30px 0 18px;padding-bottom:8px;border-bottom:1px solid #333350}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:18px}}
.card{{display:grid;grid-template-columns:105px 1fr;grid-template-rows:auto auto;gap:6px 8px;padding:14px 16px 14px 14px;border-radius:10px;border-left:5px solid;min-height:300px;box-shadow:0 2px 8px rgba(0,0,0,.3)}}
.tl{{display:flex;flex-direction:column;gap:3px;align-items:flex-start}}
.tr{{display:flex;flex-direction:column;gap:6px;overflow:hidden;padding-right:2px}}
.bl{{display:flex;flex-direction:column;gap:4px;justify-content:center}}
.br{{display:flex;align-items:center;justify-content:center}}
.rank{{font-size:21px;color:#6868a0}}
.title{{font-size:22px;color:#e4e4f0;font-weight:600;min-height:60px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:break-word}}
.cover{{width:130px;height:130px;border-radius:6px;object-fit:cover;opacity:0.92;box-shadow:0 2px 6px rgba(0,0,0,.4)}}
.type-badge{{font-size:17px;color:#8888b0}}
.level{{font-size:21px;color:#9090b8}}
.achievements{{font-size:28px;color:#f0d060;font-weight:700}}
.ra{{font-size:25px;color:#c0c0d4}}
.meta{{font-size:17px;color:#7878a0}}
.dxscore{{font-size:15px;color:#686890}}
.footer-bar{{display:flex;align-items:center;margin-top:44px;padding-top:18px;border-top:1px solid #333350;font-size:20px}}
.footer-time{{color:#7878a8;flex:1;text-align:left}}
.footer-source{{color:#7878a8;flex:1;text-align:center}}
.blessing{{color:#c0c0d8;flex:1;text-align:right}}
</style></head>
<body>
<div class="header">
<h2>MaiMai DX / Best 50 (lxns)</h2>
<div class="sub">@{_html.escape(username)}</div>
<div class="total">DX Rating: {rating}</div>
</div>
{_cards_html(sd35, "B35 / Standard")}
{_cards_html(dx15, "B15 / DX")}
<div class="footer-bar">
<span class="footer-time">查询时间: {_html.escape(query_time)}</span>
<span class="footer-source">数据来源: lxns</span>
<span class="blessing">{_html.escape(blessing)}</span>
</div>
</body></html>"""

        sd_rows = (len(sd35) + 4) // 5 if sd35 else 0
        dx_rows = (len(dx15) + 4) // 5 if dx15 else 0
        total_rows = sd_rows + dx_rows
        card_h = 300
        header_h = 175
        section_h = 55
        row_gap = 18
        pad = 36
        height = header_h + section_h * 2 + total_rows * card_h + max(total_rows - 2, 0) * row_gap + pad * 2 + 100
        return await self._render_html_to_png(
            html, width=1600, height=height, wait_for_images=True, image_timeout=30000,
        )

    async def _render_lxns_my_image(
        self, player: dict, bests: dict,
    ) -> str:
        name = str(player.get("name", "") or "???")
        rating = player.get("rating", 0)
        friend_code = player.get("friend_code", 0)
        course_rank = player.get("course_rank", 0)
        class_rank = player.get("class_rank", 0)
        star = player.get("star", 0)
        trophy = player.get("trophy", {}) or {}
        trophy_name = trophy.get("name", "-") if isinstance(trophy, dict) else "-"
        icon = player.get("icon", {}) or {}
        icon_name = icon.get("name", "-") if isinstance(icon, dict) else "-"
        name_plate = player.get("name_plate", {}) or {}
        plate_name = name_plate.get("name", "-") if isinstance(name_plate, dict) else "-"
        frame = player.get("frame", {}) or {}
        frame_name = frame.get("name", "-") if isinstance(frame, dict) else "-"

        standard = bests.get("standard", []) or []
        dx = bests.get("dx", []) or []
        if not isinstance(standard, list):
            standard = []
        if not isinstance(dx, list):
            dx = []
        sd_count = len(standard)
        dx_count = len(dx)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:40px 48px}}
.header{{text-align:center;margin-bottom:28px}}
.header .name{{font-size:26px;color:#e8e8f0;font-weight:600;letter-spacing:2px}}
.header .fc{{font-size:14px;color:#7878a8;margin-top:4px}}
.rating{{text-align:center;margin:20px 0}}
.rating .val{{font-size:46px;font-weight:700;color:#f0c060}}
.rating .label{{font-size:14px;color:#8888a8}}
.stats{{display:flex;gap:18px;justify-content:center;margin:20px 0;flex-wrap:wrap}}
.stat-box{{background:#24243a;border-radius:8px;padding:14px 20px;text-align:center;min-width:90px;box-shadow:0 2px 6px rgba(0,0,0,.2)}}
.stat-box .s-val{{font-size:22px;font-weight:600;color:#e4e4f0}}
.stat-box .s-label{{font-size:11px;color:#7878a8;margin-top:2px}}
.section-title{{font-size:16px;color:#c0c0d8;font-weight:600;margin:20px 0 10px;padding-bottom:4px;border-bottom:1px solid #333350}}
.collections{{display:flex;gap:24px;flex-wrap:wrap;margin:10px 0}}
.col-item{{display:flex;flex-direction:column;align-items:center;gap:6px}}
.col-item .c-name{{font-size:13px;color:#a0a0c0}}
.col-item .c-val{{font-size:14px;color:#c8c8d8;font-weight:600}}
.footer-bar{{display:flex;align-items:center;margin-top:28px;padding-top:12px;border-top:1px solid #333350;font-size:12px}}
.footer-source{{color:#7878a8;flex:1}}
.footer-mai{{color:#585878;text-align:right}}
</style></head>
<body>
<div class="header">
<div class="name">{_html.escape(name)}</div>
<div class="fc">好友码: {friend_code}</div>
</div>
<div class="rating">
<div class="val">{rating}</div>
<div class="label">DX Rating</div>
</div>
<div class="stats">
<div class="stat-box"><div class="s-val">{_html.escape(str(course_rank))}</div><div class="s-label">段位</div></div>
<div class="stat-box"><div class="s-val">{_html.escape(str(class_rank))}</div><div class="s-label">阶级</div></div>
<div class="stat-box"><div class="s-val">{star}</div><div class="s-label">★</div></div>
<div class="stat-box"><div class="s-val">{sd_count}</div><div class="s-label">SD 成绩数</div></div>
<div class="stat-box"><div class="s-val">{dx_count}</div><div class="s-label">DX 成绩数</div></div>
</div>
<div class="section-title">称号与藏品</div>
<div class="collections">
<div class="col-item"><div class="c-name">称号</div><div class="c-val">{_html.escape(str(trophy_name))}</div></div>
<div class="col-item"><div class="c-name">头像</div><div class="c-val">{_html.escape(str(icon_name))}</div></div>
<div class="col-item"><div class="c-name">铭牌</div><div class="c-val">{_html.escape(str(plate_name))}</div></div>
<div class="col-item"><div class="c-name">外框</div><div class="c-val">{_html.escape(str(frame_name))}</div></div>
</div>
<div class="footer-bar">
<span class="footer-source">数据来源: lxns</span>
<span class="footer-mai">MaiBot</span>
</div>
</body></html>"""
        return await self._render_html_to_png(html, width=680, height=500)

    async def _render_heatmap_image(self, heatmap_data: dict) -> str:
        cells = ""
        today = datetime.now(timezone.utc).date()
        start_date = today.replace(year=today.year - 1)
        current = start_date
        max_count = max(heatmap_data.values()) if heatmap_data else 1
        while current <= today:
            date_str = current.strftime("%Y-%m-%d")
            count = heatmap_data.get(date_str, 0)
            if count == 0:
                color = "#1e1e32"
            elif count <= max_count * 0.25:
                color = "#1a3a1a"
            elif count <= max_count * 0.5:
                color = "#2a5a2a"
            elif count <= max_count * 0.75:
                color = "#3a7a3a"
            else:
                color = "#4a9a4a"
            cells += f'<div class="cell" style="background:{color}" title="{date_str}: {count}"></div>'
            current = current + timedelta(days=1)
        weeks = (today - start_date).days // 7 + 1
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:32px 40px}}
h2{{font-size:20px;color:#d0d0e0;text-align:center;margin-bottom:20px;letter-spacing:2px}}
.grid{{display:grid;grid-template-columns:repeat({weeks},14px);grid-template-rows:repeat(7,14px);gap:2px;justify-content:center}}
.cell{{width:14px;height:14px;border-radius:2px}}
.legend{{display:flex;gap:4px;justify-content:center;margin-top:16px;align-items:center;font-size:11px;color:#7878a8}}
.legend .box{{width:12px;height:12px;border-radius:2px}}
.footer-bar{{display:flex;align-items:center;margin-top:20px;padding-top:10px;border-top:1px solid #333350;font-size:12px}}
.footer-source{{color:#7878a8;flex:1}}
.footer-mai{{color:#585878;text-align:right}}
</style></head>
<body>
<h2>游玩热力图 (近一年)</h2>
<div class="grid">{cells}</div>
<div class="legend">
<span>少</span>
<div class="box" style="background:#1e1e32"></div>
<div class="box" style="background:#1a3a1a"></div>
<div class="box" style="background:#2a5a2a"></div>
<div class="box" style="background:#3a7a3a"></div>
<div class="box" style="background:#4a9a4a"></div>
<span>多</span>
</div>
<div class="footer-bar">
<span class="footer-source">数据来源: lxns</span>
<span class="footer-mai">MaiBot</span>
</div>
</body></html>"""
        return await self._render_html_to_png(html, width=1200, height=300)

    async def _render_trend_image(
        self, trend_data: list, version: int,
    ) -> str:
        if not trend_data:
            trend_data = []
        bars = ""
        max_val = max(
            (d.get("total", 0) for d in trend_data if isinstance(d, dict)), default=1
        )
        for i, d in enumerate(trend_data):
            if not isinstance(d, dict):
                continue
            total = d.get("total", 0)
            std_total = d.get("standard_total", 0)
            dx_total = d.get("dx_total", 0)
            date_str = str(d.get("date", ""))
            if len(date_str) > 10:
                date_str = date_str[:10]
            height_pct = (total / max_val * 100) if max_val else 0
            bars += (
                f'<div class="bar-wrap">'
                f'<div class="bar-val">{total}</div>'
                f'<div class="bar" style="height:{height_pct:.0f}%"><div class="bar-dx" style="height:{(dx_total / total * 100) if total else 0:.0f}%"></div></div>'
                f'<div class="bar-label">{_html.escape(date_str)}</div>'
                f'</div>'
            )
        version_names = {25000: "舞萌DX 2025", 24000: "舞萌DX 2024", 23000: "舞萌DX 2023"}
        version_name = version_names.get(version, f"v{version}")
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:32px 40px}}
h2{{font-size:20px;color:#d0d0e0;text-align:center;margin-bottom:8px;letter-spacing:2px}}
.sub{{font-size:14px;color:#7878a8;text-align:center;margin-bottom:24px}}
.chart{{display:flex;gap:6px;align-items:flex-end;justify-content:center;height:280px;padding:0 10px}}
.bar-wrap{{display:flex;flex-direction:column;align-items:center;gap:3px;width:44px}}
.bar{{width:32px;background:#2a2a42;border-radius:4px 4px 0 0;position:relative;min-height:2px}}
.bar-dx{{position:absolute;bottom:0;left:0;right:0;background:#5b8fd4;border-radius:0 0 4px 4px}}
.bar-val{{font-size:11px;color:#9090b8}}
.bar-label{{font-size:9px;color:#6868a0;transform:rotate(-40deg);white-space:nowrap;margin-top:2px}}
.legend{{display:flex;gap:16px;justify-content:center;margin-top:18px;font-size:12px;color:#9090b8}}
.legend .dot{{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:4px}}
.footer-bar{{display:flex;align-items:center;margin-top:20px;padding-top:10px;border-top:1px solid #333350;font-size:12px}}
.footer-source{{color:#7878a8;flex:1}}
.footer-mai{{color:#585878;text-align:right}}
</style></head>
<body>
<h2>Rating 趋势</h2>
<div class="sub">{version_name}</div>
<div class="chart">{bars}</div>
<div class="legend">
<span><span class="dot" style="background:#2a2a42"></span>SD Rating</span>
<span><span class="dot" style="background:#5b8fd4"></span>DX Rating</span>
</div>
<div class="footer-bar">
<span class="footer-source">数据来源: lxns</span>
<span class="footer-mai">MaiBot</span>
</div>
</body></html>"""
        return await self._render_html_to_png(html, width=900, height=480)

    async def _render_year_review_image(
        self, data: dict, year: int,
    ) -> str:
        player_name = str(data.get("player_name", "") or "???")
        upload_days = data.get("player_upload_days", 0)
        total = data.get("prober_total_uploads", 0)
        monthly = data.get("player_monthly_uploads", {}) or {}
        max_month = max(monthly.values()) if monthly else 1
        monthly_bars = ""
        for m in range(1, 13):
            cnt = monthly.get(str(m), 0)
            h = (cnt / max_month * 100) if max_month else 0
            monthly_bars += (
                f'<div class="m-bar-wrap">'
                f'<div class="m-bar-val">{cnt}</div>'
                f'<div class="m-bar"><div class="m-bar-fill" style="height:{h:.0f}%"></div></div>'
                f'<div class="m-bar-label">{m}月</div>'
                f'</div>'
            )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{_BASE_HTML_STYLE}
body{{padding:36px 44px}}
.header{{text-align:center;margin-bottom:32px}}
.header h2{{font-size:28px;color:#e8e8f0;letter-spacing:3px;margin-bottom:6px}}
.header .name{{font-size:18px;color:#a0a0c0}}
.stats{{display:flex;gap:24px;justify-content:center;margin:24px 0}}
.stat-box{{background:#24243a;border-radius:8px;padding:16px 24px;text-align:center;min-width:100px}}
.stat-box .s-val{{font-size:28px;font-weight:600;color:#e4e4f0}}
.stat-box .s-label{{font-size:12px;color:#7878a8;margin-top:4px}}
.sec-title{{font-size:16px;color:#c0c0d8;margin:20px 0 10px;padding-bottom:4px;border-bottom:1px solid #333350}}
.m-chart{{display:flex;gap:6px;align-items:flex-end;justify-content:center;height:140px}}
.m-bar-wrap{{display:flex;flex-direction:column;align-items:center;gap:2px;width:36px}}
.m-bar{{width:24px;background:#2a2a42;border-radius:3px 3px 0 0;height:100px}}
.m-bar-fill{{background:linear-gradient(180deg,#f0c060,#e08030);border-radius:3px 3px 0 0;width:100%}}
.m-bar-val{{font-size:10px;color:#9090b8}}
.m-bar-label{{font-size:9px;color:#6868a0}}
.footer-bar{{display:flex;align-items:center;margin-top:28px;padding-top:12px;border-top:1px solid #333350;font-size:12px}}
.footer-source{{color:#7878a8;flex:1}}
.footer-mai{{color:#585878;text-align:right}}
</style></head>
<body>
<div class="header">
<h2>{year} 年度回顾</h2>
<div class="name">{_html.escape(player_name)}</div>
</div>
<div class="stats">
<div class="stat-box"><div class="s-val">{upload_days}</div><div class="s-label">出勤天数</div></div>
<div class="stat-box"><div class="s-val">{total}</div><div class="s-label">总上传成绩</div></div>
</div>
<div class="sec-title">月上传量</div>
<div class="m-chart">{monthly_bars}</div>
<div class="footer-bar">
<span class="footer-source">数据来源: lxns</span>
<span class="footer-mai">MaiBot</span>
</div>
</body></html>"""
        return await self._render_html_to_png(html, width=760, height=520)

    # ---- lxns 命令 ----

    @Command(
        "mai_lxns_help",
        description="lxns 查分器帮助",
        pattern=r"^/mai lxns(\s+(help|帮助))?$",
    )
    async def handle_lxns_help(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用，请在配置中开启", stream_id)
            return False, "未启用", True
        try:
            img_b64 = await self._render_lxns_help_image()
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"lxns 帮助图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
            return False, "渲染失败", True
        return True, "显示lxns帮助", True

    @Command(
        "mai_lxns_bind",
        description="绑定 lxns JWT Token",
        pattern=r"^/mai lxns bind\s+(?P<token>\S+)$",
    )
    async def handle_lxns_bind(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        if not matched_groups or not matched_groups.get("token"):
            await self.ctx.send.text("用法: /mai lxns bind <JWT Token>", stream_id)
            return False, "参数错误", True
        token = matched_groups["token"].strip()
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True

        tokens_to_try = [token]
        try:
            decoded = base64.urlsafe_b64decode(token + "===").decode("utf-8", errors="ignore")
            if decoded and decoded != token and len(decoded) > 3:
                tokens_to_try.append(decoded)
        except Exception:
            pass

        username = "unknown"
        auth_ok = False
        auth_method = "Bearer"
        for try_token in tokens_to_try:
            for method in ("Bearer", "Token", "Raw", "Import-Token", "X-API-Key", "param:token", "param:key", "param:import_token"):
                for path in ("/user/maimai/player", "/user/maimai/player/bests"):
                    resp = await client._get(path, token=try_token, auth_header=method)
                    if LxnsApiClient._is_error(resp):
                        continue
                    if isinstance(resp, dict) and resp.get("success") is not False:
                        data = resp.get("data", resp) if isinstance(resp, dict) else resp
                        if isinstance(data, dict):
                            uname = data.get("name") or data.get("username") or ""
                            if uname:
                                username = str(uname)
                                auth_ok = True
                                auth_method = method
                                token = try_token
                                break
                            if isinstance(data, dict) and (data.get("standard") is not None or data.get("dx") is not None):
                                auth_ok = True
                                auth_method = method
                                token = try_token
                                break
                    if auth_ok:
                        break
                if auth_ok:
                    break
            if auth_ok:
                break

        if not auth_ok:
            logger.warning(
                f"lxns Token 验证暂无法确认 (用户: {user_id})，已保存待实际使用时验证"
            )

        if self._lxns_bindings:
            await self._lxns_bindings.set(user_id, token, username, auth_method)
            note = (
                "\n⚠ 个人密钥暂无法访问用户数据（b50/my/heatmap等），"
                "仅公开功能可用。完整功能需浏览器登录JWT Token"
            ) if not auth_ok else ""
            await self.ctx.send.text(
                f"【lxns 绑定】\n"
                f"状态: {'绑定成功' if auth_ok else '已保存 (暂不可用)'}\n"
                f"用户名: {_html.escape(username)}\n"
                f"{note}\n\n"
                f"⚠ 建议撤回刚才的消息，避免 Token 泄露",
                stream_id,
            )
        return True, "绑定完成", True

    @Command(
        "mai_lxns_unbind",
        description="解除 lxns 账号绑定",
        pattern=r"^/mai lxns unbind$",
    )
    async def handle_lxns_unbind(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        if self._lxns_bindings:
            deleted = await self._lxns_bindings.delete(user_id)
            if deleted:
                await self.ctx.send.text("已解除 lxns 账号绑定", stream_id)
            else:
                await self.ctx.send.text("当前未绑定 lxns 账号", stream_id)
        return True, "解绑完成", True

    @Command(
        "mai_lxns_status",
        description="查看 lxns 服务器状态",
        pattern=r"^/mai lxns status$",
    )
    async def handle_lxns_status(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        resp = await client.alive_check()
        if LxnsApiClient._is_error(resp):
            await self.ctx.send.text(f"lxns 服务器异常: {resp.get('message', '未知')}", stream_id)
            return False, "异常", True
        await self.ctx.send.text("lxns 服务器状态: 正常 ✅", stream_id)
        return True, "状态检测", True

    @Command(
        "mai_lxns_b50",
        description="lxns 版 Best 50 成绩查询",
        pattern=r"^/mai lxns b50$",
    )
    async def handle_lxns_b50(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text(
                "请先绑定 lxns Token: /mai lxns bind <Token>", stream_id,
            )
            return False, "未绑定", True
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        player_resp = await self._lxns_auth_call(
            client, "/user/maimai/player", binding,
        )
        if LxnsApiClient._is_error(player_resp):
            await self.ctx.send.text(f"获取玩家数据失败: {player_resp.get('message', '')}", stream_id)
            return False, "获取失败", True
        bests_resp = await self._lxns_auth_call(
            client, "/user/maimai/player/bests", binding,
        )
        if LxnsApiClient._is_error(bests_resp):
            await self.ctx.send.text(f"获取成绩数据失败: {bests_resp.get('message', '')}", stream_id)
            return False, "获取失败", True
        username = str(player_resp.get("name", "") or binding["username"]) if isinstance(player_resp, dict) else binding["username"]
        rating = player_resp.get("rating", 0) if isinstance(player_resp, dict) else 0
        await self.ctx.send.text("正在生成 lxns B50 图片，请稍候...", stream_id)
        query_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        blessing = random.choice(self._BLESSINGS)
        try:
            img_b64 = await self._render_lxns_b50_image(
                bests_resp, username, rating,
                query_time=query_time_str, blessing=blessing,
            )
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"lxns B50 图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
            return False, "渲染失败", True
        return True, "发送lxns B50图片", True

    @Command(
        "mai_lxns_my",
        description="lxns 个人资料与成绩摘要",
        pattern=r"^/mai lxns my$",
    )
    async def handle_lxns_my(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text("请先绑定: /mai lxns bind <Token>", stream_id)
            return False, "未绑定", True
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        player_resp = await self._lxns_auth_call(
            client, "/user/maimai/player", binding,
        )
        if LxnsApiClient._is_error(player_resp):
            await self.ctx.send.text(f"获取数据失败: {player_resp.get('message', '')}", stream_id)
            return False, "获取失败", True
        bests_resp = await self._lxns_auth_call(
            client, "/user/maimai/player/bests", binding,
        )
        if LxnsApiClient._is_error(bests_resp):
            bests_resp = {"standard": [], "dx": []}
        try:
            img_b64 = await self._render_lxns_my_image(player_resp, bests_resp)
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"lxns my 图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
            return False, "渲染失败", True
        return True, "显示资料", True

    @Command(
        "mai_lxns_song",
        description="lxns 增强版曲目详情",
        pattern=r"^/mai lxns song\s+(?P<keyword>.+)$",
    )
    async def handle_lxns_song(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        if not matched_groups or not matched_groups.get("keyword"):
            await self.ctx.send.text("用法: /mai lxns song <歌曲ID>", stream_id)
            return False, "参数错误", True
        keyword = matched_groups["keyword"].strip()
        if not keyword.isdigit():
            await self.ctx.send.text("请使用歌曲 ID 查询，如 /mai lxns song 11385", stream_id)
            return False, "参数错误", True
        sid = int(keyword)
        songs = await self._get_songs_cached()
        if not songs:
            await self.ctx.send.text("获取曲目列表失败，请稍后重试", stream_id)
            return False, "获取失败", True
        music = None
        for m in songs:
            if isinstance(m, dict) and str(m.get("id", "") or "") == keyword:
                music = m
                break
        if not music:
            await self.ctx.send.text(f"未找到歌曲 ID: {keyword}", stream_id)
            return False, "无匹配", True
        cover_b64 = await self._download_cover_base64(str(sid))
        if cover_b64:
            await self.ctx.send.text("正在生成详情图片...", stream_id)
            try:
                img_b64 = await self._render_song_detail_image(music, cover_b64)
                await self.ctx.send.image(img_b64, stream_id)
                return True, "显示详情", True
            except RuntimeError:
                await self.ctx.send.text("图片渲染失败，请确认已安装 playwright", stream_id)
                return False, "渲染失败", True
            except Exception:
                logger.debug("曲目详情图片渲染失败，回退到文本模式", exc_info=True)
        detail = await self._build_song_detail_text(music)
        await self.ctx.send.text(detail, stream_id)
        return True, "显示详情", True

    @Command(
        "mai_lxns_rank",
        description="单曲全球排行榜",
        pattern=r"^/mai lxns rank\s+(?P<song_id>\S+)$",
    )
    async def handle_lxns_rank(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text("排行榜查询需要绑定 lxns: /mai lxns bind <Token>", stream_id)
            return False, "未绑定", True
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai lxns rank <歌曲ID>", stream_id)
            return False, "参数错误", True
        song_id_str = matched_groups["song_id"].strip()
        if not song_id_str.isdigit():
            await self.ctx.send.text("请输入有效的歌曲 ID", stream_id)
            return False, "参数错误", True
        song_id = int(song_id_str)
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        songs = await self._get_songs_cached()
        song_name = str(song_id)
        song_type = "standard"
        if songs:
            for m in songs:
                if isinstance(m, dict) and str(m.get("id", "") or "") == song_id_str:
                    song_name = str(m.get("title", "") or str(song_id))
                    song_type = str(m.get("type", "") or "standard")
                    break
        lines = [f"【排行榜】{_html.escape(song_name)} (ID: {song_id})"]
        results = []
        for li in range(5):
            resp = await self._lxns_auth_call(
                client, "/user/maimai/player/score/ranking", binding,
                params={"song_id": str(song_id), "level_index": str(li), "song_type": song_type},
            )
            if LxnsApiClient._is_error(resp) or not isinstance(resp, list):
                continue
            if not resp:
                continue
            level_label = DIFF_NAMES[li] if li < len(DIFF_NAMES) else str(li)
            lines.append(f"\n[{level_label}]")
            for rank_entry in resp[:5]:
                if not isinstance(rank_entry, dict):
                    continue
                rk = rank_entry.get("ranking", "?")
                pname = rank_entry.get("player_name", "?")
                ach = rank_entry.get("achievements", 0)
                dxs = rank_entry.get("dx_score", 0)
                lines.append(f"  #{rk} {_html.escape(str(pname))}  {ach:.4f}%  ({dxs})")
            results.append(True)
        if not results:
            await self.ctx.send.text(f"未找到歌曲 {song_id} 的排行数据", stream_id)
            return False, "无数据", True
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "显示排行", True

    @Command(
        "mai_lxns_history",
        description="单曲成绩进步轨迹",
        pattern=r"^/mai lxns history\s+(?P<song_id>\S+)$",
    )
    async def handle_lxns_history(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text("请先绑定: /mai lxns bind <Token>", stream_id)
            return False, "未绑定", True
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai lxns history <歌曲ID>", stream_id)
            return False, "参数错误", True
        song_id_str = matched_groups["song_id"].strip()
        if not song_id_str.isdigit():
            await self.ctx.send.text("请输入有效的歌曲 ID", stream_id)
            return False, "参数错误", True
        song_id = int(song_id_str)
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        songs = await self._get_songs_cached()
        song_name = str(song_id)
        song_type = "standard"
        if songs:
            for m in songs:
                if isinstance(m, dict) and str(m.get("id", "") or "") == song_id_str:
                    song_name = str(m.get("title", "") or str(song_id))
                    song_type = str(m.get("type", "") or "standard")
                    break
        lines = [f"【成绩历史】{_html.escape(song_name)} (ID: {song_id})"]
        found = False
        for li in range(5):
            resp = await self._lxns_auth_call(
                client, "/user/maimai/player/score/history", binding,
                params={"song_id": str(song_id), "level_index": str(li), "song_type": song_type},
            )
            if LxnsApiClient._is_error(resp) or not isinstance(resp, list) or not resp:
                continue
            level_label = DIFF_NAMES[li] if li < len(DIFF_NAMES) else str(li)
            lines.append(f"\n[{level_label}]")
            for entry in resp[-10:]:
                if not isinstance(entry, dict):
                    continue
                ach = entry.get("achievements", 0)
                fc = entry.get("fc", "-")
                fs = entry.get("fs", "-")
                upload = str(entry.get("upload_time", ""))[:10]
                lines.append(
                    f"  {upload}  {ach:.4f}%  "
                    f"{_html.escape(str(fc))}/{_html.escape(str(fs))}"
                )
            found = True
        if not found:
            await self.ctx.send.text(f"未找到歌曲 {song_id} 的成绩历史", stream_id)
            return False, "无数据", True
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "显示历史", True

    @Command(
        "mai_lxns_comment",
        description="查看歌曲评论区",
        pattern=r"^/mai lxns comment\s+(?P<song_id>\S+)$",
    )
    async def handle_lxns_comment(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text("请先绑定: /mai lxns bind <Token>", stream_id)
            return False, "未绑定", True
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai lxns comment <歌曲ID>", stream_id)
            return False, "参数错误", True
        song_id_str = matched_groups["song_id"].strip()
        if not song_id_str.isdigit():
            await self.ctx.send.text("请输入有效的歌曲 ID", stream_id)
            return False, "参数错误", True
        song_id = int(song_id_str)
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        resp = await self._lxns_auth_call(
            client, "/user/maimai/comment/list", binding,
            params={"song_id": str(song_id), "page": "1"},
        )
        if LxnsApiClient._is_error(resp):
            await self.ctx.send.text(f"获取评论失败: {resp.get('message', '')}", stream_id)
            return False, "获取失败", True
        comments = resp if isinstance(resp, list) else resp.get("comments", [])
        if not comments:
            await self.ctx.send.text(f"歌曲 {song_id} 暂无评论", stream_id)
            return False, "无数据", True
        lines = [f"【评论区】歌曲 ID: {song_id}"]
        for c in comments[:20]:
            if not isinstance(c, dict):
                continue
            user = c.get("user", {}) or {}
            uname = user.get("name", "?") if isinstance(user, dict) else "?"
            content = c.get("content", "")
            likes = c.get("likes", 0)
            ctime = str(c.get("created_at", ""))[:10]
            lines.append(f"\n{_html.escape(str(uname))} ({ctime})  ❤{likes}")
            lines.append(f"  {_html.escape(str(content)[:200])}")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "显示评论", True

    @Command(
        "mai_lxns_collections",
        description="查看收藏品列表",
        pattern=r"^/mai lxns collections(\s+(?P<ctype>\S+))?$",
    )
    async def handle_lxns_collections(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text("请先绑定: /mai lxns bind <Token>", stream_id)
            return False, "未绑定", True
        ctype = (matched_groups.get("ctype", "") or "").strip() if matched_groups else ""
        valid_types = ["trophy", "plate", "icon", "frame", "character"]
        if ctype not in valid_types:
            await self.ctx.send.text(
                f"用法: /mai lxns collections <种类>\n"
                f"种类: {', '.join(valid_types)}",
                stream_id,
            )
            return False, "参数错误", True
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        resp = await client.get_collections_list(ctype, required=False)
        if LxnsApiClient._is_error(resp):
            await self.ctx.send.text(f"获取收藏品失败: {resp.get('message', '')}", stream_id)
            return False, "获取失败", True
        items = resp if isinstance(resp, list) else resp.get("data", [])
        if not items:
            await self.ctx.send.text(f"暂无 {ctype} 收藏品数据", stream_id)
            return False, "无数据", True
        lines = [f"【收藏品】{ctype} ({len(items)} 件)"]
        for item in items[:30]:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "?")
            rarity = item.get("color", "") or item.get("level", "")
            desc = item.get("description", "")
            line = f"  {_html.escape(str(name))}"
            if rarity:
                line += f"  [{_html.escape(str(rarity))}]"
            if desc:
                line += f"  {_html.escape(str(desc)[:40])}"
            lines.append(line)
        if len(items) > 30:
            lines.append(f"  ... 共 {len(items)} 件，仅显示前 30")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "显示收藏品", True

    @Command(
        "mai_lxns_heatmap",
        description="游玩热力图",
        pattern=r"^/mai lxns heatmap$",
    )
    async def handle_lxns_heatmap(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text("请先绑定: /mai lxns bind <Token>", stream_id)
            return False, "未绑定", True
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        resp = await self._lxns_auth_call(
            client, "/user/maimai/player/heatmap", binding,
        )
        if LxnsApiClient._is_error(resp):
            await self.ctx.send.text(f"获取热力图失败: {resp.get('message', '')}", stream_id)
            return False, "获取失败", True
        if not isinstance(resp, dict):
            resp = {}
        try:
            img_b64 = await self._render_heatmap_image(resp)
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"热力图图片生成失败: {e}", exc_info=True)
            total_uploads = sum(v for v in resp.values() if isinstance(v, (int, float)))
            await self.ctx.send.text(
                f"【游玩热力图概要】\n总出勤天数: {len(resp)}\n总上传成绩: {total_uploads}",
                stream_id,
            )
            return False, "渲染失败", True
        return True, "显示热力图", True

    @Command(
        "mai_lxns_trend",
        description="Rating 趋势",
        pattern=r"^/mai lxns trend(\s+(?P<version>\d+))?$",
    )
    async def handle_lxns_trend(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text("请先绑定: /mai lxns bind <Token>", stream_id)
            return False, "未绑定", True
        version = 25000
        if matched_groups and matched_groups.get("version"):
            version = int(matched_groups["version"])
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        resp = await self._lxns_auth_call(
            client, "/user/maimai/player/trend", binding,
            params={"version": str(version)},
        )
        if LxnsApiClient._is_error(resp):
            await self.ctx.send.text(f"获取趋势失败: {resp.get('message', '')}", stream_id)
            return False, "获取失败", True
        trend_list = resp if isinstance(resp, list) else resp.get("data", [])
        if not trend_list:
            await self.ctx.send.text("暂无 Rating 趋势数据", stream_id)
            return False, "无数据", True
        try:
            img_b64 = await self._render_trend_image(trend_list, version)
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"趋势图片生成失败: {e}", exc_info=True)
            parts = ["【Rating 趋势】"]
            for d in trend_list[-15:]:
                if isinstance(d, dict):
                    date_str = str(d.get("date", ""))[:10]
                    parts.append(
                        f"  {date_str}  RT:{d.get('total', 0)}  "
                        f"(SD:{d.get('standard_total', 0)} DX:{d.get('dx_total', 0)})"
                    )
            await self.ctx.send.text("\n".join(parts), stream_id)
            return False, "渲染失败", True
        return True, "显示趋势", True

    @Command(
        "mai_lxns_year",
        description="年度回顾",
        pattern=r"^/mai lxns year(\s+(?P<year>\d+))?$",
    )
    async def handle_lxns_year(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        binding = await self._get_lxns_binding(kwargs)
        if not binding:
            await self.ctx.send.text("请先绑定: /mai lxns bind <Token>", stream_id)
            return False, "未绑定", True
        year = datetime.now(timezone.utc).year - 1
        if matched_groups and matched_groups.get("year"):
            year = int(matched_groups["year"])
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        await self.ctx.send.text(
            f"正在生成 {year} 年度回顾 (将代表您同意生成数据)...", stream_id,
        )
        resp = await self._lxns_auth_call(
            client, f"/user/maimai/player/year-in-review/{year}", binding,
            params={"agree": "true"},
        )
        if LxnsApiClient._is_error(resp):
            msg = resp.get("message", "")
            if "agree" in msg.lower():
                await self.ctx.send.text("生成年度回顾需要同意数据使用协议，请重试", stream_id)
            else:
                await self.ctx.send.text(f"获取年度回顾失败: {msg}", stream_id)
            return False, "获取失败", True
        if not isinstance(resp, dict):
            await self.ctx.send.text("年度回顾数据格式异常", stream_id)
            return False, "格式错误", True
        try:
            img_b64 = await self._render_year_review_image(resp, year)
            await self.ctx.send.image(img_b64, stream_id)
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False, "渲染失败", True
        except Exception as e:
            logger.warning(f"年度回顾图片生成失败: {e}", exc_info=True)
            await self.ctx.send.text(f"图片生成失败: {e}", stream_id)
            return False, "渲染失败", True
        return True, "显示年度回顾", True

    @Command(
        "mai_lxns_alias_import",
        description="导入 lxns 社区别名",
        pattern=r"^/mai lxns alias import$",
    )
    async def handle_lxns_alias_import(
        self, stream_id: str = "", **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not self.config.lxns.enable:
            await self.ctx.send.text("lxns 功能未启用", stream_id)
            return False, "未启用", True
        client = await self._get_lxns_client()
        if not client:
            await self.ctx.send.text("lxns 客户端初始化失败", stream_id)
            return False, "初始化失败", True
        await self.ctx.send.text("正在从 lxns 导入社区别名，请稍候...", stream_id)

        async def _fetch_page(page: int):
            return await client.get_alias_list(page)

        imported, skipped = await self._aliases.import_from_lxns(
            _fetch_page, None,
        )
        await self.ctx.send.text(
            f"【lxns 别名导入完成】\n新增: {imported} 条\n跳过(已存在): {skipped} 条",
            stream_id,
        )
        return True, "导入别名", True

    # ---- Tool ----

    @Tool(
        "search_mai_songs",
        description="在舞萌 DX 曲库中按名称/艺术家/ID搜索曲目，也能搜索别称",
        parameters=[
            ToolParameterInfo(
                name="keyword",
                param_type=ToolParamType.STRING,
                description="搜索关键词",
                required=True,
            ),
        ],
    )
    async def handle_tool_search_songs(
        self, keyword: str = "", **kwargs: Any
    ) -> dict:
        del kwargs
        songs = await self._get_songs_cached()
        if not songs:
            return {"name": "search_mai_songs", "content": "获取曲目列表失败"}

        if keyword.isdigit():
            for music in songs:
                if isinstance(music, dict) and str(music.get("id", "") or "") == keyword:
                    return {
                        "name": "search_mai_songs",
                        "content": json.dumps(
                            {
                                "id": music.get("id"),
                                "title": music.get("title"),
                                "artist": (music.get("basic_info") or {}).get("artist", ""),
                                "type": music.get("type"),
                                "version": (music.get("basic_info") or {}).get("from", ""),
                                "ds": music.get("ds", []),
                                "level": music.get("level", []),
                            },
                            ensure_ascii=False,
                        ),
                    }
            return {"name": "search_mai_songs", "content": f"未找到歌曲 ID: {keyword}"}

        matches = (await self._match_songs(keyword))[:10]
        if not matches:
            return {
                "name": "search_mai_songs",
                "content": f"未找到匹配 \"{keyword}\" 的曲目",
            }
        result = [
            {
                "id": m.get("id"),
                "title": m.get("title"),
                "artist": (m.get("basic_info") or {}).get("artist", ""),
                "type": m.get("type"),
                "version": (m.get("basic_info") or {}).get("from", ""),
                "max_ds": max(m.get("ds", [0])) if m.get("ds") else 0,
            }
            for m in matches
        ]
        return {
            "name": "search_mai_songs",
            "content": json.dumps(result, ensure_ascii=False),
        }


def create_plugin() -> MaiMaiDXPlugin:
    return MaiMaiDXPlugin()
