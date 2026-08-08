# -*- coding: utf-8 -*-
"""成绩查询命令（v2.0 起统一为 /mai 前缀）。"""

import html as _html
import logging
import random
from datetime import datetime, timezone
from typing import Any

from maibot_sdk import Command

from ..constants import BLESSINGS
from ..renderers import render_b50, render_my
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
        await self._track_user(stream_id, self._get_user_id(kwargs))

        target = ""
        if matched_groups and matched_groups.get("target"):
            target = matched_groups["target"].strip()

        if not target:
            binding = await self._get_binding(kwargs)
            if not binding:
                await self.ctx.send.text(
                    "未提供查询目标，且未绑定账号。\n"
                    "用法: /mai b50 <用户名或QQ>\n"
                    "或先绑定: /mai bind <Token>",
                    stream_id,
                )
                return False, "无目标", True
            target = binding["username"]

        resp = await self._df.query_player(target)
        if is_error(resp):
            status = resp.get("_status", 0)
            msg = error_msg(resp)
            if status == 403:
                await self.ctx.send.text(
                    f"查询被拒绝: {target} 已设置隐私或未同意用户协议", stream_id
                )
            elif status == 400 and "not exists" in msg.lower():
                await self.ctx.send.text(f"用户不存在: {target}", stream_id)
            else:
                await self.ctx.send.text(f"查询失败: {msg}", stream_id)
            return False, "查询失败", True

        charts = resp.get("charts", {})
        if not charts or (not charts.get("sd") and not charts.get("dx")):
            await self.ctx.send.text(f"{target} 暂无成绩记录", stream_id)
            return False, "无记录", True

        nickname = resp.get("nickname", target)
        rating = resp.get("rating", 0)
        username = resp.get("username", target)

        await self.ctx.send.text("正在生成 B50 图片，请稍候...", stream_id)
        query_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        blessing = random.choice(BLESSINGS)

        ok = await self._render_and_send(
            stream_id,
            lambda: render_b50(
                self._renderer, charts, username, nickname, rating,
                query_time=query_time_str, blessing=blessing,
            ),
            "B50 图片生成失败",
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
        pattern=r"^/mai my$",
    )
    async def handle_my(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        binding = await self._get_binding(kwargs)
        if not binding:
            await self.ctx.send.text(
                "请先绑定 Token: /mai bind <Token>\n"
                "Token 为水鱼查分器 personal page 中的「成绩导入Token」",
                stream_id,
            )
            return False, "未绑定", True

        resp = await self._df.get_player_records(binding["import_token"])
        if is_error(resp):
            msg = error_msg(resp)
            if resp.get("_status") == 400 and "token" in msg.lower():
                await self.ctx.send.text(
                    f"Token 已失效: {msg}\n请重新绑定: /mai bind <Token>",
                    stream_id,
                )
            else:
                await self.ctx.send.text(f"获取数据失败: {msg}", stream_id)
            return False, "获取失败", True

        username = str(resp.get("username", "") or binding["username"])
        nickname = str(resp.get("nickname", "") or "未设置")
        rating = resp.get("rating", 0)
        additional = resp.get("additional_rating", 0)
        plate = resp.get("plate", "无")
        records = resp.get("records", [])
        if not isinstance(records, list):
            records = []

        ok = await self._render_and_send(
            stream_id,
            lambda: render_my(
                self._renderer, username, nickname, rating, additional, plate, records,
            ),
            "个人成绩图片生成失败",
        )
        return ok, "显示摘要", True
