# -*- coding: utf-8 -*-
"""曲库与统计服务：缓存、匹配、lxns 数据补全。"""

import logging
import time
from typing import Any, Optional

from ..clients.diving_fish import DivingFishApiClient
from ..clients.lxns import LxnsApiClient
from ..stores.aliases import AliasStore

logger = logging.getLogger(__name__)


class MusicService:

    def __init__(
        self,
        df_client: DivingFishApiClient,
        lxns_client: Optional[LxnsApiClient],
        aliases: AliasStore,
        server_ttl: int,
        lxns_ttl: int,
    ) -> None:
        self._df = df_client
        self._lxns = lxns_client
        self._aliases = aliases
        self._server_ttl = server_ttl
        self._lxns_ttl = lxns_ttl

        self._song_cache: Optional[list[dict]] = None
        self._song_cache_time: float = 0.0
        self._chart_stats_cache: Optional[dict] = None
        self._chart_stats_cache_time: float = 0.0
        self._lxns_song_cache: Optional[dict] = None
        self._lxns_song_cache_time: float = 0.0
        self._lxns_by_id: dict[int, dict] = {}
        self._df_by_lxns_id: dict[int, dict] = {}

    def invalidate(self) -> None:
        self._song_cache = None
        self._song_cache_time = 0.0
        self._chart_stats_cache = None
        self._chart_stats_cache_time = 0.0
        self._lxns_song_cache = None
        self._lxns_song_cache_time = 0.0
        self._lxns_by_id = {}
        self._df_by_lxns_id = {}

    # ---- 水鱼曲库 ----

    async def get_songs(self) -> Optional[list[dict]]:
        now = time.time()
        if self._song_cache and (now - self._song_cache_time) < self._server_ttl:
            return self._song_cache
        resp = await self._df.get_music_data()
        if isinstance(resp, list):
            self._song_cache = resp
            self._song_cache_time = now
            return resp
        if isinstance(resp, dict) and resp.get("_not_modified"):
            # 304：曲库未变更，刷新缓存时间后继续使用旧数据
            self._song_cache_time = now
            return self._song_cache
        if self._song_cache is not None:
            return self._song_cache
        logger.warning("曲库数据获取失败且无本地缓存可用")
        return None

    async def get_chart_stats(self) -> Optional[dict]:
        now = time.time()
        if self._chart_stats_cache and (now - self._chart_stats_cache_time) < self._server_ttl:
            return self._chart_stats_cache
        resp = await self._df.get_chart_stats()
        if isinstance(resp, dict) and resp.get("_not_modified"):
            self._chart_stats_cache_time = now
            return self._chart_stats_cache
        if isinstance(resp, dict) and not resp.get("_error"):
            self._chart_stats_cache = resp
            self._chart_stats_cache_time = now
            return resp
        return self._chart_stats_cache

    async def match_songs(self, keyword: str) -> list[dict]:
        songs = self._song_cache or await self.get_songs()
        if not songs:
            return []
        kw = keyword.lower()
        results: list[dict] = []
        seen_ids: set[str] = set()

        alias_sids = await self._aliases.search(keyword)

        for music in songs:
            if not isinstance(music, dict):
                continue
            sid = str(music.get("id", "") or "")
            if not sid or sid in seen_ids:
                continue
            title = str(music.get("title", "")).lower()
            bi = music.get("basic_info", {})
            artist = str(bi.get("artist", "")).lower() if isinstance(bi, dict) else ""
            if kw in title or kw in artist or kw == sid or sid in alias_sids:
                seen_ids.add(sid)
                results.append(music)

        if not results:
            words = [
                w.strip(" '\"/-()[]{}")
                for w in kw.split()
                if len(w.strip(" '\"/-()[]{}")) > 1
            ]
            for music in songs:
                if not isinstance(music, dict):
                    continue
                sid = str(music.get("id", "") or "")
                if not sid or sid in seen_ids:
                    continue
                title = str(music.get("title", "")).lower()
                bi = music.get("basic_info", {})
                artist = str(bi.get("artist", "")).lower() if isinstance(bi, dict) else ""
                if any(w in title or w in artist for w in words):
                    seen_ids.add(sid)
                    results.append(music)

        def _sort_key(m: dict) -> int:
            try:
                return int(str(m.get("id", "0") or "0"))
            except (TypeError, ValueError):
                return 0

        results.sort(key=_sort_key)
        return results

    async def find_lxns_song(
        self, keyword: str,
    ) -> tuple[Optional[dict], str]:
        """按关键词/ID 解析落雪曲目，返回 (lxns_song, 错误信息)。

        优先用 ID 直查（含水鱼 ID −10000 的候选），再用水鱼曲库匹配
        标题交叉确认，最后退回落雪曲库标题子串搜索。
        """

        cache = await self._get_lxns_cache()
        if not cache:
            return None, "落雪曲库不可用"
        if not self._lxns_by_id:
            self._rebuild_lxns_index()

        keyword = keyword.strip()
        if keyword.isdigit():
            sid_int = int(keyword)
            direct = self._lxns_by_id.get(sid_int)
            if direct is not None:
                return direct, ""
            alt = sid_int - 10000
            if alt > 0 and alt in self._lxns_by_id:
                return self._lxns_by_id[alt], ""

        matches = await self.match_songs(keyword)
        for m in matches:
            try:
                mid = int(m.get("id", 0))
            except (TypeError, ValueError):
                continue
            if not mid:
                continue
            lxns_song = self._find_lxns_song(mid, m.get("title"))
            if lxns_song:
                return lxns_song, ""

        kw = keyword.lower()
        for s in self._lxns_by_id.values():
            if kw in str(s.get("title", "") or "").lower():
                return s, ""
        return None, f"未找到曲目: {keyword}"

    # ---- lxns 公开数据补全 ----

    async def _get_lxns_cache(self) -> Optional[dict]:
        if self._lxns is None:
            return None
        now = time.time()
        if self._lxns_song_cache and (now - self._lxns_song_cache_time) < self._lxns_ttl:
            return self._lxns_song_cache
        resp = await self._lxns.get_song_list()
        if isinstance(resp, dict) and not resp.get("_error"):
            self._lxns_song_cache = resp
            self._lxns_song_cache_time = now
            self._rebuild_lxns_index()
            return resp
        return self._lxns_song_cache

    def _rebuild_lxns_index(self) -> None:
        self._lxns_by_id = {}
        cache = self._lxns_song_cache
        if not cache:
            return
        for s in cache.get("songs", []):
            if isinstance(s, dict) and s.get("id") is not None:
                try:
                    self._lxns_by_id[int(s["id"])] = s
                except (TypeError, ValueError):
                    continue

    def _rebuild_df_by_lxns_index(self, songs: list[dict]) -> None:
        """构建 落雪歌曲 ID → 水鱼歌曲 的反向索引。

        两个查分器 ID 体系：老曲 lxns id == 水鱼 id，新曲 lxns id == 水鱼 id − 10000。
        """

        self._df_by_lxns_id = {}
        for music in songs:
            if not isinstance(music, dict):
                continue
            try:
                sid = int(music.get("id", 0))
            except (TypeError, ValueError):
                continue
            if not sid:
                continue
            # 老曲：lxns id == 水鱼 id
            self._df_by_lxns_id[sid] = music
            # 新曲：lxns id == 水鱼 id − 10000
            alt = sid - 10000
            if alt > 0:
                self._df_by_lxns_id.setdefault(alt, music)

    async def get_df_song_by_lxns_id(self, lxns_id: int) -> Optional[dict]:
        """按落雪歌曲 ID 反查水鱼曲目（用于补定数、封面 ID、成绩上传映射）。"""

        if not self._df_by_lxns_id:
            songs = self._song_cache or await self.get_songs()
            if not songs:
                return None
            self._rebuild_df_by_lxns_index(songs)
        return self._df_by_lxns_id.get(int(lxns_id))

    def _find_lxns_song(self, song_id: int, title: Any) -> Optional[dict]:
        """按水鱼歌曲 ID 在 lxns 曲库中匹配对应歌曲。

        两个查分器的 ID 体系不同：老曲 lxns id == 水鱼 id，
        新曲 lxns id == 水鱼 id - 10000（如 11115 → 1115）。
        先按 ID 候选（直连优先），再按标题交叉确认，避免错配。
        """
        if not self._lxns_by_id:
            return None
        candidates: list[dict] = []
        direct = self._lxns_by_id.get(song_id)
        if direct is not None:
            candidates.append(direct)
        alt = song_id - 10000
        if alt > 0 and alt in self._lxns_by_id:
            candidates.append(self._lxns_by_id[alt])
        if not candidates:
            return None
        norm_title = str(title or "").strip().lower()
        for cand in candidates:
            if str(cand.get("title", "") or "").strip().lower() == norm_title:
                return cand
        return candidates[0]

    def _resolve_genre_name(self, genre_id: Any) -> str:
        cache = self._lxns_song_cache
        if not cache:
            return str(genre_id)
        for g in cache.get("genres", []):
            if not isinstance(g, dict):
                continue
            # 歌曲 genre 字段是代码串（如 POPSアニメ），也可能是 id
            if g.get("genre") == genre_id or g.get("id") == genre_id:
                return str(g.get("title", "") or g.get("genre", str(genre_id)))
        return str(genre_id)

    def _resolve_version_name(self, version: Any) -> str:
        cache = self._lxns_song_cache
        if not cache:
            return str(version)
        versions = [v for v in cache.get("versions", []) if isinstance(v, dict)]
        for v in versions:
            if v.get("version") == version:
                return str(v.get("title", str(version)))
        # 子版本号（如 21001）取不超过它的最近版本
        try:
            vnum = int(version)
        except (TypeError, ValueError):
            return str(version)
        best: Optional[tuple[int, dict]] = None
        for v in versions:
            try:
                cand = int(v.get("version"))
            except (TypeError, ValueError):
                continue
            if cand <= vnum and (best is None or cand > best[0]):
                best = (cand, v)
        if best is not None:
            return str(best[1].get("title", str(version)))
        return str(version)

    async def enrich_with_lxns(self, music: dict) -> dict:
        sid_val = music.get("id", 0)
        try:
            sid_int = int(sid_val)
        except (TypeError, ValueError):
            return {}
        if not sid_int:
            return {}
        cache = await self._get_lxns_cache()
        if not cache:
            return {}
        if not self._lxns_by_id:
            self._rebuild_lxns_index()
        lxns_song = self._find_lxns_song(sid_int, music.get("title"))
        if not lxns_song:
            return {}
        return {
            "genre_name": self._resolve_genre_name(lxns_song.get("genre", "")),
            "version_name": self._resolve_version_name(lxns_song.get("version", 0)),
            "map_name": lxns_song.get("map", ""),
            "difficulties": lxns_song.get("difficulties", {}),
        }

    # ---- Maidle 歌曲池 ----

    async def get_maidle_song_ids(self, maidle_data_resp: Any) -> list[int]:
        song_ids: list[int] = []
        if isinstance(maidle_data_resp, list):
            for item in maidle_data_resp:
                sid = item.get("id", "") if isinstance(item, dict) else str(item)
                if sid and str(sid).isdigit():
                    song_ids.append(int(sid))
        elif isinstance(maidle_data_resp, dict) and not maidle_data_resp.get("_error"):
            for key in ("songs", "data", "list"):
                val = maidle_data_resp.get(key)
                if isinstance(val, list):
                    for item in val:
                        sid = item.get("id", "") if isinstance(item, dict) else str(item)
                        if sid and str(sid).isdigit():
                            song_ids.append(int(sid))
                    break
            if not song_ids:
                for key in maidle_data_resp:
                    if str(key).isdigit():
                        song_ids.append(int(key))
        if not song_ids:
            songs = await self.get_songs()
            if songs:
                for m in songs:
                    if isinstance(m, dict):
                        sid = str(m.get("id", "") or "")
                        if sid and sid.isdigit():
                            song_ids.append(int(sid))
        return song_ids
