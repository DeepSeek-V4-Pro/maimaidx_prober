# -*- coding: utf-8 -*-
"""Maidle 猜歌会话管理。"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_SESSION_TTL = 900


class MaidleManager:

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._cleanup_task is None:
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._cleanup_loop())
            except RuntimeError:
                pass

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def get_or_create(self, user_id: str) -> Optional[dict]:
        async with self._lock:
            existing = self._sessions.get(user_id)
            if existing and time.time() - existing["started_at"] < _SESSION_TTL:
                return existing
            if existing:
                del self._sessions[user_id]
            return None

    async def create(self, user_id: str, uuid: str) -> None:
        async with self._lock:
            self._sessions[user_id] = {"uuid": uuid, "started_at": time.time()}

    async def get(self, user_id: str) -> Optional[dict]:
        async with self._lock:
            session = self._sessions.get(user_id)
            if not session:
                return None
            if time.time() - session["started_at"] > _SESSION_TTL:
                del self._sessions[user_id]
                return None
            return session

    async def pop(self, user_id: str) -> Optional[dict]:
        async with self._lock:
            return self._sessions.pop(user_id, None)

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            now = time.time()
            async with self._lock:
                expired = [
                    uid for uid, s in self._sessions.items()
                    if now - s["started_at"] > _SESSION_TTL
                ]
                for uid in expired:
                    del self._sessions[uid]
            if expired:
                logger.debug("已清理过期 Maidle 会话: %d 个", len(expired))
