# -*- coding: utf-8 -*-
"""水鱼（diving-fish）OAuth 绑定存储：QQ 用户 → 水鱼账号凭据。

公开客户端设备码流程：每个用户授权后，插件保存该用户自己的 access_token、
refresh_token、expires_at 与 waterfish sub/username。
"""

from datetime import datetime, timezone
from typing import Any, Optional

from .json_store import JsonStore


class DivingFishBindingStore(JsonStore):

    async def get(self, user_id: str) -> Optional[dict[str, Any]]:
        return await super().get(user_id)

    async def set_oauth(
        self,
        user_id: str,
        username: str,
        sub: str,
        access_token: str,
        refresh_token: str,
        expires_at: str,
        scope: str = "",
    ) -> None:
        async with self._lock:
            self._data[user_id] = {
                "mode": "oauth",
                "username": username,
                "sub": sub,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "scope": scope,
                "bound_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._save()

    async def update_tokens(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: str,
    ) -> bool:
        """刷新后更新令牌；绑定不存在或非 oauth 模式时返回 False。"""
        async with self._lock:
            binding = self._data.get(user_id)
            if not binding or binding.get("mode") != "oauth":
                return False
            binding["access_token"] = access_token
            binding["refresh_token"] = refresh_token
            binding["expires_at"] = expires_at
            await self._save()
            return True

    async def delete(self, user_id: str) -> bool:
        async with self._lock:
            if user_id in self._data:
                del self._data[user_id]
                await self._save()
                return True
            return False
