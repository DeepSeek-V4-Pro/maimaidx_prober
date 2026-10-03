# -*- coding: utf-8 -*-
"""今日运势图片渲染。

曲绘通过 CoverService 校验后的 data URL 内嵌，
不再会出现「HTTP 200 但内容是 HTML」导致的曲绘缺失。
"""

import html as _html
import random
from typing import Optional

from ..assets import data_uri
from ..services.renderer import HtmlRenderer
from .common import doc, safe_str
from .theme import panel_style

CHARA_ASSETS = (
    "awmc_core/mai/pic/prism_plus/chara_right.png",
    "awmc_core/mai/pic/prism_plus/chara_left.png",
    "awmc_core/mai/pic/prism_plus/chara.png",
    "awmc_core/mai/pic/circle/chara.png",
    "awmc_core/mai/pic/circle/chara_left.png",
    "awmc_core/mai/pic/circle/chara_right.png",
    "awmc_core/mai/pic/logo_foreground.webp",
)


async def render_today(
    renderer: HtmlRenderer,
    rp: int,
    yi_parts: list[str],
    ji_parts: list[str],
    music: dict,
    cover_data_url: Optional[str],
    blessing: str = "",
    chara_index: Optional[int] = None,
) -> str:
    title = safe_str(music.get("title"), "???")
    sid = safe_str(music.get("id"), "???")
    tp = safe_str(music.get("type"), "?")
    bi = music.get("basic_info", {})
    artist = safe_str(bi.get("artist"), "?") if isinstance(bi, dict) else "?"
    ds_list = music.get("ds", [])
    level_list = music.get("level", [])

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
        ".rec{display:flex;gap:26px;align-items:flex-start;position:relative}"
        ".rec-left{flex-shrink:0;width:210px}"
        ".rec .cover{flex-shrink:0;width:210px;height:210px;border-radius:14px;overflow:hidden;border:2px solid #EFE6F7;box-shadow:0 4px 14px rgba(120,80,160,.16)}"
        ".rec .cover img{width:100%;height:100%;object-fit:cover;display:block}"
        ".rec .cover-missing{display:flex;align-items:center;justify-content:center;font-size:15px;color:#8B7BA6;background:#F7F3FB}"
        ".cover-meta{display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:14px;color:#8B7BA6}"
        ".cover-meta .cover-id{color:#8B7BA6;font-weight:700}"
        ".cover-meta .cover-type{color:#7048E8;font-weight:700}"
        ".rec .info{flex:1;display:flex;flex-direction:column;gap:10px;padding-top:4px;min-width:0}"
        ".rec .info .song{font-size:24px;color:#4A3B63;font-weight:800;overflow-wrap:break-word}"
        ".rec .info .artist{font-size:17px;color:#6B5D8A}"
        ".rec .info .type-badge{font-size:13px;font-weight:700;color:#7048E8;background:#F0EAF8;border-radius:8px;padding:2px 10px;width:fit-content}"
        ".rec .info .ds{font-size:16px;color:#6B5D8A}"
        ".ds-wrap{display:flex;flex-direction:column;align-items:flex-start;gap:6px;margin-top:4px;width:100%}"
        ".ds-box{padding:4px 9px;border-radius:6px;border:1px solid;font-size:13px;font-weight:700;line-height:1.2;white-space:nowrap;text-shadow:0 1px 2px rgba(50,30,70,.65)}"
        ".ds-d0{color:rgba(255,255,255,1);border-color:rgba(132,220,84,1);background:rgba(132,220,84,1)}"
        ".ds-d1{color:rgba(255,255,255,1);border-color:rgba(244,188,20,1);background:rgba(244,188,20,1)}"
        ".ds-d2{color:rgba(255,255,255,1);border-color:rgba(252,132,140,1);background:rgba(252,132,140,1)}"
        ".ds-d3{color:rgba(255,255,255,1);border-color:rgba(156,84,220,1);background:rgba(156,84,220,1)}"
        ".ds-d4{color:rgba(255,255,255,1);border-color:rgba(190,130,248,1);background:rgba(190,130,248,1)}"
        ".panel.panel-chara-0{background:linear-gradient(150deg,rgba(233,215,246,.94) 0%,rgba(210,229,250,.94) 46%,rgba(249,222,244,.94) 100%)}"
        ".panel.panel-chara-1{background:linear-gradient(150deg,rgba(217,236,255,.94) 0%,rgba(238,247,255,.94) 52%,rgba(224,241,255,.94) 100%)}"
        ".panel.panel-chara-2{background:linear-gradient(150deg,rgba(226,218,248,.94) 0%,rgba(216,234,252,.94) 50%,rgba(248,223,243,.94) 100%)}"
        ".panel.panel-chara-3{background:linear-gradient(155deg,rgba(255,222,230,.94) 0%,rgba(255,231,224,.94) 22%,rgba(255,238,210,.94) 38%,rgba(249,235,221,.94) 48%,rgba(228,240,236,.94) 68%,rgba(232,226,246,.94) 100%)}"
        ".panel.panel-chara-4{background:linear-gradient(150deg,rgba(255,224,232,.94) 0%,rgba(243,237,244,.94) 52%,rgba(224,233,242,.94) 100%)}"
        ".panel.panel-chara-5{background:linear-gradient(150deg,rgba(255,240,210,.94) 0%,rgba(238,250,230,.94) 52%,rgba(252,236,236,.94) 100%)}"
        ".panel.panel-chara-6{background:linear-gradient(155deg,rgba(255,218,231,.94) 0%,rgba(255,232,240,.94) 20%,rgba(248,240,252,.94) 42%,rgba(226,233,252,.94) 68%,rgba(245,224,240,.94) 100%)}"
        ".chara{position:absolute;right:18px;top:4px;width:280px;height:280px;z-index:1;display:flex;justify-content:flex-end;overflow:visible}"
        ".chara img{width:280px;height:280px;object-fit:contain;object-position:right top}"
        ".chara.chara-logo{right:16px;top:2px;width:340px;height:240px}"
        ".chara.chara-logo img{width:340px;height:240px;object-fit:contain;object-position:center bottom}"
        ".p-footer .footer-message{flex:1;text-align:center;color:#6B5D8A}"
        ".footer{margin-top:22px;text-align:center;font-size:15px;color:#8B7BA6}"
    )
    cover_meta = (
        '<div class="cover-meta">'
        f'<span class="cover-id">ID: {_html.escape(sid)}</span>'
        f'<span class="cover-type">{_html.escape(tp)}</span>'
        "</div>"
    )
    ds_boxes = "".join(
        (
            f'<span class="ds-box ds-d{min(max(idx, 0), 4)}">'
            f"{_html.escape(str(level))} ({_html.escape(str(ds))})</span>"
        )
        for idx, (level, ds) in enumerate(zip(level_list, ds_list))
    )
    chara_idx = (
        max(0, min(int(chara_index), len(CHARA_ASSETS) - 1))
        if chara_index is not None
        else random.randrange(len(CHARA_ASSETS))
    )
    chara_uri = data_uri(CHARA_ASSETS[chara_idx])
    chara_html = (
        f'<div class="chara{" chara-logo" if chara_idx == 6 else ""}">'
        f'<img src="{chara_uri}" alt="" /></div>'
        if chara_uri
        else ""
    )
    body = (
        f'<div class="panel panel-chara-{chara_idx}">'
        f'<div class="p-title">今日运势</div>'
        f'<div class="p-sub">幸运指数 <span style="color:{rp_color};font-weight:800">{rp}</span> / 100</div>'
        '<div class="yi-ji">'
        '<div class="box yi"><div class="label">宜</div>'
        f'<div class="value">{_html.escape(yi_text)}</div></div>'
        '<div class="box ji"><div class="label">忌</div>'
        f'<div class="value">{_html.escape(ji_text)}</div></div>'
        "</div>"
        '<div class="sep"></div><div class="rec">'
        f'<div class="rec-left">{cover_html}{cover_meta}</div>'
        '<div class="info">'
        f'<div class="song">{_html.escape(title)}</div>'
        f'<div class="artist">{_html.escape(artist)}</div>'
        f'<div class="ds">定数<span class="ds-wrap">{ds_boxes}</span></div>'
        "</div>"
        + chara_html
        + "</div>"
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai</span>'
        f'<span class="footer-message">{_html.escape(blessing)}</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(
        doc(panel_style(style), body),
        width=880,
        height=560,
        wait_images=bool(cover_data_url),
        strict_images=True,
    )
