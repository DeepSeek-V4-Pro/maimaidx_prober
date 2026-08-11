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
        imported = 0
        skipped = 0
        page = 1
        max_pages = 100  # 防呆：服务端异常时避免无限翻页
        pending: list[tuple[str, str]] = []
        while page <= max_pages:
            resp = await fetch_page(page)
            if not isinstance(resp, dict) or resp.get("_error"):
                break
            aliases = resp.get("aliases", [])
            if not isinstance(aliases, list) or not aliases:
                break
            for entry in aliases:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("approved", False):
                    continue
                alias_text = entry.get("alias", "")
                song = entry.get("song", {})
                song_id = str(song.get("id", "") if isinstance(song, dict) else "")
                if not alias_text or not song_id:
                    continue
                pending.append((alias_text.strip(), song_id))
            page += 1
            page_count = resp.get("page_count", 0)
            if page > page_count:
                break
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
