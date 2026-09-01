# -*- coding: utf-8 -*-
"""今日运势图片渲染。

曲绘通过 CoverService 校验后的 data URL 内嵌，
不再会出现「HTTP 200 但内容是 HTML」导致的曲绘缺失。
"""

import html as _html
from typing import Optional

from ..services.renderer import HtmlRenderer
from .common import doc, safe_str
from .theme import panel_style


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
        ".yi-ji{display:flex;gap:16px;margin:16px 0}"
        ".yi-ji .box{flex:1;background:#FFFFFF;border-radius:14px;padding:14px 18px;box-shadow:0 3px 10px rgba(120,80,160,.1)}"
        ".yi-ji .label{font-size:16px;font-weight:700;margin-bottom:6px}"
        ".yi-ji .yi .label{color:#3BA55D}"
        ".yi-ji .ji .label{color:#D9534F}"
        ".yi-ji .value{font-size:18px;color:#4A3B63}"
        ".sep{border-top:1px solid #EFE6F7;margin:22px 0}"
        ".rec{display:flex;gap:26px;align-items:flex-start}"
        ".rec .cover{flex-shrink:0;width:210px;height:210px;border-radius:14px;overflow:hidden;border:2px solid #EFE6F7;box-shadow:0 4px 14px rgba(120,80,160,.16)}"
        ".rec .cover img{width:100%;height:100%;object-fit:cover;display:block}"
        ".rec .cover-missing{display:flex;align-items:center;justify-content:center;font-size:15px;color:#8B7BA6;background:#F7F3FB}"
        ".rec .info{flex:1;display:flex;flex-direction:column;gap:10px;padding-top:4px;min-width:0}"
        ".rec .info .song{font-size:24px;color:#4A3B63;font-weight:800;overflow-wrap:break-word}"
        ".rec .info .artist{font-size:17px;color:#6B5D8A}"
        ".rec .info .type-badge{font-size:13px;font-weight:700;color:#7048E8;background:#F0EAF8;border-radius:8px;padding:2px 10px;width:fit-content}"
        ".rec .info .ds{font-size:16px;color:#6B5D8A}"
        ".footer{margin-top:22px;text-align:center;font-size:15px;color:#8B7BA6}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">今日运势</div>'
        f'<div class="p-sub">幸运指数 <span style="color:{rp_color};font-weight:800">{rp}</span> / 100</div>'
        '<div class="yi-ji">'
        '<div class="box yi"><div class="label">宜</div>'
        f'<div class="value">{_html.escape(yi_text)}</div></div>'
        '<div class="box ji"><div class="label">忌</div>'
        f'<div class="value">{_html.escape(ji_text)}</div></div>'
        "</div>"
        '<div class="sep"></div><div class="rec">'
        f"{cover_html}"
        '<div class="info">'
        f'<div class="song">{_html.escape(title)}</div>'
        f'<div class="artist">{_html.escape(artist)}</div>'
        f'<div><span class="type-badge">{_html.escape(tp)}</span></div>'
        f'<div class="ds">定数: {_html.escape(ds_str)}</div>'
        f'<div style="font-size:14px;color:#8B7BA6">ID: {_html.escape(sid)}</div>'
        "</div></div>"
        f'<div class="footer">{_html.escape(blessing)}</div>'
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(
        doc(panel_style(style), body),
        width=880,
        height=800,
        wait_images=bool(cover_data_url),
        strict_images=True,
    )
