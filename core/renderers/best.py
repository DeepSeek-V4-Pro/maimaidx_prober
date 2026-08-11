# -*- coding: utf-8 -*-
"""单曲最佳成绩渲染（落雪，浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from ..util import safe_float
from .common import doc, safe_str
from .theme import panel_style


async def render_best(
    renderer: HtmlRenderer,
    title: str,
    rows: list[dict],
) -> str:
    row_html = []
    for r in rows:
        ach = r.get("achievements")
        ach_str = f"{safe_float(ach):.4f}%" if ach is not None else "-"
        fc = safe_str(r.get("fc"), "-") or "-"
        fs = safe_str(r.get("fs"), "-") or "-"
        dx = safe_str(r.get("dx_score"), "-")
        row_html.append(
            "<tr>"
            f'<td class="td-lv">{_html.escape(safe_str(r.get("level_name"), "?"))}</td>'
            f'<td class="td-type">{_html.escape(safe_str(r.get("type"), "?"))}</td>'
            f'<td class="td-ach">{_html.escape(ach_str)}</td>'
            f'<td class="td-dx">{_html.escape(dx)}</td>'
            f'<td class="td-fc">{_html.escape(fc)}</td>'
            f'<td class="td-fs">{_html.escape(fs)}</td>'
            f'<td class="td-time">{_html.escape(safe_str(r.get("upload_time"), ""))}</td>'
            "</tr>"
        )
    style = (
        ".table{width:100%;border-collapse:collapse;margin-top:10px}"
        ".table th{font-size:12px;color:#8B7BA6;padding:6px 10px;text-align:left;border-bottom:2px solid #EFE6F7}"
        ".table td{font-size:14px;color:#4A3B63;padding:7px 10px;border-bottom:1px solid #F3EEF8}"
        ".td-lv{width:110px;color:#7048E8;font-weight:700}"
        ".td-type{width:60px}"
        ".td-ach{width:130px;color:#C77D3A;font-weight:600}"
        ".td-dx{width:90px}"
        ".td-fc{width:70px}"
        ".td-fs{width:80px}"
        ".td-time{color:#8B7BA6}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">单曲最佳成绩</div>'
        f'<div class="p-sub">{_html.escape(safe_str(title, "?"))}（{len(rows)} 个谱面）</div>'
        '<table class="table"><tr><th>难度</th><th>类型</th><th>达成率</th><th>DX Score</th><th>FC</th><th>FS</th><th>最近游玩</th></tr>'
        + "".join(row_html)
        + "</table>"
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · 落雪</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=820, height=260 + len(rows) * 36)
