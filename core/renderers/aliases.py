# -*- coding: utf-8 -*-
"""别称列表渲染（浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from .common import doc, footer_bar, safe_str
from .theme import panel_style


async def render_aliases(
    renderer: HtmlRenderer,
    title: str,
    song_id: str,
    aliases: list[str],
) -> str:
    if not aliases:
        body = (
            '<div class="panel">'
            f'<div class="p-title">{_html.escape(safe_str(title, "?"))}</div>'
            f'<div class="p-sub">ID: {_html.escape(safe_str(song_id, "?"))}</div>'
            '<div class="empty">暂无比称 — 可用 /mai alias add 添加</div>'
            + footer_bar("数据来源: 本地")
            + "</div>"
        )
        style = ".empty{text-align:center;color:#8B7BA6;padding:28px 0;font-size:15px}"
        return await renderer.render(doc(panel_style(style), body), width=640, height=260)

    items = "".join(
        f'<div class="alias-row"><span class="idx">{i}</span>'
        f'<span class="name">{_html.escape(a)}</span></div>'
        for i, a in enumerate(aliases, 1)
    )
    style = (
        ".alias-row{display:flex;align-items:center;gap:14px;background:#FFFFFF;"
        "border-radius:12px;padding:11px 16px;margin:8px 0;box-shadow:0 2px 8px rgba(120,80,160,.08)}"
        ".alias-row .idx{width:34px;height:34px;border-radius:50%;background:#F0EAF8;color:#7048E8;"
        "font-weight:800;display:flex;align-items:center;justify-content:center;flex:none}"
        ".alias-row .name{font-size:16px;color:#4A3B63;font-weight:600}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">{_html.escape(safe_str(title, "?"))}</div>'
        f'<div class="p-sub">ID: {_html.escape(safe_str(song_id, "?"))} · 共 {len(aliases)} 个别称</div>'
        + items
        + footer_bar("数据来源: 本地")
        + "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=640, height=220 + len(aliases) * 50)
