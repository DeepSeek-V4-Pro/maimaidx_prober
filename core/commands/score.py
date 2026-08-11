# -*- coding: utf-8 -*-
"""成绩查询命令（v2.0 起统一为 /mai 前缀）。"""

import html as _html
import logging
import random
from typing import Any

from maibot_sdk import Command

from ..constants import BLESSINGS
from ..renderers import render_b50, render_my, render_plate
from ..util import error_msg, is_error
from .base import SharedHelpersMixin

logger = logging.getLogger(__name__)


class ScoreCommandsMixin(SharedHelpersMixin):

    @Command(
        "mai_b50",
        description="查询舞萌 DX Best 50 成绩，生成图片",
        pattern=r"^/mai b50(\s+(?P<target>.+))?$",
    )
    async def handle_b50(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        target = ""
        force = ""
        if matched_groups and matched_groups.get("target"):
            raw = matched_groups["target"].strip()
            tokens = raw.split(None, 1)
            flag = tokens[0].lower() if tokens else ""
            if flag in ("--lxns", "--df", "--落雪", "--水鱼"):
                force = "lxns" if flag in ("--lxns", "--落雪") else "water_fish"
                target = tokens[1].strip() if len(tokens) > 1 else ""
            else:
                target = raw

        ok, data, err = await self._players.get_b50(user_id, target, force)
        if not ok:
            await self.ctx.send.text(err or "查询失败", stream_id)
            return False, "查询失败", True

        await self.ctx.send.text("正在生成 B50 图片，请稍候...", stream_id)
        blessing = random.choice(BLESSINGS)

        ok = await self._render_and_send(
            stream_id,
            lambda: render_b50(
                self._renderer,
                data["charts"],
                data["username"],
                data["nickname"],
                data["rating"],
                query_time=data["query_time"],
                blessing=blessing,
                avatar_url=data.get("avatar_url", ""),
                version=data.get("version", 25500),
                course_rank=data.get("course_rank"),
                class_rank=data.get("class_rank"),
            ),
            "B50 图片生成失败",
        )
        if ok and data.get("masked"):
            await self.ctx.send.text(
                "⚠ 该账号可能开启了查询掩码，成绩为掩码后的近似值"
                "（dxScore 显示为 0），仅供粗略参考。",
                stream_id,
            )
        return ok, "发送B50图片", True

    @Command(
        "mai_bind",
        description="绑定水鱼查分器的成绩导入Token",
        pattern=r"^/mai bind\s+(?P<token>\S+)$",
    )
    async def handle_bind(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        if not matched_groups or not matched_groups.get("token"):
            await self.ctx.send.text(
                "用法: /mai bind <Token>\n"
                "Token 为水鱼查分器 personal page 中的「成绩导入Token」",
                stream_id,
            )
            return False, "参数错误", True

        token = matched_groups["token"].strip()
        check = await self._df.token_available(token)
        if is_error(check):
            status = check.get("_status", 0)
            if status == 404 or "non-exist" in str(check.get("message", "")).lower():
                await self.ctx.send.text("Token 无效，请检查后重试", stream_id)
            else:
                await self.ctx.send.text(f"验证 Token 失败: {error_msg(check)}", stream_id)
            return False, "Token无效", True

        try:
            recs = await self._df.get_player_records(token)
        except Exception:
            await self.ctx.send.text("Token 验证失败，无法获取账号信息", stream_id)
            return False, "获取失败", True

        username = "unknown"
        if isinstance(recs, dict) and not recs.get("_error"):
            username = str(recs.get("username", "") or "unknown")

        await self._bindings.set(user_id, username, token)
        logger.warning(
            f"用户 {user_id} 绑定了 Import-Token (用户名: {username})，"
            "Token 将以明文存储在 bindings.json 中，请确保插件目录权限合理"
        )
        await self.ctx.send.text(
            f"【账号绑定】\n"
            f"状态: 绑定成功\n"
            f"用户名: {_html.escape(username)}\n"
            f"可使用 /mai my 查看个人成绩\n\n"
            f"⚠ 建议撤回刚才的消息，避免 Token 泄露",
            stream_id,
        )
        return True, "绑定完成", True

    @Command(
        "mai_unbind",
        description="解除水鱼查分器账号绑定",
        pattern=r"^/mai unbind$",
    )
    async def handle_unbind(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        deleted = await self._bindings.delete(user_id)
        if deleted:
            await self.ctx.send.text("已解除账号绑定", stream_id)
        else:
            await self.ctx.send.text("当前未绑定账号", stream_id)
        return True, "解绑完成", True

    @Command(
        "mai_my",
        description="查看个人成绩摘要",
        pattern=r"^/mai my(\s+(?P<source>--\w+))?$",
    )
    async def handle_my(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        force = ""
        if kwargs.get("matched_groups") and kwargs["matched_groups"].get("source"):
            flag = kwargs["matched_groups"]["source"].lower()
            force = "lxns" if flag in ("--lxns", "--落雪") else "water_fish"

        ok, data, err = await self._players.get_my(user_id, force)
        if not ok:
            await self.ctx.send.text(err or "获取数据失败", stream_id)
            return False, "获取失败", True

        ok = await self._render_and_send(
            stream_id,
            lambda: render_my(
                self._renderer,
                data["username"],
                data["nickname"],
                data["rating"],
                data["additional_rating"],
                data["plate"],
                data["records"],
                class_rank=data.get("class_rank"),
                star=data.get("star"),
            ),
            "个人成绩图片生成失败",
        )
        if ok and data.get("masked"):
            await self.ctx.send.text(
                "⚠ 该账号可能开启了查询掩码，成绩为掩码后的近似值。",
                stream_id,
            )
        return ok, "显示摘要", True

    @Command(
        "mai_plate",
        description="按版本查询水鱼成绩（需配置水鱼 Developer-Token）",
        pattern=r"^/mai plate\s+(?P<versions>.+)$",
    )
    async def handle_plate(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        raw = (matched_groups or {}).get("versions", "").strip()
        versions = [v for v in raw.split() if v.strip()]
        if not versions:
            await self.ctx.send.text("用法: /mai plate <版本代号>", stream_id)
            return False, "参数错误", True
        ok, data, err = await self._players.get_plate(user_id, "", versions)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "查询失败", True
        verlist = data.get("verlist") or []
        if not verlist:
            await self.ctx.send.text(
                f"「{'、'.join(versions)}」暂无已游玩谱面记录", stream_id
            )
            return False, "无记录", True
        ok = await self._render_and_send(
            stream_id,
            lambda: render_plate(
                self._renderer,
                data["username"],
                data["versions"],
                verlist,
            ),
            "版本成绩图片生成失败",
        )
        return ok, "显示版本成绩", True
