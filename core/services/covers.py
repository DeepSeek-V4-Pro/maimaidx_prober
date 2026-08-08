# -*- coding: utf-8 -*-
"""封面下载服务。

核心修复（v2.0）：不再盲目信任 HTTP 200。
lxns CDN 会对部分客户端（如 Python 3.12 的 TLS 指纹）返回
「HTTP 200 + JS 反爬挑战页」，旧版本会把 HTML 当作 PNG 内嵌到图片里，
导致运势/曲目详情等卡片曲绘缺失。本服务按图片魔数校验内容，
仅接受真正的图片，并自动识别 MIME；lxns 失败时回退 diving-fish。
"""

import asyncio
import base64
import logging
from collections import OrderedDict
from typing import Optional

import aiohttp

from ..clients.lxns import LxnsApiClient

logger = logging.getLogger(__name__)

# 魔数 -> (MIME, 说明)
_MAGIC_MIME: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # RIFF....WEBP 由 sniff 进一步确认
]

_MIN_IMAGE_BYTES = 128


def sniff_mime(data: bytes) -> Optional[str]:
    """根据文件头判断图片类型；非图片返回 None。"""
    if len(data) < _MIN_IMAGE_BYTES:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _df_cover_url(song_id: str) -> str:
    sid = int(song_id)
    if 10001 <= sid <= 11000:
        padded = str(sid - 10000).zfill(5)
    else:
        padded = str(sid).zfill(5)
    return f"https://www.diving-fish.com/covers/{padded}.png"


class CoverService:

    def __init__(
        self,
        session: aiohttp.ClientSession,
        lxns: Optional[LxnsApiClient],
        lxns_enabled: bool,
    ) -> None:
        self._session = session
        self._lxns = lxns
        self._lxns_enabled = lxns_enabled
        self._cache: "OrderedDict[str, Optional[str]]" = OrderedDict()
        self._b64_cache: "OrderedDict[str, str]" = OrderedDict()
        self._max_cache = 300

    def _cache_set(self, key: str, mime: Optional[str], b64: Optional[str]) -> None:
        if mime is None:
            self._cache[key] = None
            return
        self._cache[key] = mime
        if b64 is not None:
            self._b64_cache[key] = b64
        while len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)
        while len(self._b64_cache) > self._max_cache:
            self._b64_cache.popitem(last=False)

    async def _download_validated(self, url: str) -> Optional[tuple[bytes, str]]:
        for attempt in range(3):
            try:
                async with self._session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.read()
                    mime = sniff_mime(data)
                    if mime:
                        return data, mime
                    # 200 但内容不是图片（WAF 挑战页 / 错误页），不再重试
                    logger.debug(
                        "封面响应非图片内容 (status=200): %s bytes=%d", url, len(data)
                    )
                    return None
            except (asyncio.TimeoutError, aiohttp.ClientError):
                if attempt < 2:
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug("封面下载异常: %s %s", url, e)
                if attempt < 2:
                    await asyncio.sleep(0.5)
        return None

    async def get_cover(self, song_id: str) -> Optional[dict[str, str]]:
        """返回 {"mime": ..., "b64": ...}；失败返回 None。"""
        key = str(song_id)
        if key in self._cache:
            cached = self._cache[key]
            if cached:
                b64 = self._b64_cache.get(key, "")
                if b64:
                    return {"mime": cached, "b64": b64}
            return None

        result: Optional[tuple[bytes, str]] = None
        if self._lxns_enabled and self._lxns:
            lxns_url = LxnsApiClient.get_cover_url(
                self._lxns.asset_url, int(song_id)
            )
            result = await self._download_validated(lxns_url)

        if result is None:
            result = await self._download_validated(_df_cover_url(song_id))

        if result is None:
            self._cache_set(key, None, None)
            logger.debug(f"封面下载失败 (lxns + diving-fish 双源): song_id={song_id}")
            return None

        data, mime = result
        b64 = base64.b64encode(data).decode()
        self._cache_set(key, mime, b64)
        return {"mime": mime, "b64": b64}

    async def get_cover_data_url(self, song_id: str) -> Optional[str]:
        info = await self.get_cover(song_id)
        if not info:
            return None
        return f"data:{info['mime']};base64,{info['b64']}"

    def invalidate(self) -> None:
        self._cache.clear()
        self._b64_cache.clear()
