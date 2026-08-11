# -*- coding: utf-8 -*-
"""DX Rating 排行榜渲染（水鱼 /rating_ranking，浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from .common import doc, footer_bar
from .theme import panel_style


async def render_ranking(
    renderer: HtmlRenderer,
    items: list[dict],
    limit: int,
) -> str:
    rows = []
    for i, item in enumerate(items, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        rows.append(
            "<tr>"
            f'<td class="td-rank">{medal}</td>'
            f'<td class="td-user">{_html.escape(str(item.get("username", "?")))}</td>'
            f'<td class="td-ra">{item.get("ra", 0)}</td>'
            "</tr>"
        )
    style = (
        ".table{width:100%;border-collapse:collapse;margin-top:12px}"
        ".table th{font-size:12px;color:#8B7BA6;padding:6px 10px;text-align:left;border-bottom:2px solid #EFE6F7}"
        ".table td{font-size:15px;color:#4A3B63;padding:8px 10px;border-bottom:1px solid #F3EEF8}"
        ".td-rank{width:64px;font-weight:800;color:#A78BFA}"
        ".td-user{max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".td-ra{width:90px;color:#7048E8;font-weight:800;text-align:right}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">DX Rating 排行榜</div>'
        f'<div class="p-sub">diving-fish 公开数据 · TOP {limit}（不含隐私用户）</div>'
        '<table class="table"><tr><th>名次</th><th>玩家</th><th>Rating</th></tr>'
        + "".join(rows)
        + "</table>"
        + footer_bar("数据来源: maimai · diving-fish")
        + "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=680, height=220 + len(rows) * 40)
