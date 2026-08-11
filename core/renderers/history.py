# -*- coding: utf-8 -*-
"""单曲游玩历史渲染（落雪，浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from ..util import fmt_utc, safe_float
from .common import doc, safe_str
from .theme import panel_style


async def render_history(
    renderer: HtmlRenderer,
    title: str,
    history: list[dict],
) -> str:
    rows = []
    for h in history[:20]:
        time_str = fmt_utc(h.get("play_time"))
        ach = h.get("achievements")
        ach_str = f"{safe_float(ach):.4f}%" if ach is not None else "-"
        rate = safe_str(h.get("rate"), "-")
        fc = safe_str(h.get("fc"), "-") or "-"
        rows.append(
            "<tr>"
            f'<td class="td-lv">{_html.escape(safe_str(h.get("level_name"), "?"))}</td>'
            f'<td class="td-ach">{_html.escape(ach_str)}</td>'
            f'<td class="td-rate">{_html.escape(rate)}</td>'
            f'<td class="td-fc">{_html.escape(fc)}</td>'
            f'<td class="td-time">{_html.escape(time_str)}</td>'
            "</tr>"
        )
    extra = (
        ".table{width:100%;border-collapse:collapse;margin-top:10px}"
        ".table th{font-size:12px;color:#8B7BA6;padding:6px 10px;text-align:left;border-bottom:2px solid #EFE6F7}"
        ".table td{font-size:14px;color:#4A3B63;padding:7px 10px;border-bottom:1px solid #F3EEF8}"
        ".td-lv{width:110px;color:#7048E8;font-weight:700}"
        ".td-ach{width:120px;color:#C77D3A;font-weight:600}"
        ".td-rate{width:90px}"
        ".td-fc{width:90px}"
        ".td-time{color:#8B7BA6}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">游玩历史</div>'
        f'<div class="p-sub">{_html.escape(safe_str(title, "?"))}（{len(history[:20])} 条）</div>'
        '<table class="table"><tr><th>难度</th><th>达成率</th><th>评级</th><th>FC</th><th>时间</th></tr>'
        + "".join(rows)
        + "</table>"
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · 落雪</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(extra), body), width=760, height=280 + len(rows) * 36)
