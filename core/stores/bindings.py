# -*- coding: utf-8 -*-
"""水鱼 Import-Token 绑定存储。"""

from datetime import datetime, timezone
from typing import Any, Optional

from .json_store import JsonStore


class BindingStore(JsonStore):

    async def get(self, user_id: str) -> Optional[dict[str, Any]]:
        return await super().get(user_id)

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
