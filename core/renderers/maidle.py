# -*- coding: utf-8 -*-
"""Maidle 猜歌相关图片渲染。"""

import html as _html
from typing import Optional

from ..services.renderer import HtmlRenderer
from ..util import format_maidle_test
from .common import doc
from .theme import panel_style


async def render_maidle_guess(
    renderer: HtmlRenderer, guess_id: int, test: dict,
    header: str = "猜测结果",
) -> str:
    clues = format_maidle_test(test)
    style = (
        ".guess{font-size:14px;color:#8B7BA6;text-align:center;margin-bottom:4px}"
        ".sep{border-top:1px solid #EFE6F7;margin:16px 0}"
        ".clues{font-size:15px;color:#4A3B63;line-height:1.8;padding:10px 16px;background:#F7F3FB;border-radius:12px;white-space:pre-wrap;box-shadow:0 2px 8px rgba(120,80,160,.08)}"
        ".tips{margin-top:16px;font-size:13px;color:#8B7BA6;text-align:center}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">Maidle 猜歌</div>'
        f'<div class="guess">{_html.escape(header)}: ID.{guess_id}</div>'
        '<div class="sep"></div>'
        f'<div class="clues">{_html.escape(clues)}</div>'
        '<div class="tips">继续: /mai maidle guess &lt;ID&gt;  |  放弃: /mai maidle answer</div>'
        '<div class="p-footer">'
        '<span class="footer-source">MaiBot</span><span class="footer-mai"></span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=480, height=420)


async def render_maidle_answer(
    renderer: HtmlRenderer,
    title: str,
    artist: str,
    sid: str,
    cover_data_url: Optional[str],
) -> str:
    cover_html = (
        f'<div class="cover"><img src="{cover_data_url}" /></div>'
        if cover_data_url
        else ""
    )
    style = (
        ".body2{display:flex;gap:22px;align-items:flex-start;margin-top:16px}"
        ".cover{flex-shrink:0;width:150px;height:150px;border-radius:14px;overflow:hidden;border:2px solid #EFE6F7;box-shadow:0 4px 14px rgba(120,80,160,.16)}"
        ".cover img{width:100%;height:100%;object-fit:cover;display:block}"
        ".info{flex:1;display:flex;flex-direction:column;gap:8px;padding-top:4px;min-width:0}"
        ".info .song{font-size:20px;color:#4A3B63;font-weight:800;letter-spacing:1px;overflow-wrap:break-word}"
        ".info .artist{font-size:15px;color:#6B5D8A}"
        ".info .sid{font-size:13px;color:#8B7BA6}"
        ".footer{margin-top:18px;text-align:center;font-size:13px;color:#8B7BA6}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">Maidle 答案</div>'
        '<div class="body2">'
        f"{cover_html}"
        '<div class="info">'
        f'<div class="song">{_html.escape(title)}</div>'
        f'<div class="artist">{_html.escape(artist)}</div>'
        f'<div class="sid">ID: {_html.escape(sid)}</div>'
        "</div></div>"
        '<div class="footer">使用 /mai maidle 开始新游戏</div>'
        '<div class="p-footer">'
        '<span class="footer-source">MaiBot</span><span class="footer-mai"></span></div>'
        "</div>"
    )
    return await renderer.render(
        doc(panel_style(style), body),
        width=560,
        height=360,
        wait_images=bool(cover_data_url),
        strict_images=True,
    )
