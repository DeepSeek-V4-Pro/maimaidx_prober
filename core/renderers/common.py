# -*- coding: utf-8 -*-
"""渲染公共助手。"""

import html as _html
from typing import Any

from ..constants import BASE_HTML_STYLE
from .theme import font_face_css, FONT_STACK


def doc(style_extra: str, body: str) -> str:
    """组装标准 HTML 文档。"""
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><style>"
        + BASE_HTML_STYLE
        + font_face_css()
        + f"body{{font-family:{FONT_STACK}}}"
        + style_extra
        + "</style></head><body>"
        + body
        + "</body></html>"
    )


def cmd_section(label: str, cmds: list[tuple[str, str]], name_width: str = "380px") -> str:
    items = "".join(
        f'<div class="cmd"><span class="cmd-name">{_html.escape(c[0])}</span>'
        f'<span class="cmd-desc">{_html.escape(c[1])}</span></div>'
        for c in cmds
    )
    return (
        f'<div class="section"><div class="sec-label">{_html.escape(label)}</div>{items}</div>'
    )


def footer_bar(left: str = "数据来源: maimai", right: str = "MaiBot") -> str:
    return (
        '<div class="footer-bar">'
        f'<span class="footer-source">{_html.escape(left)}</span>'
        f'<span class="footer-mai">{_html.escape(right)}</span>'
        "</div>"
    )


def safe_str(v: Any, default: str = "?") -> str:
    return str(v) if v not in (None, "") else default
