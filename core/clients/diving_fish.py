# -*- coding: utf-8 -*-
"""diving-fish（水鱼）API 客户端。"""

import asyncio
from typing import Any

import aiohttp


# 水鱼 /query/plate 的 version 参数必须使用完整版本名称（如 "maimai PLUS"），
# 单字代号（真/超/檄/...）是给用户看的简称，服务端按 music.basic_info.from
# 精确匹配，传简称会匹配不到任何记录。这里统一做 简称 → 完整名称 映射。
# 已按线上 music_data 的全部 distinct 版本值校验：
# - PLUS 子时代（華/煌/星/祝/宴）在曲库中统一标注为基础版本名，故就近映射到基础版本；
# - "ALL FiNALE" 是舞牌/霸者（全版本）特殊值，与 basic_info.from 无关；
# - PRiSM PLUS 有独立的版本值（鏡+）。
_VERSION_FULL_NAMES: dict[str, str] = {
    "真": "maimai PLUS",
    "超": "maimai GreeN",
    "檄": "maimai GreeN PLUS",
    "橙": "maimai ORANGE",
    "暁": "maimai ORANGE PLUS",
    "桃": "maimai PiNK",
    "櫻": "maimai PiNK PLUS",
    "紫": "maimai MURASAKi",
    "菫": "maimai MURASAKi PLUS",
    "白": "maimai MiLK",
    "雪": "MiLK PLUS",
    "輝": "maimai FiNALE",
    "舞": "ALL FiNALE",
    "覇": "ALL FiNALE",
    "熊": "maimai でらっくす",
    "華": "maimai でらっくす",
    "爽": "maimai でらっくす Splash",
    "煌": "maimai でらっくす Splash",
    "宙": "maimai でらっくす UNiVERSE",
    "星": "maimai でらっくす UNiVERSE",
    "祭": "maimai でらっくす FESTiVAL",
    "祝": "maimai でらっくす FESTiVAL",
    "双": "maimai でらっくす BUDDiES",
    "宴": "maimai でらっくす BUDDiES",
    "鏡": "maimai でらっくす PRiSM",
    "鏡+": "maimai でらっくす PRiSM PLUS",
}


class DivingFishApiClient:

    def __init__(
        self, base_url: str, timeout: int, session: aiohttp.ClientSession,
        developer_token: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session
        self._developer_token = developer_token
        # 静态大表 ETag 缓存：music_data / chart_stats 等返回 ETag，
        # 下次请求自动携带 If-None-Match，304 时返回 {"_not_modified": True}。
        self._etags: dict[str, str] = {}

    @staticmethod
    def _error(message: str, status: int = 0) -> dict:
        return {"_error": True, "_status": status, "message": message}

    async def _get(
        self,
        path: str,
        params: dict = None,
        headers: dict = None,
        auth: dict = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        kw: dict[str, Any] = {"timeout": self._timeout}
        merged = dict(headers or {})
        merged.update(self._auth_headers(auth))
        etag = self._etags.get(path)
        if etag:
            merged["If-None-Match"] = etag
        if merged:
            kw["headers"] = merged
        if params:
            kw["params"] = params
        try:
            async with self._session.get(url, **kw) as resp:
                if resp.status == 304:
                    return {"_not_modified": True}
                if resp.status == 200 and resp.headers.get("ETag"):
                    self._etags[path] = resp.headers["ETag"]
                if resp.status == 404:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {}
                    return self._error(data.get("message", "not found"), 404)
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    message = data.get("message", str(data)) if isinstance(data, dict) else str(data)
                    return self._error(message, resp.status)
                return data
        except asyncio.TimeoutError:
            return self._error("请求超时")
        except aiohttp.ClientError as e:
            return self._error(f"网络错误: {e}")
        except Exception as e:
            return self._error(f"未知错误: {e}")

    async def _post(
        self,
        path: str,
        json_data: dict = None,
        headers: dict = None,
        auth: dict = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        kw: dict[str, Any] = {"timeout": self._timeout}
        merged = dict(headers or {})
        merged.update(self._auth_headers(auth))
        if merged:
            kw["headers"] = merged
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

    @staticmethod
    def _auth_headers(auth: dict = None) -> dict[str, str]:
        if not auth or not isinstance(auth, dict):
            return {}
        if str(auth.get("scheme", "")).lower() == "oauth":
            token = str(auth.get("token", "")).strip()
            return {"Authorization": f"Bearer {token}"} if token else {}
        if str(auth.get("scheme", "")).lower() == "import":
            token = str(auth.get("token", "")).strip()
            return {"Import-Token": token} if token else {}
        return {}

    async def get_music_data(self, etag: str = None) -> dict:
        del etag  # 由客户端内部自动携带 If-None-Match
        return await self._get("/music_data")

    async def query_player(self, target: str = "", auth: dict = None) -> dict:
        body: dict[str, Any] = {"b50": "1"}
        target = (target or "").strip()
        if target:
            if target.isdigit():
                body["qq"] = target
            else:
                body["username"] = target
        return await self._post("/query/player", json_data=body, auth=auth)

    async def get_player_records(
        self, import_token: str = "", auth: dict = None
    ) -> dict:
        headers = {}
        if auth:
            return await self._get("/player/records", auth=auth)
        if import_token:
            headers["Import-Token"] = import_token
        return await self._get("/player/records", headers=headers)

    async def token_available(self, token: str) -> dict:
        return await self._get("/token_available", params={"token": token})

    async def alive_check(self) -> dict:
        return await self._get("/alive_check")

    async def get_chart_stats(self, etag: str = None) -> dict:
        del etag
        return await self._get("/chart_stats")

    async def get_maidle_data(self, etag: str = None) -> dict:
        del etag
        return await self._get("/maidle/data")

    async def query_plate(
        self,
        target: str,
        versions: list[str],
        developer_token: str = "",
        auth: dict = None,
    ) -> dict:
        """按版本查询成绩（OAuth 走 /player/plate，否则旧 Developer-Token 走 /query/plate）。

        target 为用户名或 QQ 号（OAuth 时忽略，按 Bearer 定位本人）；versions
        接受中文单字代号（真/超/檄/.../鏡/鏡+）或完整版本名称
        （maimai PLUS / maimai でらっくす PRiSM 等），发送前统一转换为服务端
        要求的完整版本名称。旧回退路径将于 2026-10-01 随水鱼官方迁移停止。
        """

        full_versions = [
            _VERSION_FULL_NAMES.get(v, v) for v in versions
        ]
        body: dict[str, Any] = {"version": full_versions}
        if auth:
            return await self._post(
                "/player/plate",
                json_data=body,
                auth=auth,
            )
        token = developer_token or self._developer_token
        if not token:
            return self._error("未配置水鱼 Developer-Token（config.toml [server].developer_token）")
        target = (target or "").strip()
        if target.isdigit():
            body["qq"] = target
        else:
            body["username"] = target
        return await self._post(
            "/query/plate",
            json_data=body,
            headers={"Developer-Token": token},
        )

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

    async def update_records(
        self,
        import_token: str = "",
        records: list[dict] = None,
        auth: dict = None,
    ) -> dict:
        """批量更新/新建成绩（POST /player/update_records，需 Import-Token）。

        请求体为 JSON List，歌曲唯一凭证是 ``title`` + ``type``，
        ``level_index`` 必须存在；服务端按 chart 归并（新建或覆盖）后重算 RA。
        """

        if auth:
            return await self._post(
                "/player/update_records",
                json_data=records,
                auth=auth,
            )
        return await self._post(
            "/player/update_records",
            json_data=records,
            headers={"Import-Token": import_token} if import_token else {},
        )

    async def get_hot_music(self) -> dict:
        """热门歌曲加权统计（新曲 ×2、≥13 级 ×2、≥13.7 ×3，权重和为 1）。"""

        return await self._get("/hot_music")

    async def get_rating_ranking(self) -> dict:
        """公开 DX Rating 排行榜（不含隐私用户；服务端未排序）。"""

        return await self._get("/rating_ranking")
