# -*- coding: utf-8 -*-
"""落雪（lxns）命令：绑定管理与落雪独有能力。

两源共有的 b50 / my / player 在 ``score.py`` / 统一数据服务层实现；
本文件只包含落雪独有命令（heatmap / trend / history / rank / year /
collections / comment）以及绑定管理（bind / unbind / status）。
"""

import asyncio
import html as _html
import logging
import random
from datetime import datetime, timezone
from typing import Any

from maibot_sdk import Command

from ..clients.lxns import LxnsApiClient
from ..constants import BLESSINGS
from ..renderers import (
    render_b50,
    render_best,
    render_collections,
    render_heatmap,
    render_history,
    render_lxns_status,
    render_player,
    render_rank,
    render_trend,
    render_year,
)
from ..util import error_msg, is_error
from .base import SharedHelpersMixin

logger = logging.getLogger(__name__)


class LxnsCommandsMixin(SharedHelpersMixin):

    # ---- 绑定管理 ----

    @Command(
        "mai_lxns_bind",
        description="绑定落雪账号（OAuth 授权）",
        pattern=r"^/mai lxns bind\s*$",
    )
    async def handle_lxns_bind(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok, url = await self._lxns_auth.create_authorize_url(user_id)
        if not ok:
            await self.ctx.send.text(url, stream_id)
            return False, "OAuth 未启用", True
        await self.ctx.send.text(
            "【落雪账号绑定（OAuth）】\n\n"
            "1. 点击下方链接，登录落雪查分器并授权：\n"
            f"{url}\n\n"
            "2. 授权成功后页面会显示一个授权码（形如 JVJ6-VPTM-MGHZ）\n"
            "3. 把授权码发给我：/mai lxns bind code <授权码>\n\n"
            "⚠ 授权链接 10 分钟内有效，请尽快完成。",
            stream_id,
        )
        return True, "已发送授权链接", True

    @Command(
        "mai_lxns_bind_token",
        description="绑定落雪账号（个人 API 密钥）",
        pattern=r"^/mai lxns bind token\s+(?P<token>\S+)\s*$",
    )
    async def handle_lxns_bind_token(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        token = (matched_groups or {}).get("token", "").strip()
        if not token:
            await self.ctx.send.text(
                "用法: /mai lxns bind token <个人API密钥>\n"
                "密钥在落雪查分器「账号详情页」生成",
                stream_id,
            )
            return False, "参数错误", True
        ok, info = await self._lxns_auth.bind_personal_token(user_id, token)
        if not ok:
            await self.ctx.send.text(f"绑定失败: {info}", stream_id)
            return False, "绑定失败", True
        await self.ctx.send.text(
            f"【落雪账号绑定】\n状态: 绑定成功\n玩家: {_html.escape(info)}\n\n"
            "绑定后 /mai b50、/mai my 会自动使用落雪数据源。\n"
            "⚠ 建议撤回刚才的消息，避免密钥泄露。",
            stream_id,
        )
        return True, "绑定完成", True

    @Command(
        "mai_lxns_bind_code",
        description="用授权码完成落雪 OAuth 绑定",
        pattern=r"^/mai lxns bind code\s+(?P<code>\S+)(\s+(?P<state>\S+))?\s*$",
    )
    async def handle_lxns_bind_code(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        code = (matched_groups or {}).get("code", "").strip()
        state = (matched_groups or {}).get("state", "") or ""
        if not code:
            await self.ctx.send.text("请提供授权码: /mai lxns bind code <授权码>", stream_id)
            return False, "参数错误", True
        ok, info = await self._lxns_auth.complete_oauth_bind(user_id, code, state)
        if not ok:
            await self.ctx.send.text(f"绑定失败: {info}", stream_id)
            return False, "绑定失败", True
        await self.ctx.send.text(
            f"【落雪账号绑定】\n状态: 绑定成功\n玩家: {_html.escape(info)}\n\n"
            "绑定后 /mai b50、/mai my 会自动使用落雪数据源，"
            "并解锁 /mai lxns heatmap / trend / history / rank / year / collections 等命令。",
            stream_id,
        )
        return True, "绑定完成", True

    @Command(
        "mai_lxns_unbind",
        description="解除落雪账号绑定",
        pattern=r"^/mai lxns unbind\s*$",
    )
    async def handle_lxns_unbind(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        deleted = await self._lxns_auth.unbind(user_id)
        if deleted:
            await self.ctx.send.text("已解除落雪账号绑定", stream_id)
        else:
            await self.ctx.send.text("当前未绑定落雪账号", stream_id)
        return True, "解绑完成", True

    @Command(
        "mai_lxns_status",
        description="查看落雪绑定状态",
        pattern=r"^/mai lxns status\s*$",
    )
    async def handle_lxns_status(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        binding = await self._lxns_bindings.get(user_id)
        ok = await self._render_and_send(
            stream_id,
            lambda: render_lxns_status(
                self._renderer,
                binding,
                self._lxns_auth.oauth_enabled,
                self._lxns_auth.developer_enabled,
                developer_qq_count=len(self.config.plugin.developer_qq),
            ),
            "状态图片生成失败",
        )
        return ok, "显示状态", True

    # ---- 玩家资料卡 ----

    @Command(
        "mai_lxns_player",
        description="查看落雪玩家资料卡",
        pattern=r"^/mai lxns player(\s+(?P<target>\S+))?\s*$",
    )
    async def handle_lxns_player(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        target = (matched_groups or {}).get("target", "").strip()
        ok, data, err = await self._players.get_player(user_id, target)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "获取失败", True
        player = data.get("player") or {}
        source = data.get("source", "")
        assets: dict[str, str] = {}
        if source == "lxns" and isinstance(player, dict):
            icon = player.get("icon")
            if isinstance(icon, dict) and icon.get("id"):
                url = LxnsApiClient.get_icon_url(
                    self._lxns.asset_url, int(icon["id"]),
                )
                avatar = await self._covers.get_image_data_url(url)
                if avatar:
                    assets["avatar"] = avatar
        ok = await self._render_and_send(
            stream_id,
            lambda: render_player(
                self._renderer,
                player,
                data.get("username", ""),
                source,
                assets,
            ),
            "玩家资料图片生成失败",
        )
        return ok, "显示玩家资料", True

    # ---- All Perfect 50（开发者模式）----

    @Command(
        "mai_lxns_ap50",
        description="查询落雪 All Perfect 50（好友码，开发者模式）",
        pattern=r"^/mai lxns ap50\s+(?P<target>\d+)\s*$",
    )
    async def handle_lxns_ap50(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        target = (matched_groups or {}).get("target", "").strip()
        ok, data, err = await self._players.get_ap50(user_id, target)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "查询失败", True
        await self.ctx.send.text("正在生成 AP50 图片，请稍候...", stream_id)
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
            "AP50 图片生成失败",
        )
        return ok, "发送AP50图片", True

    # ---- 落雪独有能力 ----

    @Command(
        "mai_lxns_heatmap",
        description="查看落雪成绩上传热力图",
        pattern=r"^/mai lxns heatmap\s*$",
    )
    async def handle_lxns_heatmap(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok, data, err = await self._players.get_heatmap(user_id)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "获取失败", True
        binding = await self._lxns_bindings.get(user_id)
        username = str((binding or {}).get("username", "玩家"))
        query_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        await self.ctx.send.text("正在生成热力图...", stream_id)
        ok = await self._render_and_send(
            stream_id,
            lambda: render_heatmap(
                self._renderer, data["heatmap"], username,
                query_time=query_time,
            ),
            "热力图生成失败",
        )
        return ok, "显示热力图", True

    @Command(
        "mai_lxns_trend",
        description="查看落雪 DX Rating 趋势",
        pattern=r"^/mai lxns trend(\s+(?P<version>\d+))?\s*$",
    )
    async def handle_lxns_trend(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        version = getattr(self.config.plugin, "game_version", 25500)
        if matched_groups and matched_groups.get("version"):
            try:
                version = int(matched_groups["version"])
            except (TypeError, ValueError):
                pass
        ok, data, err = await self._players.get_trend(user_id, version=version)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "获取失败", True
        binding = await self._lxns_bindings.get(user_id)
        username = str((binding or {}).get("username", "玩家"))
        query_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        await self.ctx.send.text("正在生成趋势图...", stream_id)
        ok = await self._render_and_send(
            stream_id,
            lambda: render_trend(
                self._renderer, data["trend"], username,
                query_time=query_time,
            ),
            "趋势图生成失败",
        )
        return ok, "显示趋势", True

    @Command(
        "mai_lxns_history",
        description="查看单曲游玩历史（落雪）",
        pattern=r"^/mai lxns history\s+(?P<keyword>.+)\s*$",
    )
    async def handle_lxns_history(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        keyword = (matched_groups or {}).get("keyword", "").strip()
        if not keyword:
            await self.ctx.send.text("用法: /mai lxns history <曲名或ID>", stream_id)
            return False, "参数错误", True
        ok, data, err = await self._players.get_history(user_id, keyword)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "获取失败", True
        history = data["history"]
        if not history:
            await self.ctx.send.text(
                f"「{data['title']}」暂无游玩历史记录", stream_id
            )
            return False, "无记录", True
        await self.ctx.send.text("正在生成历史图片，请稍候...", stream_id)
        ok = await self._render_and_send(
            stream_id,
            lambda: render_history(self._renderer, data["title"], history),
            "历史图片生成失败",
        )
        return ok, "显示历史", True

    @Command(
        "mai_lxns_rank",
        description="查看单曲分数排行（落雪）",
        pattern=r"^/mai lxns rank\s+(?P<keyword>.+)\s*$",
    )
    async def handle_lxns_rank(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        keyword = (matched_groups or {}).get("keyword", "").strip()
        if not keyword:
            await self.ctx.send.text("用法: /mai lxns rank <曲名或ID>", stream_id)
            return False, "参数错误", True
        ok, data, err = await self._players.get_ranking(user_id, keyword)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "获取失败", True
        ranking = data["ranking"]
        if not ranking:
            await self.ctx.send.text(
                f"「{data['title']}」暂无排行数据", stream_id
            )
            return False, "无记录", True
        await self.ctx.send.text("正在生成排行图片，请稍候...", stream_id)
        ok = await self._render_and_send(
            stream_id,
            lambda: render_rank(self._renderer, data["title"], ranking),
            "排行图片生成失败",
        )
        return ok, "显示排行", True

    @Command(
        "mai_lxns_year",
        description="查看年度回顾（落雪）",
        pattern=r"^/mai lxns year(\s+(?P<year>\d{4}))?\s*$",
    )
    async def handle_lxns_year(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        year = datetime.now().year
        if matched_groups and matched_groups.get("year"):
            year = int(matched_groups["year"])
        ok, data, err = await self._players.get_year_review(user_id, year)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "获取失败", True
        review = data["year"]
        song_counts = review.get("player_most_uploaded_songs") or {}
        top_songs = sorted(
            ((str(k), int(v)) for k, v in song_counts.items() if isinstance(v, (int, float))),
            key=lambda x: x[1], reverse=True,
        )[:5]
        songs: list[tuple[str, int]] = []
        for sid, count in top_songs:
            lxns_song, _ = await self._music.find_lxns_song(sid)
            title = str((lxns_song or {}).get("title", sid))
            songs.append((title, count))
        await self.ctx.send.text("正在生成年度回顾图片，请稍候...", stream_id)
        ok = await self._render_and_send(
            stream_id,
            lambda: render_year(self._renderer, review, songs),
            "年度回顾图片生成失败",
        )
        return ok, "显示年度回顾", True

    @Command(
        "mai_lxns_collections",
        description="查看落雪收藏品（称号/头像等）",
        pattern=r"^/mai lxns collections\s*$",
    )
    async def handle_lxns_collections(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok, data, err = await self._players.get_collections(user_id)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "获取失败", True
        player = data.get("player") or {}
        collections = data.get("collections") or {}

        # 预取实物图：当前装备 4 件 + 每类拥有列表前 6 个
        asset_urls: list[tuple[str, str]] = []
        for key, ctype in (
            ("icon", "icon"), ("name_plate", "plate"),
            ("frame", "frame"), ("trophy", "trophy"),
        ):
            equip = player.get(key)
            if isinstance(equip, dict) and equip.get("id") is not None:
                asset_urls.append((
                    key,
                    LxnsApiClient.get_collection_url(
                        self._lxns.asset_url, ctype, int(equip["id"]),
                    ),
                ))
        for ctype in ("trophies", "icons", "plates", "frames"):
            for c in (collections.get(ctype) or [])[:6]:
                if isinstance(c, dict) and c.get("id") is not None:
                    asset_urls.append((
                        f"{ctype}_{c['id']}",
                        LxnsApiClient.get_collection_url(
                            self._lxns.asset_url,
                            ctype.rstrip("s"),
                            int(c["id"]),
                        ),
                    ))
        results = await asyncio.gather(
            *(self._covers.get_image_data_url(url) for _, url in asset_urls),
            return_exceptions=True,
        )
        asset_map: dict[str, str] = {}
        for (key, _), res in zip(asset_urls, results):
            if isinstance(res, str) and res:
                asset_map[key] = res

        await self.ctx.send.text("正在生成收藏品图片，请稍候...", stream_id)
        ok = await self._render_and_send(
            stream_id,
            lambda: render_collections(
                self._renderer,
                player,
                collections,
                asset_map,
            ),
            "收藏品图片生成失败",
        )
        return ok, "显示收藏品", True

    @Command(
        "mai_lxns_upload",
        description="把水鱼成绩同步上传到落雪账号",
        pattern=r"^/mai lxns upload\s*$",
    )
    async def handle_lxns_upload(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok, data, err = await self._players.upload_df_to_lxns(user_id)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "上传失败", True
        lines = [
            "【水鱼 → 落雪 成绩同步】",
            f"水鱼成绩: {data['total']} 条",
            f"成功映射: {data['mapped']} 条",
            f"新增: {data['new']} 条",
            f"更高成绩覆盖: {data['upgraded']} 条（保留原游玩时间）",
            f"相同/更低跳过: {data['unchanged']} 条",
            f"已上传: {data['uploaded']} 条",
            f"跳过（无法映射）: {data['skipped']} 条",
        ]
        if data.get("errors"):
            lines.append("")
            lines.append("⚠ 部分批次失败:")
            lines.extend(data["errors"][:5])
        lines.append("")
        lines.append("策略：成绩只升不降——缺失补齐、更高覆盖、相同或更低不动。")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "同步完成", True

    @Command(
        "mai_df_upload",
        description="把落雪成绩同步上传到水鱼（反向同步，只升不降）",
        pattern=r"^/mai df upload\s*$",
    )
    async def handle_df_upload(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok, data, err = await self._players.upload_lxns_to_df(user_id)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "上传失败", True
        lines = [
            "【落雪 → 水鱼 成绩同步】",
            f"落雪成绩: {data['total']} 条",
            f"成功映射: {data['mapped']} 条",
            f"新增: {data['new']} 条",
            f"更高成绩覆盖: {data['upgraded']} 条",
            f"相同/更低跳过: {data['unchanged']} 条",
            f"已上传: {data['uploaded']} 条",
            f"跳过（无法映射）: {data['skipped']} 条",
        ]
        if data.get("errors"):
            lines.append("")
            lines.append("⚠ 部分批次失败:")
            lines.extend(data["errors"][:5])
        lines.append("")
        lines.append("策略：成绩只升不降——缺失补齐、更高覆盖、相同或更低不动。")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "同步完成", True

    # ---- 单曲最佳（好友码走开发者 API，否则用绑定账号）----

    @Command(
        "mai_lxns_best",
        description="查看单曲所有谱面最佳成绩（落雪）",
        pattern=r"^/mai lxns best(?:\s+(?P<fc>\d{12,}))?\s+(?P<keyword>.+)\s*$",
    )
    async def handle_lxns_best(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        groups = matched_groups or {}
        keyword = groups.get("keyword", "").strip()
        fc = groups.get("fc", "").strip()
        if not keyword:
            await self.ctx.send.text(
                "用法: /mai lxns best <曲名/ID> 或 /mai lxns best <好友码> <曲名/ID>",
                stream_id,
            )
            return False, "参数错误", True
        ok, data, err = await self._players.get_lxns_best(user_id, keyword, fc)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "获取失败", True
        rows = data.get("rows") or []
        if not rows:
            await self.ctx.send.text(f"「{data['title']}」暂无最佳成绩", stream_id)
            return False, "无记录", True
        ok = await self._render_and_send(
            stream_id,
            lambda: render_best(self._renderer, data["title"], rows),
            "最佳成绩图片生成失败",
        )
        return ok, "显示最佳成绩", True

    # ---- 按 QQ 查玩家（开发者模式）----

    @Command(
        "mai_lxns_qq",
        description="按 QQ 号查询落雪玩家资料（开发者模式）",
        pattern=r"^/mai lxns qq\s+(?P<qq>\d+)\s*$",
    )
    async def handle_lxns_qq(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        qq = (matched_groups or {}).get("qq", "").strip()
        ok, data, err = await self._players.get_lxns_player_by_qq(user_id, qq)
        if not ok:
            await self.ctx.send.text(err, stream_id)
            return False, "查询失败", True
        player = data.get("player") or {}
        assets: dict[str, str] = {}
        icon = player.get("icon")
        if isinstance(icon, dict) and icon.get("id"):
            url = LxnsApiClient.get_icon_url(
                self._lxns.asset_url, int(icon["id"]),
            )
            avatar = await self._covers.get_image_data_url(url)
            if avatar:
                assets["avatar"] = avatar
        ok = await self._render_and_send(
            stream_id,
            lambda: render_player(
                self._renderer,
                player,
                data.get("username", ""),
                "lxns",
                assets,
            ),
            "玩家资料图片生成失败",
        )
        return ok, "显示玩家资料", True

    # ---- 评论（OAuth 专属）----

    async def _require_oauth(self, user_id: str) -> tuple[bool, str]:
        binding = await self._lxns_bindings.get(user_id)
        if not binding:
            return False, "未绑定落雪账号，请先 /mai lxns bind"
        if binding.get("mode") != "oauth":
            return False, "评论功能仅支持 OAuth 绑定（个人 API 密钥无法访问评论接口），请用 /mai lxns bind 重新绑定"
        auth, err = await self._lxns_auth.get_auth(user_id)
        if not auth:
            return False, err
        return True, auth

    @staticmethod
    def _comment_error(resp: dict) -> str:
        """评论接口错误转友好文案（实测落雪服务端全部路径 404，接口未开放）。"""

        if resp.get("_status") == 404:
            return "评论功能暂不可用：落雪服务端未开放该接口（实测 404），等待官方上线后可用"
        return f"{error_msg(resp)}"

    @Command(
        "mai_lxns_comment_list",
        description="查看曲目评论（落雪）",
        pattern=r"^/mai lxns comment list\s+(?P<keyword>.+)\s*$",
    )
    async def handle_lxns_comment_list(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok_auth, auth = await self._require_oauth(user_id)
        if not ok_auth:
            await self.ctx.send.text(auth, stream_id)
            return False, "权限不足", True
        keyword = (matched_groups or {}).get("keyword", "").strip()
        lxns_song, err = await self._music.find_lxns_song(keyword)
        if not lxns_song:
            await self.ctx.send.text(err, stream_id)
            return False, "无匹配", True
        resp = await self._lxns.get_user_comment_list(
            auth, int(lxns_song["id"]),
            song_type=self._players._song_type_for(lxns_song, 0),
            level_index=0,
        )
        if is_error(resp):
            await self.ctx.send.text(f"获取评论失败: {self._comment_error(resp)}", stream_id)
            return False, "获取失败", True
        data = resp.get("data") or []
        title = str(lxns_song.get("title", ""))
        if not isinstance(data, list) or not data:
            await self.ctx.send.text(f"「{title}」暂无评论", stream_id)
            return False, "无评论", True
        lines = [f"【评论】{title}"]
        for c in data[:10]:
            if not isinstance(c, dict):
                continue
            cid = c.get("comment_id", "?")
            user = c.get("uploader", {})
            name = user.get("name", "?") if isinstance(user, dict) else "?"
            content = str(c.get("comment", ""))
            created = str(c.get("upload_time", ""))[:16].replace("T", " ")
            lines.append(f"  [{cid}] {_html.escape(name)}: {_html.escape(content)} ({created})")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "显示评论", True

    @Command(
        "mai_lxns_comment_post",
        description="发表曲目评论（落雪）",
        pattern=r"^/mai lxns comment\s+(?P<keyword>.+?)\s+(?P<content>.+)\s*$",
    )
    async def handle_lxns_comment_post(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok_auth, auth = await self._require_oauth(user_id)
        if not ok_auth:
            await self.ctx.send.text(auth, stream_id)
            return False, "权限不足", True
        keyword = (matched_groups or {}).get("keyword", "").strip()
        content = (matched_groups or {}).get("content", "").strip()
        if not keyword or not content:
            await self.ctx.send.text("用法: /mai lxns comment <曲名> <评论内容>", stream_id)
            return False, "参数错误", True
        lxns_song, err = await self._music.find_lxns_song(keyword)
        if not lxns_song:
            await self.ctx.send.text(err, stream_id)
            return False, "无匹配", True
        resp = await self._lxns.post_user_comment(
            auth, int(lxns_song["id"]), content,
            song_type=self._players._song_type_for(lxns_song, 0),
            level_index=0,
        )
        if is_error(resp):
            await self.ctx.send.text(f"发表失败: {self._comment_error(resp)}", stream_id)
            return False, "发表失败", True
        await self.ctx.send.text(
            f"评论已发表: 「{lxns_song.get('title', '')}」\n{_html.escape(content)}",
            stream_id,
        )
        return True, "评论已发表", True

    @Command(
        "mai_lxns_comment_like",
        description="点赞曲目评论（落雪）",
        pattern=r"^/mai lxns comment like\s+(?P<cid>\d+)\s*$",
    )
    async def handle_lxns_comment_like(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)
        ok_auth, auth = await self._require_oauth(user_id)
        if not ok_auth:
            await self.ctx.send.text(auth, stream_id)
            return False, "权限不足", True
        cid = int((matched_groups or {}).get("cid", "0"))
        resp = await self._lxns.like_user_comment(auth, cid)
        if is_error(resp):
            await self.ctx.send.text(f"点赞失败: {self._comment_error(resp)}", stream_id)
            return False, "点赞失败", True
        await self.ctx.send.text(f"已点赞评论 #{cid}", stream_id)
        return True, "点赞完成", True
