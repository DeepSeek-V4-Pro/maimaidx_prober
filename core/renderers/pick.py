# -*- coding: utf-8 -*-
"""随机选择（ソルト帮你选）渲染（浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from .common import doc
from .theme import panel_style


async def render_pick(
    renderer: HtmlRenderer,
    options: list[str],
    chosen: str,
    phrase: str,
) -> str:
    rows = []
    for i, o in enumerate(options, 1):
        hl = " chosen" if o == chosen else ""
        rows.append(
            f'<div class="opt{hl}">'
            f'<span class="idx">{i}</span>'
            f'<span class="name">{_html.escape(o)}</span>'
            f'{"<span class=\"tag\">选中</span>" if hl else ""}'
            "</div>"
        )
    extra = (
        ".opts{display:flex;flex-direction:column;gap:10px;margin:18px 0}"
        ".opt{display:flex;align-items:center;gap:12px;background:#FFFFFF;border-radius:12px;padding:12px 16px;box-shadow:0 2px 8px rgba(120,80,160,.08);font-size:18px;color:#4A3B63}"
        ".opt .idx{width:28px;height:28px;border-radius:50%;background:#F0EAF8;color:#7048E8;font-weight:800;display:flex;align-items:center;justify-content:center;font-size:14px;flex:none}"
        ".opt.chosen{background:linear-gradient(90deg,#7048E8,#A78BFA);color:#FFFFFF;box-shadow:0 4px 14px rgba(112,72,232,.35)}"
        ".opt.chosen .idx{background:rgba(255,255,255,.25);color:#FFFFFF}"
        ".opt .tag{margin-left:auto;background:rgba(255,255,255,.92);color:#7048E8;font-size:13px;font-weight:800;border-radius:8px;padding:2px 10px}"
        ".phrase{margin-top:6px;font-size:15px;color:#6B5D8A;line-height:1.8;background:#F7F3FB;border-radius:12px;padding:12px 16px}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">ソルト帮你选</div>'
        f'<div class="p-sub">共 {len(options)} 个选项</div>'
        f'<div class="opts">{"".join(rows)}</div>'
        f'<div class="phrase">{_html.escape(phrase)}</div>'
        '<div class="p-footer">'
        '<span class="footer-source">MaiBot</span><span class="footer-mai"></span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(extra), body), width=560, height=300 + len(options) * 48)
