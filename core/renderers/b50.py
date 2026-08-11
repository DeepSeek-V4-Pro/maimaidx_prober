# -*- coding: utf-8 -*-
"""Best 50 成绩图片渲染（官方 B50 版式复刻）。

版式：马卡龙渐变背景 + 青绿分区条（BEST 35 / BEST 15）+ 紫色成绩卡片
（文字居左、曲绘居右、右下编号框），配色与字体由 theme 设计系统提供。
封面沿用 diving-fish CDN 远程 URL，因此渲染时允许页面访问网络
（allow_network=True），失败自动隐藏。
"""

import html as _html
from typing import Any

from ..assets import maimai_icon, maimai_rank
from ..constants import DEFAULT_GAME_VERSION
from ..services.renderer import HtmlRenderer
from ..util import fmt_utc, safe_float
from .common import safe_str
from .theme import (
    doc,
    footer_html,
    header_html,
    page_style,
    placeholder_card_html,
    score_card_html,
    section_html,
)


def _df_cover_url(song_id: Any) -> str:
    try:
        sid = int(song_id)
    except (TypeError, ValueError):
        sid = 0
    if 10001 <= sid <= 11000:
        padded = str(sid - 10000).zfill(5)
    else:
        padded = str(sid).zfill(5)
    return f"https://www.diving-fish.com/covers/{padded}.png"


async def render_b50(
    renderer: HtmlRenderer,
    charts: dict,
    username: str,
    nickname: str,
    rating: int,
    query_time: str = "",
    blessing: str = "",
    avatar_url: str = "",
    version: int = DEFAULT_GAME_VERSION,
    course_rank: Any = None,
    class_rank: Any = None,
) -> str:
    sd = charts.get("sd", []) or []
    dx = charts.get("dx", []) or []

    def _cards_html(
        recs: list[dict], section_key: str, total_slots: int,
    ) -> str:
        parts = []
        for i, r in enumerate(recs):
            title = safe_str(r.get("title"), "???")
            tp = safe_str(r.get("type"), "SD")
            achievements = safe_float(r.get("achievements"))
            ra_val = r.get("ra", 0)
            fc_key = str(r.get("fc", "") or "")
            fs_key = str(r.get("fs", "") or "")
            ds_val = r.get("ds", 0)
            # 水鱼补全：优先使用水鱼歌曲 ID（落雪新曲 ID = 水鱼 ID − 10000）
            cover_song_id = r.get("df_song_id") or r.get("song_id", 0)
            cover_url = _df_cover_url(cover_song_id)
            rate_uri = maimai_rank(r.get("rate", ""))
            fc_uri = maimai_icon(fc_key)
            fs_uri = maimai_icon(fs_key)
            parts.append(
                score_card_html(
                    i + 1,
                    title=title,
                    achievements=f"{achievements:.4f}%",
                    ds=ds_val,
                    ra=ra_val,
                    rate_uri=rate_uri,
                    fc_uri=fc_uri,
                    fs_uri=fs_uri,
                    cover_url=cover_url,
                    section=section_key,
                    level=tp,
                    level_index=r.get("level_index", 2),
                    dx_star=r.get("dx_star"),
                    level_text=r.get("level", ""),
                    play_time=fmt_utc(
                        r.get("play_time") or r.get("last_played_time")
                    ),
                )
            )
        # 不满整行时补「未游玩」占位卡，保证 BEST 35 / BEST 15 网格完整
        for _ in range(len(recs), total_slots):
            parts.append(placeholder_card_html())
        return "".join(parts)

    body = (
        '<div class="page">'
        + header_html(
            nickname,
            username,
            rating,
            blessing,
            avatar_url,
            version,
            course_rank=course_rank,
            class_rank=class_rank,
        )
        + section_html("BEST 35", _cards_html(sd, "sd", 35))
        + section_html("BEST 15", _cards_html(dx, "dx", 15))
        + footer_html(f"查询时间: {_html.escape(query_time)}", "数据来源: maimai")
        + "</div>"
    )

    sd_rows = 7  # BEST 35 固定 7 行（不足补占位卡）
    dx_rows = 3  # BEST 15 固定 3 行
    total_rows = sd_rows + dx_rows
    card_h = 126
    header_h = 232
    section_extra = 132  # 分区条 + 内边距 + 外边距
    row_gap = 16
    footer_h = 130
    pad_top = 26
    height = (
        pad_top
        + header_h
        + section_extra * 2
        + total_rows * card_h
        + max(total_rows - 2, 0) * row_gap
        + footer_h
    )

    return await renderer.render(
        doc(page_style(), body),
        width=1600,
        height=height,
        wait_images=True,
        image_timeout=30000,
        allow_network=True,
        strict_images=False,
    )
