# -*- coding: utf-8 -*-
"""命令公共辅助。"""

import html as _html
import logging
from typing import Any, Callable, Coroutine, Optional

from ..util import build_difficulty_detail_text, get_user_id

logger = logging.getLogger(__name__)


class SharedHelpersMixin:

    def _get_user_id(self, kwargs: dict) -> str:
        return get_user_id(kwargs)

    async def _track_user(self, stream_id: str, user_id: str) -> None:
        await self._ensure_clients()
        async with self._stream_users_lock:
            if len(self._stream_users) >= 5000:
                for _ in range(min(1000, len(self._stream_users))):
                    self._stream_users.popitem(last=False)
            self._stream_users[stream_id] = user_id

    async def _get_binding(self, kwargs: dict) -> Optional[dict[str, Any]]:
        user_id = self._get_user_id(kwargs)
        if not user_id:
            return None
        return await self._bindings.get(user_id)

    async def _build_song_detail_text(self, music: dict) -> str:
        sid = str(music.get("id", "") or "?")
        title = str(music.get("title", "") or "?")
        tp = str(music.get("type", "") or "?")
        bi = music.get("basic_info", {})
        artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
        version = str(bi.get("from", "") or "?") if isinstance(bi, dict) else "?"
        genre = str(bi.get("genre", "") or "?") if isinstance(bi, dict) else "?"
        bpm = bi.get("bpm", "?") if isinstance(bi, dict) else "?"
        ds_list = music.get("ds", [])
        level_list = music.get("level", [])
        diffs_parts = [f"{lvl}({ds})" for lvl, ds in zip(level_list, ds_list)]
        lines = [
            "【曲目详情】",
            f"[{_html.escape(tp)}] {_html.escape(title)}  (ID: {_html.escape(sid)})",
            f"作者: {_html.escape(artist)}  |  BPM: {bpm}",
        ]
        extra = await self._music.enrich_with_lxns(music)
        if extra:
            genre_display = str(extra.get("genre_name", "") or genre)
            version_display = str(extra.get("version_name", "") or version)
            lines.append(
                f"分类: {_html.escape(genre_display)}  |  版本: {_html.escape(version_display)}"
            )
            map_name = extra.get("map_name", "")
            if map_name:
                lines.append(f"原曲出处: {_html.escape(str(map_name))}")
            diffs = extra.get("difficulties", {})
            if diffs:
                lines.append(build_difficulty_detail_text(diffs, level_list))
        else:
            lines.append(f"版本: {_html.escape(version)}  |  分类: {_html.escape(genre)}")
        lines.append(f"定数: {' / '.join(diffs_parts)}")
        aliases = await self._aliases.list_aliases(sid)
        if aliases:
            lines.append(f"别称: {', '.join(aliases)}")
        return "\n".join(lines)

    async def _render_and_send(
        self,
        stream_id: str,
        render_call: Callable[[], Coroutine[Any, Any, str]],
        fail_prefix: str = "图片生成失败",
    ) -> bool:
        """渲染图片并发送；失败时发送错误文本。"""
        try:
            img = await render_call()
        except RuntimeError as e:
            await self.ctx.send.text(str(e), stream_id)
            return False
        except Exception as e:
            logger.warning(f"{fail_prefix}: {e}", exc_info=True)
            await self.ctx.send.text(f"{fail_prefix}: {e}", stream_id)
            return False
        await self.ctx.send.image(img, stream_id)
        return True
