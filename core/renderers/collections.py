# -*- coding: utf-8 -*-
"""落雪收藏品渲染（浅色面板风格）。"""

import html as _html
from typing import Any

from ..services.renderer import HtmlRenderer
from .common import doc, safe_str
from .theme import panel_style


def _equip_html(label: str, value: Any) -> str:
    if isinstance(value, dict):
        name = safe_str(value.get("name"), "?")
        color = safe_str(value.get("color"), "")
        extra = f"（{_html.escape(color)}）" if color else ""
        return (
            f'<div class="row"><span class="label">{label}</span>'
            f'{_html.escape(name)}{extra}</div>'
        )
    if value:
        return (
            f'<div class="row"><span class="label">{label}</span>'
            f"{_html.escape(str(value))}</div>"
        )
    return ""


async def render_collections(
    renderer: HtmlRenderer,
    player: dict,
    collections: dict,
) -> str:
    equips = "".join(
        _equip_html(label, player.get(key))
        for label, key in (
            ("称号", "trophy"), ("头像", "icon"),
            ("姓名框", "name_plate"), ("背景", "frame"),
        )
    )
    rank_rows = ""
    if player.get("course_rank") is not None:
        rank_rows += f'<div class="row"><span class="label">段位</span>{_html.escape(str(player["course_rank"]))}</div>'
    if player.get("class_rank") is not None:
        rank_rows += f'<div class="row"><span class="label">阶级</span>{_html.escape(str(player["class_rank"]))}</div>'
    if player.get("star") is not None:
        rank_rows += f'<div class="row"><span class="label">搭档觉醒</span>{_html.escape(str(player["star"]))}</div>'

    labels = {
        "trophies": "称号", "icons": "头像",
        "plates": "姓名框", "frames": "背景",
    }
    list_html = ""
    for ctype, label in labels.items():
        items = collections.get(ctype) or []
        parts = []
        for c in items[:10]:
            if not isinstance(c, dict):
                continue
            name = safe_str(c.get("name"), "?")
            color = safe_str(c.get("color"), "")
            fav = " ★" if c.get("is_favorite") else ""
            parts.append(
                f'{_html.escape(name)}'
                + (f"（{_html.escape(color)}）" if color else "")
                + fav
            )
        if not parts:
            continue
        if len(items) > 10:
            parts.append(f"… 共 {len(items)} 个")
        list_html += (
            f'<div class="p-section">{label}（{len(items)}）</div>'
            f'<div class="tag-list">{" · ".join(parts)}</div>'
        )

    extra = (
        ".info-card{background:#F7F3FB;border-radius:14px;padding:14px 18px;margin-top:12px}"
        ".info-card .row{font-size:15px;color:#4A3B63;padding:4px 0}"
        ".info-card .row .label{color:#8B7BA6;margin-right:10px}"
        ".tag-list{background:#FFFFFF;border-radius:12px;padding:10px 14px;font-size:14px;color:#6B5D8A;line-height:1.9;box-shadow:0 2px 8px rgba(120,80,160,.08)}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">收藏品</div>'
        f'<div class="p-sub">{_html.escape(safe_str(player.get("name"), "玩家"))}</div>'
        f'<div class="info-card">{equips}{rank_rows}</div>'
        f"{list_html}"
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · 落雪</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(extra), body), width=720, height=520)
