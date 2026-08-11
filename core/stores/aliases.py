# -*- coding: utf-8 -*-
"""别称存储：歌曲 ID → 别称列表，带反序索引搜索。"""

from .json_store import JsonStore


class AliasStore(JsonStore):

    def __init__(self, filepath: str) -> None:
        super().__init__(filepath)
        self._index: dict[str, str] = {}

    async def load(self) -> None:
        await super().load()
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._index.clear()
        for sid, aliases in self._data.items():
            if not isinstance(aliases, list):
                continue
            for a in aliases:
                self._index[str(a).lower()] = str(sid)

    async def add(self, song_id: str, alias: str) -> tuple[bool, str]:
        async with self._lock:
            normalized = alias.strip()
            if not normalized or len(normalized) > 30:
                return False, "别称无效（长度 1-30）"
            key = normalized.lower()
            if key in self._index and self._index[key] != str(song_id):
                return False, f"别称「{normalized}」已被歌曲 {self._index[key]} 使用"
            sid = str(song_id)
            if sid not in self._data:
                self._data[sid] = []
            if normalized not in self._data[sid]:
                self._data[sid].append(normalized)
                self._index[key] = sid
                await self._save()
                return True, "添加成功"
            return True, "别称已存在"

    async def delete(self, song_id: str, alias: str) -> tuple[bool, str]:
        async with self._lock:
            sid = str(song_id)
            if sid not in self._data:
                return False, f"歌曲 {song_id} 没有别称"
            normalized = alias.strip()
            if normalized not in self._data[sid]:
                return False, f"别称「{normalized}」不存在"
            self._data[sid].remove(normalized)
            if not self._data[sid]:
                del self._data[sid]
            key = normalized.lower()
            if self._index.get(key) == sid:
                del self._index[key]
            await self._save()
            return True, "删除成功"

    async def list_aliases(self, song_id: str) -> list[str]:
        async with self._lock:
            return list(self._data.get(str(song_id), []))

    async def search(self, keyword: str) -> list[str]:
        async with self._lock:
            key = keyword.lower()
            results: list[str] = []
            if key in self._index:
                results.append(self._index[key])
            for alias_lower, sid in self._index.items():
                if key in alias_lower and sid not in results:
                    results.append(sid)
            return results

    async def import_from_lxns(
        self, fetch_page,
    ) -> tuple[int, int]:
        """导入落雪公开社区别名（GET /maimai/alias/list）。

        真实返回结构：``{"aliases": [{"song_id": 8, "aliases": ["真爱歌", ...]}]}``，
        单次请求返回全量（无分页字段）。
        """

        imported = 0
        skipped = 0
        resp = await fetch_page(1)
        if not isinstance(resp, dict) or resp.get("_error"):
            return imported, skipped
        aliases = resp.get("aliases", [])
        if not isinstance(aliases, list) or not aliases:
            return imported, skipped

        pending: list[tuple[str, str]] = []
        for entry in aliases:
            if not isinstance(entry, dict):
                continue
            song_id = str(entry.get("song_id", "") or "")
            alias_list = entry.get("aliases")
            if not song_id or not isinstance(alias_list, list):
                continue
            for alias_text in alias_list:
                text = str(alias_text or "").strip()
                if text:
                    pending.append((text, song_id))

        async with self._lock:
            for alias_text, song_id in pending:
                key = alias_text.lower()
                if key in self._index:
                    skipped += 1
                    continue
                self._data.setdefault(song_id, [])
                if alias_text not in self._data[song_id]:
                    self._data[song_id].append(alias_text)
                    self._index[key] = song_id
                    imported += 1
        if imported > 0:
            await self._save()
        return imported, skipped
