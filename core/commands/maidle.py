# -*- coding: utf-8 -*-
"""Maidle 猜歌命令。"""

import html as _html
import random
from typing import Any

from maibot_sdk import Command

from ..renderers import render_maidle_answer, render_maidle_guess, render_maidle_help
from ..util import error_msg, is_error
from .base import SharedHelpersMixin


class MaidleCommandsMixin(SharedHelpersMixin):

    @Command(
        "mai_maidle_start",
        description="开始 Maidle 猜歌游戏",
        pattern=r"^/mai maidle$",
    )
    async def handle_maidle_start(
        self, stream_id: str = "", **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        existing = await self._maidle.get_or_create(user_id)
        if existing:
            await self.ctx.send.text(
                "当前已有进行中的猜歌游戏\n"
                "继续猜测: /mai maidle guess <ID/名称>\n"
                "放弃答案: /mai maidle answer",
                stream_id,
            )
            return True, "已有会话", True

        maidle_data_resp = await self._df.get_maidle_data()
        song_ids = await self._music.get_maidle_song_ids(maidle_data_resp)
        if not song_ids:
            await self.ctx.send.text("无法获取歌曲列表，请稍后重试", stream_id)
            return False, "无数据", True

        first_guess = random.choice(song_ids)
        resp = await self._df.maidle_single(first_guess, lists=song_ids)
        if is_error(resp):
            await self.ctx.send.text(
                f"开始游戏失败: {error_msg(resp)}", stream_id
            )
            return False, "失败", True

        uuid_val = resp.get("uuid", "")
        if not uuid_val:
            await self.ctx.send.text("开始游戏失败: 未获取到会话 ID", stream_id)
            return False, "失败", True
        await self._maidle.create(user_id, uuid_val)

        test = resp.get("test", {})
        ok = await self._render_and_send(
            stream_id,
            lambda: render_maidle_guess(
                self._renderer, first_guess, test, header="开局线索（系统代猜）"
            ),
            "Maidle 图片生成失败",
        )
        return ok, "游戏开始", True

    @Command(
        "mai_maidle_guess",
        description="Maidle 猜歌 — 提交猜测",
        pattern=r"^/mai maidle guess\s+(?P<guess>.+)$",
    )
    async def handle_maidle_guess(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        session = await self._maidle.get(user_id)
        if not session:
            await self.ctx.send.text(
                "请先使用 /mai maidle 开始游戏", stream_id
            )
            return False, "无会话", True

        if not matched_groups or not matched_groups.get("guess"):
            await self.ctx.send.text("用法: /mai maidle guess <歌曲ID/名称/别称>", stream_id)
            return False, "参数错误", True

        raw = matched_groups["guess"].strip()
        if raw.isdigit():
            guess_id = int(raw)
        else:
            matches = await self._music.match_songs(raw)
            if not matches:
                await self.ctx.send.text(
                    f"未找到匹配的曲目: \"{raw}\"\n可使用 /mai song 先行查询", stream_id
                )
                return False, "无匹配", True
            if len(matches) > 1:
                names = " | ".join(
                    f"ID.{str(m.get('id', '') or '?')} {str(m.get('title', '') or '?')[:12]}"
                    for m in matches[:5]
                )
                await self.ctx.send.text(
                    f"找到多个匹配: {names}\n请使用 ID 重新猜测", stream_id
                )
                return False, "多匹配", True
            guess_id = int(str(matches[0].get("id", "0") or "0"))

        session = await self._maidle.get(user_id)
        if not session:
            await self.ctx.send.text("游戏会话已不存在，请重新开始", stream_id)
            return False, "无会话", True

        resp = await self._df.maidle_single(guess_id, uuid=session["uuid"])
        if is_error(resp):
            await self.ctx.send.text(f"猜测失败: {error_msg(resp)}", stream_id)
            return False, "失败", True

        test = resp.get("test", {})
        ok = await self._render_and_send(
            stream_id,
            lambda: render_maidle_guess(self._renderer, guess_id, test),
            "Maidle 图片生成失败",
        )
        return ok, "猜测提交", True

    @Command(
        "mai_maidle_help",
        description="Maidle 猜歌游戏说明",
        pattern=r"^/mai maidle help$",
    )
    async def handle_maidle_help(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        ok = await self._render_and_send(
            stream_id,
            lambda: render_maidle_help(self._renderer),
            "Maidle 帮助图片生成失败",
        )
        return ok, "显示说明", True

    @Command(
        "mai_maidle_answer",
        description="Maidle 猜歌 — 查看答案",
        pattern=r"^/mai maidle answer$",
    )
    async def handle_maidle_answer(
        self, stream_id: str = "", **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        session = await self._maidle.pop(user_id)
        if not session:
            await self.ctx.send.text("请先使用 /mai maidle 开始游戏", stream_id)
            return False, "无会话", True

        resp = await self._df.maidle_answer(session["uuid"])
        if is_error(resp):
            await self.ctx.send.text(f"获取答案失败: {error_msg(resp)}", stream_id)
            return False, "获取失败", True

        title = str(resp.get("title", "") or "?")
        artist = str(resp.get("artist", "") or "?")
        sid = str(resp.get("id", "") or "?")
        cover = await self._covers.get_cover_data_url(sid)

        ok = await self._render_and_send(
            stream_id,
            lambda: render_maidle_answer(
                self._renderer, title, artist, sid, cover,
            ),
            "Maidle 答案图片生成失败",
        )
        if not ok:
            await self.ctx.send.text(
                f"【Maidle 答案】\n歌曲: {_html.escape(title)} — {_html.escape(artist)}  (ID: {_html.escape(sid)})",
                stream_id,
            )
        return True, "显示答案", True
