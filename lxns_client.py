"""lxns API 客户端 — 封装 maimai.lxns.net 全部接口"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class LxnsBindingStore:

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

    async def set(self, user_id: str, token: str, username: str = "unknown",
                  auth_method: str = "Bearer") -> None:
        async with self._lock:
            self._data[user_id] = {
                "token": token,
                "username": username,
                "auth_method": auth_method,
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


class LxnsApiClient:

    def __init__(
        self, base_url: str, asset_url: str, timeout: int,
        session: aiohttp.ClientSession,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._asset_url = asset_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session

    @staticmethod
    def _error(message: str, status: int = 0) -> dict:
        return {"_error": True, "_status": status, "message": message}

    @staticmethod
    def _is_error(resp: Any) -> bool:
        return isinstance(resp, dict) and resp.get("_error", False)

    async def _get(
        self, path: str, params: dict = None, token: str = None,
        auth_header: str = "Bearer",
    ) -> dict:
        url = f"{self._base_url}{path}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            if auth_header.startswith("param:"):
                param_name = auth_header[6:]
                if params is None:
                    params = {}
                params = dict(params)
                params[param_name] = token
            elif auth_header in ("X-API-Key", "Import-Token"):
                headers[auth_header] = token
            elif auth_header == "Raw":
                headers["Authorization"] = token
            elif auth_header == "Token":
                headers["Authorization"] = f"Token {token}"
            else:
                headers["Authorization"] = f"Bearer {token}"
        kw: dict[str, Any] = {"timeout": self._timeout, "headers": headers}
        if params:
            kw["params"] = params
        try:
            async with self._session.get(url, **kw) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    return self._error(
                        data.get("message", str(data)), resp.status
                    )
                return data
        except asyncio.TimeoutError:
            return self._error("请求超时")
        except aiohttp.ClientError as e:
            return self._error(f"网络错误: {e}")
        except Exception as e:
            return self._error(f"未知错误: {e}")

    async def _post(
        self, path: str, json_data: dict = None, token: str = None,
        auth_header: str = "Bearer",
    ) -> dict:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            if auth_header.startswith("param:"):
                sep = "&" if "?" in path else "?"
                path = f"{path}{sep}{auth_header[6:]}={token}"
            elif auth_header in ("X-API-Key", "Import-Token"):
                headers[auth_header] = token
            elif auth_header == "Raw":
                headers["Authorization"] = token
            elif auth_header == "Token":
                headers["Authorization"] = f"Token {token}"
            else:
                headers["Authorization"] = f"Bearer {token}"
        url = f"{self._base_url}{path}"
        kw: dict[str, Any] = {
            "timeout": self._timeout, "headers": headers,
        }
        if json_data is not None:
            kw["json"] = json_data
        try:
            async with self._session.post(url, **kw) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    return self._error(
                        data.get("message", str(data)), resp.status
                    )
                return data
        except asyncio.TimeoutError:
            return self._error("请求超时")
        except aiohttp.ClientError as e:
            return self._error(f"网络错误: {e}")
        except Exception as e:
            return self._error(f"未知错误: {e}")

    @staticmethod
    def _unwrap_auth(resp: dict) -> dict:
        """解包 lxns 认证接口的 {success, data} 包装"""
        if LxnsApiClient._is_error(resp):
            return resp
        if isinstance(resp, dict):
            if resp.get("success") is False:
                return LxnsApiClient._error(
                    resp.get("message", "未知错误"), resp.get("code", 0)
                )
            if "data" in resp:
                return resp["data"]
        return resp

    # ---- 公开端点 ----

    async def get_song_list(self) -> dict:
        return await self._get("/maimai/song/list")

    async def get_song_detail(self, song_id: int, version: int = None) -> dict:
        params = {"version": str(version)} if version is not None else None
        return await self._get(f"/maimai/song/{song_id}", params=params)

    async def get_song_collections(self, song_id: int) -> dict:
        return await self._get(f"/maimai/song-collections/{song_id}")

    async def get_alias_list(self, page: int = 1) -> dict:
        return await self._get("/maimai/alias/list", params={"page": str(page)})

    async def get_collections_list(
        self, collection_type: str, required: bool = True,
    ) -> dict:
        return await self._get(
            f"/maimai/{collection_type}/list",
            params={"required": str(required).lower()},
        )

    async def get_crawl_statistic(self) -> dict:
        return await self._get("/maimai/crawl/statistic")

    async def alive_check(self) -> dict:
        return await self._get("/maimai/song/list")

    # ---- 认证端点 ----

    async def get_player(self, token: str) -> dict:
        return self._unwrap_auth(
            await self._get("/user/maimai/player", token=token)
        )

    async def get_bests(self, token: str) -> dict:
        return self._unwrap_auth(
            await self._get("/user/maimai/player/bests", token=token)
        )

    async def get_scores(self, token: str) -> dict:
        return self._unwrap_auth(
            await self._get("/user/maimai/player/scores", token=token)
        )

    async def get_heatmap(self, token: str) -> dict:
        return self._unwrap_auth(
            await self._get("/user/maimai/player/heatmap", token=token)
        )

    async def get_rating_trend(
        self, token: str, version: int = 25000,
    ) -> dict:
        return self._unwrap_auth(
            await self._get(
                "/user/maimai/player/trend",
                params={"version": str(version)},
                token=token,
            )
        )

    async def get_score_ranking(
        self, token: str, song_id: int, level_index: int,
        song_type: str = "standard",
    ) -> dict:
        params = {
            "song_id": str(song_id),
            "level_index": str(level_index),
            "song_type": song_type,
        }
        return self._unwrap_auth(
            await self._get(
                "/user/maimai/player/score/ranking",
                params=params, token=token,
            )
        )

    async def get_score_history(
        self, token: str, song_id: int, level_index: int,
        song_type: str = "standard",
    ) -> dict:
        params = {
            "song_id": str(song_id),
            "level_index": str(level_index),
            "song_type": song_type,
        }
        return self._unwrap_auth(
            await self._get(
                "/user/maimai/player/score/history",
                params=params, token=token,
            )
        )

    async def get_comments(
        self, token: str, song_id: int, page: int = 1,
    ) -> dict:
        params = {"song_id": str(song_id), "page": str(page)}
        return self._unwrap_auth(
            await self._get(
                "/user/maimai/comment/list", params=params, token=token,
            )
        )

    async def get_player_collection(
        self, token: str, collection_type: str, item_id: int,
    ) -> dict:
        return self._unwrap_auth(
            await self._get(
                f"/user/maimai/player/{collection_type}/{item_id}",
                token=token,
            )
        )

    async def get_year_in_review(
        self, token: str, year: int, agree: bool = True,
    ) -> dict:
        params = {"agree": "true"} if agree else {}
        return self._unwrap_auth(
            await self._get(
                f"/user/maimai/player/year-in-review/{year}",
                params=params, token=token,
            )
        )

    async def vote_alias(
        self, token: str, alias_id: int, vote_up: bool,
    ) -> dict:
        direction = "up" if vote_up else "down"
        return self._unwrap_auth(
            await self._post(
                f"/user/maimai/alias/{alias_id}/vote/{direction}",
                token=token,
            )
        )

    # ---- 工具方法 ----

    @staticmethod
    def get_cover_url(asset_url: str, song_id: int) -> str:
        resource_id = song_id % 10000
        return f"{asset_url.rstrip('/')}/maimai/jacket/{resource_id}.png"

    @property
    def asset_url(self) -> str:
        return self._asset_url
