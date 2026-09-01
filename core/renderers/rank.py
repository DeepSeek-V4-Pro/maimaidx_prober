# -*- coding: utf-8 -*-
"""单曲分数排行渲染（落雪，浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from ..util import safe_float
from .common import doc, safe_str
from .theme import panel_style


async def render_rank(
    renderer: HtmlRenderer,
    title: str,
    ranking: list[dict],
) -> str:
    rows = []
    for r in ranking[:20]:
        ach = r.get("achievements")
        ach_str = f"{safe_float(ach):.4f}%" if ach is not None else "-"
        rows.append(
            "<tr>"
            f'<td class="td-rank">#{_html.escape(safe_str(r.get("ranking"), "?"))}</td>'
            f'<td class="td-lv">{_html.escape(safe_str(r.get("level_name"), "?"))}</td>'
            f'<td class="td-ach">{_html.escape(ach_str)}</td>'
            f'<td class="td-dx">DX {_html.escape(safe_str(r.get("dx_score"), "-"))}</td>'
            f'<td class="td-time">{_html.escape(safe_str(r.get("upload_time"), ""))}</td>'
            "</tr>"
        )
    extra = (
        ".table{width:100%;border-collapse:collapse;margin-top:10px}"
        ".table th{font-size:12px;color:#8B7BA6;padding:6px 10px;text-align:left;border-bottom:2px solid #EFE6F7}"
        ".table td{font-size:14px;color:#4A3B63;padding:7px 10px;border-bottom:1px solid #F3EEF8}"
        ".td-rank{width:70px;color:#A78BFA;font-weight:800}"
        ".td-lv{width:120px;color:#7048E8;font-weight:700}"
        ".td-ach{width:130px;color:#C77D3A;font-weight:600}"
        ".td-dx{width:90px}"
        ".td-time{color:#8B7BA6}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">分数排行</div>'
        f'<div class="p-sub">{_html.escape(safe_str(title, "?"))}</div>'
        '<table class="table"><tr><th>名次</th><th>难度</th><th>达成率</th><th>DX Score</th><th>时间</th></tr>'
        + "".join(rows)
        + "</table>"
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · 落雪</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(extra), body), width=760, height=280 + len(rows) * 36)
