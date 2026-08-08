# -*- coding: utf-8 -*-
"""Maidle 猜歌相关图片渲染。"""

import html as _html
from typing import Optional

from ..services.renderer import HtmlRenderer
from ..util import format_maidle_test
from .common import doc


async def render_maidle_guess(
    renderer: HtmlRenderer, guess_id: int, test: dict,
    header: str = "猜测结果",
) -> str:
    clues = format_maidle_test(test)
    style = (
        ".header{text-align:center;margin-bottom:20px}"
        ".header h2{font-size:20px;color:#e8e8f0;letter-spacing:2px;margin-bottom:4px}"
        ".header .guess{font-size:14px;color:#7878a8}"
        ".sep{border-top:1px solid #333350;margin:18px 0}"
        ".clues{font-size:15px;color:#c8c8d8;line-height:1.8;padding:8px 16px;background:#24243a;border-radius:8px;white-space:pre-wrap}"
        ".tips{margin-top:18px;font-size:13px;color:#6868a0;text-align:center}"
    )
    body = (
        '<div class="header"><h2>Maidle 猜歌</h2>'
        f'<div class="guess">{_html.escape(header)}: ID.{guess_id}</div></div>'
        '<div class="sep"></div>'
        f'<div class="clues">{_html.escape(clues)}</div>'
        '<div class="tips">继续: /mai maidle guess &lt;ID&gt;  |  放弃: /mai maidle answer</div>'
        '<div style="text-align:right;margin-top:16px;font-size:12px;color:#585878">MaiBot</div>'
    )
    return await renderer.render(doc(style, body), width=480, height=400)


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
        ".header{text-align:center;margin-bottom:22px}"
        ".header h2{font-size:20px;color:#e8e8f0;letter-spacing:2px}"
        ".body2{display:flex;gap:24px;align-items:flex-start}"
        ".cover{flex-shrink:0;width:160px;height:160px;border-radius:10px;overflow:hidden;border:2px solid #444460;box-shadow:0 2px 10px rgba(0,0,0,.3)}"
        ".cover img{width:100%;height:100%;object-fit:cover;display:block}"
        ".info{flex:1;display:flex;flex-direction:column;gap:8px;padding-top:4px;min-width:0}"
        ".info .song{font-size:20px;color:#e4e4f0;font-weight:600;letter-spacing:1px;overflow-wrap:break-word}"
        ".info .artist{font-size:15px;color:#a0a0c0}"
        ".info .sid{font-size:13px;color:#6868a0}"
        ".footer{margin-top:22px;text-align:center;font-size:13px;color:#6868a0}"
    )
    body = (
        '<div class="header"><h2>Maidle 答案</h2></div>'
        '<div class="body2">'
        f"{cover_html}"
        '<div class="info">'
        f'<div class="song">{_html.escape(title)}</div>'
        f'<div class="artist">{_html.escape(artist)}</div>'
        f'<div class="sid">ID: {_html.escape(sid)}</div>'
        "</div></div>"
        '<div class="footer">使用 /mai maidle 开始新游戏</div>'
        '<div style="text-align:right;margin-top:16px;font-size:12px;color:#585878">MaiBot</div>'
    )
    return await renderer.render(
        doc(style, body),
        width=560,
        height=350,
        wait_images=bool(cover_data_url),
        strict_images=True,
    )
