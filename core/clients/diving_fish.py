# -*- coding: utf-8 -*-
"""diving-fish（水鱼）API 客户端。"""

import asyncio
from typing import Any

import aiohttp


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
