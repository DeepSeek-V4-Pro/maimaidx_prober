# -*- coding: utf-8 -*-
"""水鱼按版本查询成绩渲染（/query/plate，Developer-Token）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from ..util import safe_float
from .common import doc, safe_str
from .theme import panel_style


async def render_plate(
    renderer: HtmlRenderer,
    username: str,
    versions: list[str],
    verlist: list[dict],
) -> str:
    rows = []
    for item in verlist[:60]:
        if not isinstance(item, dict):
            continue
        title = safe_str(item.get("title"), "?")
        level = safe_str(item.get("level_label") or item.get("level"), "?")
        ach = item.get("achievements")
        ach_str = f"{safe_float(ach):.4f}%" if ach is not None else "-"
        ra = item.get("ra")
        ra_str = str(ra) if ra is not None else "-"
        fc = safe_str(item.get("fc"), "-") or "-"
        rows.append(
            "<tr>"
            f'<td class="td-title">{_html.escape(title)}</td>'
            f'<td class="td-lv">{_html.escape(level)}</td>'
            f'<td class="td-ach">{_html.escape(ach_str)}</td>'
            f'<td class="td-ra">{_html.escape(ra_str)}</td>'
            f'<td class="td-fc">{_html.escape(fc)}</td>'
            "</tr>"
        )
    style = (
        ".table{width:100%;border-collapse:collapse;margin-top:12px}"
        ".table th{font-size:12px;color:#8B7BA6;padding:6px 10px;text-align:left;border-bottom:2px solid #EFE6F7}"
        ".table td{font-size:14px;color:#4A3B63;padding:7px 10px;border-bottom:1px solid #F3EEF8}"
        ".td-title{max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".td-lv{width:90px;color:#7048E8;font-weight:700}"
        ".td-ach{width:120px;color:#C77D3A;font-weight:600}"
        ".td-ra{width:70px;color:#7048E8;text-align:right;font-weight:700}"
        ".td-fc{width:80px}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">按版本查询成绩</div>'
        f'<div class="p-sub">@{_html.escape(username)} · 版本: {_html.escape("、".join(versions))}'
        f' · 共 {len(verlist[:60])} 条</div>'
        '<table class="table"><tr><th>曲目</th><th>难度</th><th>达成率</th><th>RA</th><th>FC</th></tr>'
        + "".join(rows)
        + "</table>"
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · diving-fish</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(
        doc(panel_style(style), body),
        width=860,
        height=240 + len(rows) * 36,
    )
