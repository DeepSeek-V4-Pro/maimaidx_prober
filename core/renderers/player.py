# -*- coding: utf-8 -*-
"""落雪玩家资料卡渲染（B50 同风格浅色面板）。"""

import html as _html
from typing import Optional

from ..assets import data_uri
from ..services.renderer import HtmlRenderer
from ..util import fmt_utc
from .common import doc, safe_str
from .theme import panel_style


async def render_player(
    renderer: HtmlRenderer,
    player: dict,
    username: str,
    source: str,
    assets: Optional[dict[str, str]] = None,
) -> str:
    assets = assets or {}
    name = safe_str(player.get("name") or player.get("nickname") or username, "未知玩家")
    friend_code = player.get("friend_code")
    rating = int(player.get("rating") or 0)
    course_rank = player.get("course_rank")
    class_rank = player.get("class_rank")
    star = player.get("star")
    upload_time = fmt_utc(player.get("upload_time"))

    initial = str(name).strip()[:1] or "?"
    if assets.get("avatar"):
        avatar = (
            f'<div class="avatar"><img src="{assets["avatar"]}" '
            'onerror="this.style.display=\'none\'" />'
            f'<span class="avatar-fallback">{_html.escape(initial)}</span></div>'
        )
    else:
        avatar = (
            f'<div class="avatar no-avatar">'
            f'<span class="avatar-fallback">{_html.escape(initial)}</span></div>'
        )

    badge_html = ""
    for key, max_v in (("class_rank", 25), ("course_rank", 23)):
        try:
            val = int(player.get(key))
        except (TypeError, ValueError):
            val = -1
        if 0 <= val <= max_v:
            uri = data_uri(f"maimai/{key}/{val}.webp")
            if uri:
                badge_html += (
                    f'<img class="badge" src="{uri}" title="{_html.escape(key)} {val}" />'
                )

    equip_rows = []
    for label, key in (
        ("称号", "trophy"), ("头像", "icon"),
        ("姓名框", "name_plate"), ("背景", "frame"),
    ):
        equip = player.get(key)
        if isinstance(equip, dict):
            equip_rows.append((label, str(equip.get("name", "?"))))
        elif equip:
            equip_rows.append((label, str(equip)))
    equip_html = "".join(
        f'<div class="row"><span class="label">{_html.escape(label)}</span>'
        f'<span class="value">{_html.escape(value)}</span></div>'
        for label, value in equip_rows
    )
    meta_rows = ""
    if friend_code:
        meta_rows += (
            f'<div class="row"><span class="label">好友码</span>'
            f'<span class="value">{friend_code}</span></div>'
        )
    if star is not None:
        meta_rows += (
            f'<div class="row"><span class="label">搭档觉醒</span>'
            f'<span class="value">{star}</span></div>'
        )
    if upload_time:
        meta_rows += (
            f'<div class="row"><span class="label">数据同步</span>'
            f'<span class="value">{_html.escape(upload_time)}</span></div>'
        )

    style = (
        ".head{display:flex;align-items:center;gap:20px;background:#FFFFFF;border-radius:16px;"
        "padding:18px 22px;box-shadow:0 3px 10px rgba(120,80,160,.1)}"
        ".avatar{width:88px;height:88px;border-radius:50%;flex:none;position:relative;overflow:hidden;"
        "background:linear-gradient(135deg,#FFD7EC,#CDE4FF);border:3px solid #FFFFFF;"
        "display:flex;align-items:center;justify-content:center;font-size:40px;font-weight:800;color:#7A5B8F}"
        ".avatar img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}"
        ".avatar .avatar-fallback{display:none}"
        ".avatar.no-avatar .avatar-fallback{display:block}"
        ".head-info{flex:1;min-width:0}"
        ".name{font-size:26px;font-weight:800;color:#4A3B63;letter-spacing:1px}"
        ".sub{font-size:14px;color:#8B7BA6;margin-top:4px}"
        ".rating{display:inline-flex;align-items:center;gap:8px;margin-top:10px;"
        "background:linear-gradient(90deg,#A78BFA,#7048E8);border-radius:12px;"
        "padding:7px 16px;color:#FFFFFF;font-weight:800;font-size:20px}"
        ".rating .rl{font-size:13px;font-weight:600;opacity:.9}"
        ".badges{display:flex;gap:8px;align-items:center}"
        ".badges .badge{height:46px;width:auto;mix-blend-mode:multiply}"
        ".card{background:#FFFFFF;border-radius:14px;padding:12px 18px;margin-top:12px;"
        "box-shadow:0 2px 8px rgba(120,80,160,.08)}"
        ".card .row{display:flex;padding:6px 0;font-size:15px;color:#4A3B63}"
        ".card .row .label{width:100px;color:#8B7BA6;flex:none}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">玩家资料</div>'
        '<div class="head">'
        f"{avatar}"
        '<div class="head-info">'
        f'<div class="name">{_html.escape(name)}</div>'
        f'<div class="sub">@{_html.escape(username)} · 来源: {_html.escape(source)}</div>'
        '<div class="rating"><span class="rl">DX Rating</span>'
        f"{rating}</div>"
        "</div>"
        f'<div class="badges">{badge_html}</div>'
        "</div>"
        f'<div class="card">{equip_html}{meta_rows}</div>'
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · '
        f'{_html.escape(source)}</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(
        doc(panel_style(style), body), width=720, height=430,
    )
