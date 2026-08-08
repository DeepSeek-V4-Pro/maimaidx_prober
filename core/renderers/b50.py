# -*- coding: utf-8 -*-
"""Best 50 成绩图片渲染。

封面沿用 diving-fish CDN 远程 URL（浏览器内加载，失败自动隐藏），
因此渲染时允许页面访问网络（allow_network=True）。
"""

import html as _html
from typing import Any

from ..constants import FC_DISPLAY, RATE_DISPLAY
from ..services.renderer import HtmlRenderer
from ..util import safe_float
from .common import doc, safe_str

_DIFF_COLORS = {
    0: ("#4caf50", "#162316"),
    1: ("#e0b040", "#262016"),
    2: ("#e05050", "#261816"),
    3: ("#9b59b6", "#1c1626"),
    4: ("#a0a0d0", "#1a1a28"),
}


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
) -> str:
    sd = charts.get("sd", []) or []
    dx = charts.get("dx", []) or []

    def _cards_html(recs: list[dict], section_label: str) -> str:
        parts = [
            f'<div class="section-title">{section_label}  ({len(recs)} 首)</div>'
            '<div class="grid">'
        ]
        for i, r in enumerate(recs):
            title = safe_str(r.get("title"), "???")
            level = safe_str(r.get("level"), "?")
            tp = safe_str(r.get("type"), "SD")
            li = r.get("level_index", 2)
            if not isinstance(li, int) or li not in _DIFF_COLORS:
                li = 2
            song_id = r.get("song_id", 0)
            achievements = safe_float(r.get("achievements"))
            ra_val = r.get("ra", 0)
            rate = RATE_DISPLAY.get(r.get("rate", ""), r.get("rate", "-"))
            fc = FC_DISPLAY.get(r.get("fc", ""), r.get("fc", "-"))
            ds_val = r.get("ds", 0)
            border_color, bg_color = _DIFF_COLORS[li]
            cover_url = _df_cover_url(song_id)
            parts.append(
                f'<div class="card" style="border-left-color:{border_color};background:{bg_color}">'
                '<div class="tl">'
                f'<div class="rank">#{i + 1}</div>'
                f'<div class="type-badge">{_html.escape(str(tp))}</div>'
                f'<div class="level">Lv.{_html.escape(str(level))}</div>'
                "</div>"
                '<div class="tr">'
                f'<div class="title">{_html.escape(str(title))}</div>'
                f'<div class="achievements">{achievements:.4f}</div>'
                "</div>"
                '<div class="bl">'
                f'<div class="ra">RA:{ra_val}</div>'
                f'<div class="meta">{_html.escape(str(rate))} | {_html.escape(str(fc))} | DS:{ds_val}</div>'
                "</div>"
                '<div class="br">'
                f'<img class="cover" src="{cover_url}" onerror="this.style.display=\'none\'" />'
                "</div></div>"
            )
        parts.append("</div>")
        return "".join(parts)

    style = (
        "body{padding:36px 48px 18px 48px}"
        ".header{text-align:center;margin-bottom:40px}"
        ".header h2{font-size:44px;color:#e8e8f0;margin-bottom:6px;letter-spacing:3px}"
        ".header .sub{font-size:20px;color:#8888a8}"
        ".header .total{font-size:32px;color:#f0c060;margin-top:10px;font-weight:600}"
        ".section-title{font-size:28px;color:#d0d0e0;margin:30px 0 18px;padding-bottom:8px;border-bottom:1px solid #333350}"
        ".grid{display:grid;grid-template-columns:repeat(5,1fr);gap:18px}"
        ".card{display:grid;grid-template-columns:105px 1fr;grid-template-rows:auto auto;gap:6px 8px;padding:14px 16px 14px 14px;border-radius:10px;border-left:5px solid;min-height:280px;box-shadow:0 2px 8px rgba(0,0,0,.3)}"
        ".tl{display:flex;flex-direction:column;gap:3px;align-items:flex-start}"
        ".tr{display:flex;flex-direction:column;gap:6px;overflow:hidden;padding-right:2px}"
        ".bl{display:flex;flex-direction:column;gap:4px;justify-content:center}"
        ".br{display:flex;align-items:center;justify-content:center}"
        ".rank{font-size:21px;color:#6868a0}"
        ".title{font-size:22px;color:#e4e4f0;font-weight:600;min-height:60px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:break-word}"
        ".cover{width:130px;height:130px;border-radius:6px;object-fit:cover;opacity:0.92;box-shadow:0 2px 6px rgba(0,0,0,.4)}"
        ".type-badge{font-size:17px;color:#8888b0}"
        ".level{font-size:21px;color:#9090b8}"
        ".achievements{font-size:28px;color:#f0d060;font-weight:700}"
        ".ra{font-size:25px;color:#c0c0d4}"
        ".meta{font-size:19px;color:#7878a0}"
        ".footer-bar{display:flex;align-items:center;margin-top:44px;padding-top:18px;border-top:1px solid #333350;font-size:20px}"
        ".footer-time{color:#7878a8;flex:1;text-align:left}"
        ".footer-source{color:#7878a8;flex:1;text-align:center}"
        ".footer-mai{font-size:13px;color:#585878;flex:1;text-align:center}"
        ".blessing{color:#c0c0d8;flex:1;text-align:right}"
    )
    body = (
        '<div class="header">'
        "<h2>MaiMai DX / Best 50</h2>"
        f'<div class="sub">{_html.escape(nickname)}  (@{_html.escape(username)})</div>'
        f'<div class="total">DX Rating: {rating}</div></div>'
        f"{_cards_html(sd, 'B35 / 旧曲')}"
        f"{_cards_html(dx, 'B15 / 新曲')}"
        '<div class="footer-bar">'
        f'<span class="footer-time">查询时间: {_html.escape(query_time)}</span>'
        '<span class="footer-source">数据来源: diving-fish</span>'
        f'<span class="blessing">{_html.escape(blessing)}</span></div>'
    )

    sd_rows = (len(sd) + 4) // 5 if sd else 0
    dx_rows = (len(dx) + 4) // 5 if dx else 0
    total_rows = sd_rows + dx_rows
    card_h = 280
    header_h = 175
    section_h = 55
    row_gap = 18
    pad = 36
    height = header_h + section_h * 2 + total_rows * card_h + (total_rows - 2) * row_gap + pad * 2 + 100

    return await renderer.render(
        doc(style, body),
        width=1600,
        height=height,
        wait_images=True,
        image_timeout=30000,
        allow_network=True,
        strict_images=False,
    )
