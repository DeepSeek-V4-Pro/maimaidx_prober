# -*- coding: utf-8 -*-
"""lxns（落雪）API 客户端 — 仅保留公开接口，用于数据补全。

v2.0 起移除全部需要认证的端点（个人成绩/B50/热力图/趋势/年度回顾等），
只保留公开的曲库、别名、状态等数据补全能力。
"""

import asyncio
from typing import Any

import aiohttp


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
        self, path: str, params: dict = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        kw: dict[str, Any] = {"timeout": self._timeout}
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

    # ---- 公开端点 ----

    async def get_song_list(self) -> dict:
        return await self._get("/maimai/song/list")

    async def get_alias_list(self, page: int = 1) -> dict:
        return await self._get("/maimai/alias/list", params={"page": str(page)})

    async def alive_check(self) -> dict:
        return await self._get("/maimai/song/list")

    # ---- 工具方法 ----

    @staticmethod
    def get_cover_url(asset_url: str, song_id: int) -> str:
        resource_id = song_id % 10000
        return f"{asset_url.rstrip('/')}/maimai/jacket/{resource_id}.png"

    @property
    def asset_url(self) -> str:
        return self._asset_url
