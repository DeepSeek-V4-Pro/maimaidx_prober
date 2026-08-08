# -*- coding: utf-8 -*-
"""基础命令：帮助、选歌、运势、统计、状态、别称、AI 工具。"""

import html as _html
import json
import logging
import random
import time
from typing import Any

from maibot_sdk import Command, Tool

from ..constants import BLESSINGS, PICK_PHRASES
from ..renderers import render_help, render_song_detail, render_today
from ..util import error_msg, format_music_summary, is_error, stable_user_uid
from .base import SharedHelpersMixin

logger = logging.getLogger(__name__)


class BasicCommandsMixin(SharedHelpersMixin):

    # ---- 帮助 ----

    @Command(
        "mai_help",
        description="显示 MaiMai DX 查分器命令总览",
        pattern=r"^/mai help$",
    )
    async def handle_help(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        ok = await self._render_and_send(
            stream_id,
            lambda: render_help(self._renderer),
            "帮助图片生成失败",
        )
        return ok, "显示帮助", True

    # ---- 随机选择 ----

    @Command(
        "mai_pick",
        description="随机选择 — 帮你在 2~4 个选项中做决定",
        pattern=r"^/mai (pick|choose|选|选择)\s+(?P<options>.+)$",
    )
    async def handle_pick(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("options"):
            await self.ctx.send.text(
                "用法: /mai pick <选项1> <选项2> [选项3] [选项4]\n"
                "例: /mai pick 吃饭 睡觉 打机 摸鱼\n"
                "ソルト会从选项中帮你挑一个哦～",
                stream_id,
            )
            return False, "参数错误", True
        raw = matched_groups["options"].strip()
        opts = raw.split()
        if len(opts) < 2:
            await self.ctx.send.text(
                "诶…只给ソルト一个选项的话，根本没得选呢…\n至少给 2 个选项，用空格隔开就好～",
                stream_id,
            )
            return False, "选项不足", True
        if len(opts) > 4:
            opts = opts[:4]
        opts = [o for o in opts if 1 <= len(o) <= 10]
        if len(opts) < 2:
            await self.ctx.send.text(
                "ソルト揉着面团歪了歪头…每个选项 1~10 个字比较合适呢，太长了ソルト会看花眼的喵～",
                stream_id,
            )
            return False, "选项无效", True
        chosen = random.choice(opts)
        opts_display = "\n".join(f"  {i}. {_html.escape(o)}" for i, o in enumerate(opts, 1))
        phrase = random.choice(PICK_PHRASES).format(choice=_html.escape(chosen), count=len(opts))
        await self.ctx.send.text(
            f"【ソルト帮你选】\n\n{opts_display}\n\n{phrase}",
            stream_id,
        )
        return True, "随机选择", True

    # ---- 曲目搜索 ----

    @Command(
        "mai_song",
        description="搜索舞萌 DX 曲目",
        pattern=r"^/mai song\s+(?P<keyword>.+)$",
    )
    async def handle_song(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("keyword"):
            await self.ctx.send.text("用法: /mai song <关键词或歌曲ID>", stream_id)
            return False, "参数错误", True

        keyword = matched_groups["keyword"].strip()
        if not keyword:
            await self.ctx.send.text("请输入搜索关键词或歌曲ID", stream_id)
            return False, "参数为空", True

        songs = await self._music.get_songs()
        if not songs:
            await self.ctx.send.text("获取曲目列表失败，请稍后重试", stream_id)
            return False, "获取失败", True

        if keyword.isdigit():
            for music in songs:
                if isinstance(music, dict) and str(music.get("id", "") or "") == keyword:
                    sid = str(music.get("id", ""))
                    cover = await self._covers.get_cover_data_url(sid)
                    if cover:
                        await self.ctx.send.text("正在生成详情图片...", stream_id)
                        aliases = await self._aliases.list_aliases(sid)
                        extra = await self._music.enrich_with_lxns(music)
                        rendered = await self._render_and_send(
                            stream_id,
                            lambda: render_song_detail(
                                self._renderer, music, cover, aliases, extra,
                            ),
                            "曲目详情图片生成失败",
                        )
                        if rendered:
                            return True, "显示详情", True
                    detail = await self._build_song_detail_text(music)
                    await self.ctx.send.text(detail, stream_id)
                    return True, "显示详情", True

        matches = await self._music.match_songs(keyword)
        if not matches:
            await self.ctx.send.text(
                f"未找到匹配的曲目: \"{keyword}\"\n"
                "可使用部分关键词、作者名或别称搜索",
                stream_id,
            )
            return False, "无匹配", True

        limit = min(len(matches), 15)
        matches = matches[:limit]

        if len(matches) == 1:
            music = matches[0]
            sid = str(music.get("id", "") or "")
            cover = await self._covers.get_cover_data_url(sid)
            if cover:
                await self.ctx.send.text("正在生成详情图片...", stream_id)
                aliases = await self._aliases.list_aliases(sid)
                extra = await self._music.enrich_with_lxns(music)
                rendered = await self._render_and_send(
                    stream_id,
                    lambda: render_song_detail(
                        self._renderer, music, cover, aliases, extra,
                    ),
                    "曲目详情图片生成失败",
                )
                if rendered:
                    return True, "显示详情", True
            detail = await self._build_song_detail_text(music)
            await self.ctx.send.text(detail, stream_id)
            return True, "显示详情", True

        if len(matches) <= 5:
            lines = [f"搜索 \"{keyword}\" ({len(matches)} 条):"]
            for m in matches:
                lines.append("  " + format_music_summary(m))
            await self.ctx.send.text("\n".join(lines), stream_id)
        else:
            nodes: list[dict] = [
                {
                    "user_id": "0",
                    "nickname": f"搜索 \"{keyword}\" ({len(matches)} 条)",
                    "segments": [
                        {"type": "text", "content": "使用 /mai song <ID> 查看详情"}
                    ],
                }
            ]
            for idx, m in enumerate(matches, 1):
                sid = str(m.get("id", "") or "?")
                title = str(m.get("title", "") or "?")
                tp = str(m.get("type", "") or "?")
                bi = m.get("basic_info", {})
                artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
                version = str(bi.get("from", "") or "?") if isinstance(bi, dict) else "?"
                ds_list = m.get("ds", [])
                max_ds = max(ds_list) if ds_list else 0
                nodes.append(
                    {
                        "user_id": "0",
                        "nickname": f"#{idx} [{_html.escape(tp)}] {_html.escape(title)}",
                        "segments": [
                            {
                                "type": "text",
                                "content": (
                                    f"{_html.escape(artist)} | ID:{_html.escape(sid)} | {_html.escape(version)}\n"
                                    f"max DS: {max_ds}"
                                ),
                            }
                        ],
                    }
                )
            await self.ctx.send.forward(nodes, stream_id)
        return True, "搜索完成", True

    # ---- 谱面统计 ----

    @Command(
        "mai_charts",
        description="查看全谱面难度分布统计",
        pattern=r"^/mai charts$",
    )
    async def handle_charts(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        data = await self._music.get_chart_stats()
        if not data or not isinstance(data, dict):
            await self.ctx.send.text("获取谱面统计失败或无数据", stream_id)
            return False, "获取失败", True

        diff_data = data.get("diff_data", {})
        if not diff_data:
            await self.ctx.send.text("暂无谱面统计数据", stream_id)
            return False, "无数据", True

        diff_order = [(0, "Basic"), (1, "Advanced"), (2, "Expert"), (3, "Master"), (4, "Re:Master")]
        lines = ["【全谱面难度分布统计】"]
        for diff_idx, diff_label in diff_order:
            key = str(diff_idx)
            if key in diff_data:
                d = diff_data[key]
                try:
                    ach = float(d.get("achievements", 0))
                except (TypeError, ValueError):
                    ach = 0.0
                fc_dist = d.get("fc_dist", [0, 0, 0, 0, 0])
                total = sum(fc_dist) if fc_dist else 1
                ap_rate = ((fc_dist[3] + fc_dist[4]) / total * 100) if total > 0 else 0
                fc_rate = ((sum(fc_dist[1:])) / total * 100) if total > 0 else 0
                lines.append(
                    f"{diff_label:12s}  均达成率: {ach:.2f}%  "
                    f"FC 率: {fc_rate:.1f}%  AP 率: {ap_rate:.1f}%"
                )

        lines.append(f"\n数据来源: diving-fish.com  (共 {len(data.get('charts', {}))} 首歌曲)")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "显示统计", True

    # ---- 服务器状态 ----

    @Command(
        "mai_status",
        description="查看 diving-fish 和 lxns 服务器状态",
        pattern=r"^/mai status$",
    )
    async def handle_status(self, stream_id: str = "", **kwargs: Any) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        lines = []
        resp = await self._df.alive_check()
        if is_error(resp):
            lines.append(f"diving-fish: 异常 ({error_msg(resp)})")
        elif isinstance(resp, dict) and resp.get("message") == "ok":
            lines.append("diving-fish: 正常 ✅")
        else:
            lines.append("diving-fish: 未知")
        if self._lxns is not None:
            lxns_resp = await self._lxns.alive_check()
            if self._lxns._is_error(lxns_resp):
                lines.append(f"lxns: 异常 ({lxns_resp.get('message', '')})")
            else:
                lines.append("lxns: 正常 ✅")
        else:
            lines.append("lxns: 未启用")
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "状态检测", True

    # ---- 今日运势 ----

    @Command(
        "mai_today",
        description="今日运势 — 查看今日宜忌与推荐歌曲",
        pattern=r"^/mai today$",
    )
    async def handle_today(self, stream_id: str = "", **kwargs: Any) -> tuple:
        user_id = self._get_user_id(kwargs)
        await self._track_user(stream_id, user_id)

        wm_list = [
            "拼机", "推分", "越级", "下埋", "夜勤",
            "练底力", "练手法", "打旧框", "干饭", "抓绝赞", "收歌",
        ]
        uid_int = stable_user_uid(user_id)
        t = time.localtime()
        days = t.tm_mday + 31 * t.tm_mon + 77
        h = (days * uid_int) >> 8

        rp = h % 100
        wm_value = []
        for _ in range(11):
            wm_value.append(h & 3)
            h >>= 2

        yi_parts: list[str] = []
        ji_parts: list[str] = []
        for i in range(11):
            if wm_value[i] == 3:
                yi_parts.append(wm_list[i])
            elif wm_value[i] == 0:
                ji_parts.append(wm_list[i])

        songs = await self._music.get_songs()
        if not songs:
            await self.ctx.send.text("获取曲目列表失败，请稍后重试", stream_id)
            return False, "获取失败", True

        seed = h % len(songs)
        music = songs[seed]
        if not isinstance(music, dict):
            await self.ctx.send.text("获取推荐曲目失败", stream_id)
            return False, "数据异常", True

        sid = str(music.get("id", "") or "")
        cover_data_url = await self._covers.get_cover_data_url(sid)

        yi_text = ", ".join(yi_parts) if yi_parts else "无"
        ji_text = ", ".join(ji_parts) if ji_parts else "无"
        title = str(music.get("title", "") or "???")
        tp = str(music.get("type", "") or "?")
        bi = music.get("basic_info", {})
        artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
        ds_list = music.get("ds", [])
        ds_str = " / ".join(str(d) for d in ds_list)
        blessing = random.choice(BLESSINGS)

        if cover_data_url:
            await self.ctx.send.text("正在生成运势图片...", stream_id)
            rendered = await self._render_and_send(
                stream_id,
                lambda: render_today(
                    self._renderer, rp, yi_parts, ji_parts, music,
                    cover_data_url, blessing=blessing,
                ),
                "运势图片生成失败",
            )
            if rendered:
                return True, "今日运势", True

        lines = [
            f"【今日运势】\n人品值: {rp}",
            f"宜: {yi_text}",
            f"忌: {ji_text}",
            "━━━━━━━━━━━━━━",
            f"推荐曲目: [{_html.escape(tp)}] {_html.escape(title)} — {_html.escape(artist)}",
            f"ID: {_html.escape(sid)}  |  定数: {ds_str}",
            blessing,
        ]
        await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "今日运势", True

    # ---- 别称管理 ----

    @Command(
        "mai_alias_add",
        description="为歌曲添加别称",
        pattern=r"^/mai alias add\s+(?P<song_id>\S+)\s+(?P<alias>.+)$",
    )
    async def handle_alias_add(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai alias add <歌曲ID> <别称>", stream_id)
            return False, "参数错误", True

        song_id = matched_groups["song_id"].strip()
        alias = matched_groups.get("alias", "").strip()
        if not alias:
            await self.ctx.send.text("用法: /mai alias add <歌曲ID> <别称>", stream_id)
            return False, "参数错误", True

        songs = await self._music.get_songs()
        if not songs:
            await self.ctx.send.text("获取曲目列表失败，请稍后重试", stream_id)
            return False, "获取失败", True

        found = any(
            isinstance(m, dict) and str(m.get("id", "") or "") == song_id
            for m in songs
        )
        if not found:
            await self.ctx.send.text(
                f"歌曲 ID {song_id} 不存在于曲库中\n"
                "可使用 /mai song <关键词> 搜索歌曲ID",
                stream_id,
            )
            return False, "ID不存在", True

        ok, msg = await self._aliases.add(song_id, alias)
        if ok:
            title = next(
                (
                    str(m.get("title", "") or "?")
                    for m in songs
                    if isinstance(m, dict) and str(m.get("id", "") or "") == song_id
                ),
                "?",
            )
            await self.ctx.send.text(
                f"【别称管理】\n状态: 添加成功\n{_html.escape(title)} (ID: {_html.escape(song_id)}) ← \"{_html.escape(alias)}\"",
                stream_id,
            )
        else:
            await self.ctx.send.text(
                f"【别称管理】\n状态: 添加失败\n原因: {msg}", stream_id
            )
        return True, "添加别称", True

    @Command(
        "mai_alias_del",
        description="删除歌曲别称",
        pattern=r"^/mai alias del\s+(?P<song_id>\S+)\s+(?P<alias>.+)$",
    )
    async def handle_alias_del(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai alias del <歌曲ID> <别称>", stream_id)
            return False, "参数错误", True
        song_id = matched_groups["song_id"].strip()
        alias = matched_groups.get("alias", "").strip()
        if not alias:
            await self.ctx.send.text("用法: /mai alias del <歌曲ID> <别称>", stream_id)
            return False, "参数错误", True
        ok, msg = await self._aliases.delete(song_id, alias)
        if ok:
            await self.ctx.send.text(
                f"【别称管理】\n状态: 删除成功\n歌曲 {_html.escape(song_id)} 不再使用 \"{_html.escape(alias)}\"",
                stream_id,
            )
        else:
            await self.ctx.send.text(f"【别称管理】\n状态: 删除失败\n原因: {msg}", stream_id)
        return True, "删除别称", True

    @Command(
        "mai_alias_list",
        description="查看歌曲所有别称",
        pattern=r"^/mai alias list\s+(?P<song_id>\S+)$",
    )
    async def handle_alias_list(
        self, stream_id: str = "", matched_groups: dict = None, **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if not matched_groups or not matched_groups.get("song_id"):
            await self.ctx.send.text("用法: /mai alias list <歌曲ID>", stream_id)
            return False, "参数错误", True
        song_id = matched_groups["song_id"].strip()
        songs = await self._music.get_songs()
        title = song_id
        if songs:
            for music in songs:
                if isinstance(music, dict) and str(music.get("id", "") or "") == song_id:
                    title = str(music.get("title", "") or "?")
                    break
        aliases = await self._aliases.list_aliases(song_id)
        if not aliases:
            await self.ctx.send.text(
                f"【别称管理】\n{_html.escape(title)} (ID: {_html.escape(song_id)}) 暂无比称",
                stream_id,
            )
        else:
            lines = [
                "【别称管理】",
                f"{_html.escape(title)} (ID: {_html.escape(song_id)}) 的别称:",
            ]
            for i, a in enumerate(aliases, 1):
                lines.append(f"  {i}. {_html.escape(a)}")
            await self.ctx.send.text("\n".join(lines), stream_id)
        return True, "列出别称", True

    @Command(
        "mai_alias_import",
        description="从 lxns 导入社区别名到本地",
        pattern=r"^/mai alias import$",
    )
    async def handle_alias_import(
        self, stream_id: str = "", **kwargs: Any,
    ) -> tuple:
        await self._track_user(stream_id, self._get_user_id(kwargs))
        if self._lxns is None:
            await self.ctx.send.text("lxns 数据补全未启用，请在配置中开启", stream_id)
            return False, "未启用", True

        async def fetch_page(page: int) -> dict:
            return await self._lxns.get_alias_list(page)

        await self.ctx.send.text("正在从 lxns 导入社区别名，可能需要一些时间...", stream_id)
        imported, skipped = await self._aliases.import_from_lxns(fetch_page)
        await self.ctx.send.text(
            f"【别名导入】\n"
            f"新增: {imported} 个\n"
            f"跳过(已存在): {skipped} 个",
            stream_id,
        )
        return True, "导入完成", True

    # ---- AI 工具 ----

    @Tool(
        "search_mai_songs",
        description="按名称/艺术家/ID/别称搜索舞萌DX曲库",
        parameters={"keyword": {"type": "string", "description": "搜索关键词", "required": True}},
    )
    async def handle_tool_search_songs(
        self, keyword: str = "", **kwargs: Any,
    ) -> dict:
        del kwargs
        await self._ensure_clients()
        songs = await self._music.get_songs()
        if not songs:
            return {"name": "search_mai_songs", "content": "获取曲目列表失败"}

        if keyword.isdigit():
            for music in songs:
                if isinstance(music, dict) and str(music.get("id", "") or "") == keyword:
                    return {
                        "name": "search_mai_songs",
                        "content": json.dumps(
                            {
                                "id": music.get("id"),
                                "title": music.get("title"),
                                "artist": (music.get("basic_info") or {}).get("artist", ""),
                                "type": music.get("type"),
                                "version": (music.get("basic_info") or {}).get("from", ""),
                                "ds": music.get("ds", []),
                                "level": music.get("level", []),
                            },
                            ensure_ascii=False,
                        ),
                    }
            return {"name": "search_mai_songs", "content": f"未找到歌曲 ID: {keyword}"}

        matches = (await self._music.match_songs(keyword))[:10]
        if not matches:
            return {
                "name": "search_mai_songs",
                "content": f"未找到匹配 \"{keyword}\" 的曲目",
            }
        result = [
            {
                "id": m.get("id"),
                "title": m.get("title"),
                "artist": (m.get("basic_info") or {}).get("artist", ""),
                "type": m.get("type"),
                "version": (m.get("basic_info") or {}).get("from", ""),
                "max_ds": max(m.get("ds", [0])) if m.get("ds") else 0,
            }
            for m in matches
        ]
        return {
            "name": "search_mai_songs",
            "content": json.dumps(result, ensure_ascii=False),
        }
