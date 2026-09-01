# -*- coding: utf-8 -*-
"""JSON 文件存储基类：异步锁 + 原子写入。"""

import asyncio
import json
from pathlib import Path
from typing import Any


class JsonStore:

    def __init__(self, filepath: str) -> None:
        self._filepath = Path(filepath)
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {}

    async def load(self) -> None:
        try:
            if self._filepath.exists():
                content = self._filepath.read_text(encoding="utf-8")
                if content.strip():
                    loaded = json.loads(content)
                    if isinstance(loaded, dict):
                        self._data = loaded
        except (json.JSONDecodeError, OSError):
            self._data = {}

    async def _save(self) -> None:
        try:
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._filepath.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._filepath)
        except OSError:
            pass

    async def get(self, user_id: str) -> Any:
        async with self._lock:
            return self._data.get(user_id)

    async def all(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._data)

    async def replace_all(self, data: dict[str, Any]) -> None:
        """整体替换存储内容（用于数据目录迁移）。"""

        async with self._lock:
            self._data = dict(data)
            await self._save()
