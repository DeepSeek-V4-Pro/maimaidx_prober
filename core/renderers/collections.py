# -*- coding: utf-8 -*-
"""落雪收藏品渲染（浅色面板 + 资源 CDN 实物图）。"""

import html as _html
from typing import Optional

from ..services.renderer import HtmlRenderer
from .common import doc, safe_str
from .theme import panel_style


def _tile_html(img_url: str, name: str, sub: str = "") -> str:
    img_html = (
        f'<img class="tile-img" src="{img_url}" '
        'onerror="this.style.display=\'none\'" />'
        if img_url
        else '<div class="tile-placeholder">?</div>'
    )
    return (
        '<div class="tile">'
        f'<div class="tile-media">{img_html}</div>'
        f'<div class="tile-name">{_html.escape(name)}</div>'
        + (f'<div class="tile-sub">{_html.escape(sub)}</div>' if sub else "")
        + "</div>"
    )


async def render_collections(
    renderer: HtmlRenderer,
    player: dict,
    collections: dict,
    assets: Optional[dict[str, str]] = None,
) -> str:
    assets = assets or {}
    # 当前装备区：头像/姓名框/背景优先实物图，称号看颜色
    equips: list[tuple[str, str, str]] = []
    for label, key, asset_key in (
        ("头像", "icon", "icon"),
        ("姓名框", "name_plate", "plate"),
        ("背景", "frame", "frame"),
        ("称号", "trophy", "trophy"),
    ):
        equip = player.get(key)
        if not isinstance(equip, dict):
            continue
        name = safe_str(equip.get("name"), "?")
        color = str(equip.get("color", "") or "")
        if color == "image":
            equips.append((label, name, assets.get(asset_key, "")))
        else:
            sub = f"（{color}）" if color else ""
            equips.append((label, name + sub, assets.get(asset_key, "")))
    equip_html = "".join(
        _tile_html(img, f"{label} · {name}")
        for label, name, img in equips
    ) if equips else '<div class="empty">无当前装备</div>'

    # 拥有列表区：每类最多 6 个缩略图
    labels = {
        "trophies": "称号", "icons": "头像",
        "plates": "姓名框", "frames": "背景",
    }
    list_html = ""
    for ctype, label in labels.items():
        items = collections.get(ctype) or []
        if not items:
            continue
        tiles = []
        for c in items[:6]:
            if not isinstance(c, dict):
                continue
            cid = c.get("id")
            name = safe_str(c.get("name"), "?")
            color = str(c.get("color", "") or "")
            img = assets.get(f"{ctype}_{cid}", "")
            fav = " ★" if c.get("is_favorite") else ""
            sub = (color if color and color != "image" else "") + fav
            tiles.append(_tile_html(img, name, sub))
        more = (
            f'<div class="more">… 共 {len(items)} 个</div>'
            if len(items) > 6 else ""
        )
        list_html += (
            f'<div class="p-section">{label}（{len(items)}）</div>'
            f'<div class="tile-grid">{"".join(tiles)}</div>'
            + more
        )

    style = (
        ".equip-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}"
        ".tile-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-top:6px}"
        ".tile{background:#FFFFFF;border-radius:14px;padding:10px;text-align:center;"
        "box-shadow:0 3px 10px rgba(120,80,160,.1)}"
        ".tile-media{height:64px;display:flex;align-items:center;justify-content:center;"
        "background:#F7F3FB;border-radius:10px;overflow:hidden;margin-bottom:7px}"
        ".tile-img{max-width:100%;max-height:64px;object-fit:contain;display:block}"
        ".tile-placeholder{font-size:24px;color:#C9BBDD;font-weight:800}"
        ".tile-name{font-size:12px;color:#4A3B63;font-weight:700;line-height:1.35;"
        "overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".tile-sub{font-size:11px;color:#8B7BA6;margin-top:2px}"
        ".empty{text-align:center;color:#8B7BA6;padding:18px 0;font-size:14px}"
        ".more{text-align:right;font-size:12px;color:#8B7BA6;margin-top:4px}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">收藏品</div>'
        f'<div class="p-sub">{_html.escape(safe_str(player.get("name"), "玩家"))}'
        f' · 段位 {safe_str(player.get("course_rank"), "-")}'
        f' · 阶级 {safe_str(player.get("class_rank"), "-")}'
        f' · 搭档觉醒 {safe_str(player.get("star"), "0")}</div>'
        f'<div class="equip-grid">{equip_html}</div>'
        + list_html
        + '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · 落雪</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    list_sections = sum(
        1 for ctype in ("trophies", "icons", "plates", "frames")
        if collections.get(ctype)
    )
    height = 360 + list_sections * 170
    return await renderer.render(doc(panel_style(style), body), width=860, height=max(400, height))
