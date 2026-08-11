# -*- coding: utf-8 -*-
"""落雪年度回顾渲染（浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from .common import doc, safe_str
from .theme import panel_style


async def render_year(
    renderer: HtmlRenderer,
    review: dict,
    songs: list[tuple[str, int]] = None,
) -> str:
    year = safe_str(review.get("year"), "?")
    name = safe_str(review.get("player_name"), "玩家")
    uploads = review.get("player_total_uploads") or {}
    total = sum(int(v) for v in uploads.values() if isinstance(v, (int, float)))
    days = review.get("player_upload_days", 0)

    monthly = review.get("player_monthly_uploads") or {}
    top_months = sorted(
        ((int(k), int(v)) for k, v in monthly.items() if isinstance(v, (int, float))),
        key=lambda x: x[1], reverse=True,
    )[:3]
    months_html = (
        " · ".join(f"<b>{m}月</b>（{c}次）" for m, c in top_months)
        if top_months else "暂无"
    )

    top_songs = songs or []
    songs_html = " · ".join(
        f"{_html.escape(k)}（{c}次）" for k, c in top_songs[:5]
    ) if top_songs else "暂无"

    extra = (
        ".stat-grid{display:flex;gap:14px;justify-content:center;margin:18px 0;flex-wrap:wrap}"
        ".stat-box{background:#FFFFFF;border-radius:14px;padding:14px 22px;text-align:center;min-width:110px;box-shadow:0 3px 10px rgba(120,80,160,.1)}"
        ".stat-box .s-val{font-size:30px;font-weight:800;color:#7048E8}"
        ".stat-box .s-label{font-size:12px;color:#8B7BA6;margin-top:3px}"
        ".info-card{background:#F7F3FB;border-radius:14px;padding:14px 18px;margin-top:12px}"
        ".info-card .row{font-size:15px;color:#4A3B63;padding:5px 0}"
        ".info-card .row .label{color:#8B7BA6;margin-right:10px}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">年度回顾 {_html.escape(year)}</div>'
        f'<div class="p-sub">{_html.escape(name)}</div>'
        '<div class="stat-grid">'
        f'<div class="stat-box"><div class="s-val">{total}</div><div class="s-label">总上传</div></div>'
        f'<div class="stat-box"><div class="s-val">{days}</div><div class="s-label">出勤天数</div></div>'
        "</div>"
        '<div class="info-card">'
        f'<div class="row"><span class="label">最活跃月份</span>{months_html}</div>'
        f'<div class="row"><span class="label">打得最多的歌</span>{songs_html}</div>'
        "</div>"
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · 落雪</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(extra), body), width=720, height=420)
