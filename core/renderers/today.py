# -*- coding: utf-8 -*-
"""今日运势图片渲染。

曲绘通过 CoverService 校验后的 data URL 内嵌，
不再会出现「HTTP 200 但内容是 HTML」导致的曲绘缺失。
"""

import html as _html
from typing import Optional

from ..services.renderer import HtmlRenderer
from .common import doc, safe_str


async def render_today(
    renderer: HtmlRenderer,
    rp: int,
    yi_parts: list[str],
    ji_parts: list[str],
    music: dict,
    cover_data_url: Optional[str],
    blessing: str = "",
) -> str:
    title = safe_str(music.get("title"), "???")
    sid = safe_str(music.get("id"), "???")
    tp = safe_str(music.get("type"), "?")
    bi = music.get("basic_info", {})
    artist = safe_str(bi.get("artist"), "?") if isinstance(bi, dict) else "?"
    ds_list = music.get("ds", [])
    level_list = music.get("level", [])
    diffs_parts = [f"{lvl}({ds})" for lvl, ds in zip(level_list, ds_list)]
    ds_str = " / ".join(diffs_parts)

    yi_text = ", ".join(yi_parts) if yi_parts else "无"
    ji_text = ", ".join(ji_parts) if ji_parts else "无"
    rp_color = "#e06060" if rp < 30 else "#f0c860" if rp < 70 else "#60c060"
    cover_html = (
        f'<div class="cover"><img src="{cover_data_url}" /></div>'
        if cover_data_url
        else '<div class="cover cover-missing">曲绘缺失</div>'
    )

    style = (
        "body{padding:36px 48px}"
        ".header{text-align:center;margin-bottom:40px}"
        ".header h2{font-size:36px;color:#d0d0e0;margin-bottom:14px;letter-spacing:3px}"
        f".header .rp{{font-size:64px;font-weight:700;color:{rp_color}}}"
        ".section{margin:28px 0}"
        ".section .label{font-size:20px;color:#8888a8;margin-bottom:6px}"
        ".section .value{font-size:22px;color:#c8c8d8}"
        ".sep{border-top:1px solid #333350;margin:32px 0}"
        ".rec{display:flex;gap:32px;align-items:flex-start}"
        ".rec .cover{flex-shrink:0;width:220px;height:220px;border-radius:10px;overflow:hidden;border:2px solid #444460;box-shadow:0 2px 8px rgba(0,0,0,.3)}"
        ".rec .cover img{width:100%;height:100%;object-fit:cover;display:block}"
        ".rec .cover-missing{display:flex;align-items:center;justify-content:center;font-size:16px;color:#6868a0;background:#24243a}"
        ".rec .info{flex:1;display:flex;flex-direction:column;gap:12px;padding-top:6px;min-width:0}"
        ".rec .info .song{font-size:26px;color:#e4e4f0;font-weight:600;overflow-wrap:break-word}"
        ".rec .info .artist{font-size:20px;color:#a0a0c0}"
        ".rec .info .type-badge{font-size:15px;color:#8888b0;width:fit-content}"
        ".rec .info .ds{font-size:18px;color:#8080a8}"
        ".footer{margin-top:34px;text-align:center;font-size:17px;color:#6868a0}"
    )
    body = (
        f'<div class="header"><h2>今日运势</h2><div class="rp">{rp}</div></div>'
        '<div class="section"><div class="label">宜</div>'
        f'<div class="value">{_html.escape(yi_text)}</div></div>'
        '<div class="section"><div class="label">忌</div>'
        f'<div class="value">{_html.escape(ji_text)}</div></div>'
        '<div class="sep"></div><div class="rec">'
        f"{cover_html}"
        '<div class="info">'
        f'<div class="song">{_html.escape(title)}</div>'
        f'<div class="artist">{_html.escape(artist)}</div>'
        f'<div><span class="type-badge">{_html.escape(tp)}</span></div>'
        f'<div class="ds">定数: {_html.escape(ds_str)}</div>'
        f'<div style="font-size:15px;color:#6868a0">ID: {_html.escape(sid)}</div>'
        "</div></div>"
        f'<div class="footer">{_html.escape(blessing)}</div>'
        '<div style="text-align:right;margin-top:12px;font-size:12px;color:#585878">'
        "数据来源: diving-fish &middot; MaiBot</div>"
    )
    return await renderer.render(
        doc(style, body),
        width=880,
        height=760,
        wait_images=bool(cover_data_url),
        strict_images=True,
    )
