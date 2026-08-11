# -*- coding: utf-8 -*-
"""落雪（lxns）绑定存储：QQ 用户 → 落雪账号凭据。

支持两种绑定模式：
- ``oauth``：access_token / refresh_token / expires_at（推荐，支持全部功能）；
- ``personal_token``：个人 API 密钥（仅玩家信息与成绩相关端点）。
"""

from datetime import datetime, timezone
from typing import Any, Optional

from .json_store import JsonStore


class LxnsBindingStore(JsonStore):

    async def get(self, user_id: str) -> Optional[dict[str, Any]]:
        return await super().get(user_id)

    async def set_oauth(
        self,
        user_id: str,
        username: str,
        friend_code: Optional[int],
        access_token: str,
        refresh_token: str,
        expires_at: str,
        scope: str = "",
    ) -> None:
        async with self._lock:
            self._data[user_id] = {
                "mode": "oauth",
                "username": username,
                "friend_code": friend_code,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "scope": scope,
                "bound_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._save()

    async def set_personal_token(
        self,
        user_id: str,
        username: str,
        friend_code: Optional[int],
        personal_token: str,
    ) -> None:
        async with self._lock:
            self._data[user_id] = {
                "mode": "personal_token",
                "username": username,
                "friend_code": friend_code,
                "personal_token": personal_token,
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
        """OAuth 刷新后更新令牌；绑定不存在或非 oauth 模式时返回 False。"""

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
