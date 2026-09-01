# -*- coding: utf-8 -*-
"""水鱼 OAuth 绑定命令（公开客户端设备码流程）。"""

from typing import Any

from maibot_sdk import Command

from .base import SharedHelpersMixin


def _masked_qq(user_id: str) -> str:
    value = str(user_id or "").strip()
    if len(value) <= 6:
        return value or "unknown"
    return f"{value[:3]}****{value[-4:]}"


class DivingFishCommandsMixin(SharedHelpersMixin):

    @Command(
        "mai_df_bind",
        description="绑定水鱼账号（OAuth 设备码）",
        pattern=r"^/mai df bind\s*$",
    )
    async def handle_df_bind(
        self, stream_id: str = "", **kwargs: Any
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok, data = await self._df_oauth.start_binding(
            user_id,
            binding_label=f"QQ {_masked_qq(user_id)}",
        )
        if not ok:
            await self.ctx.send.text(str(data.get("message", "绑定发起失败")), stream_id)
            return False, "绑定发起失败", True
        await self.ctx.send.text(
            "【水鱼账号绑定（OAuth）】\n\n"
            "1. 打开以下链接，登录你的水鱼账号并确认授权：\n"
            f"{data.get('verification_uri', '')}\n\n"
            f"2. 用户码：{data.get('user_code', '')}\n"
            "3. 授权完成后，发送：/mai df bind confirm\n\n"
            "⚠ 绑定链接 10 分钟内有效；请勿把链接转发给他人。",
            stream_id,
        )
        return True, "已发起水鱼 OAuth 绑定", True

    @Command(
        "mai_df_bind_confirm",
        description="确认水鱼设备码绑定",
        pattern=r"^/mai df bind confirm\s*$",
    )
    async def handle_df_bind_confirm(
        self, stream_id: str = "", **kwargs: Any
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok, info = await self._df_oauth.poll_binding(user_id)
        if not ok:
            if info == "pending":
                await self.ctx.send.text(
                    "尚未完成授权。请打开刚才的链接登录并确认，"
                    "完成后再次发送 /mai df bind confirm。",
                    stream_id,
                )
            elif info == "slow_down":
                await self.ctx.send.text(
                    "查询过于频繁，请稍等几秒后再发送 /mai df bind confirm。",
                    stream_id,
                )
            else:
                await self.ctx.send.text(f"绑定失败: {info}", stream_id)
            return False, "绑定尚未完成", True
        await self.ctx.send.text(
            f"【水鱼账号绑定】\n状态: 绑定成功\n水鱼账号: {info}\n\n"
            "绑定后查询完整成绩、按版本查询和双向上传将优先使用 OAuth。",
            stream_id,
        )
        return True, "水鱼绑定完成", True

    @Command(
        "mai_df_unbind",
        description="解除水鱼 OAuth 绑定",
        pattern=r"^/mai df unbind\s*$",
    )
    async def handle_df_unbind(
        self, stream_id: str = "", **kwargs: Any
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        deleted = await self._df_oauth.unbind(user_id)
        if deleted:
            await self.ctx.send.text("已解除水鱼 OAuth 绑定。", stream_id)
        else:
            await self.ctx.send.text("当前没有进行中的水鱼 OAuth 绑定。", stream_id)
        return True, "解绑完成", True

    @Command(
        "mai_df_status",
        description="查看水鱼 OAuth 绑定状态",
        pattern=r"^/mai df status\s*$",
    )
    async def handle_df_status(
        self, stream_id: str = "", **kwargs: Any
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        binding = await self._df_oauth.get_binding(user_id)
        if not binding:
            text = "未绑定水鱼 OAuth，请执行 /mai df bind"
        else:
            text = (
                "【水鱼 OAuth 绑定】\n"
                f"账号: {binding.get('username', '?')}\n"
                f"scope: {binding.get('scope', '?')}\n"
                f"绑定时间: {binding.get('bound_at', '?')}"
            )
        await self.ctx.send.text(text, stream_id)
        return True, "显示水鱼绑定状态", True
