# -*- coding: utf-8 -*-
"""曲目详情图片渲染。"""

import html as _html
from typing import Optional

from ..services.renderer import HtmlRenderer
from .common import doc, safe_str


async def render_song_detail(
    renderer: HtmlRenderer,
    music: dict,
    cover_data_url: Optional[str],
    aliases: list[str],
    extra: dict,
) -> str:
    sid = safe_str(music.get("id"), "?")
    title = safe_str(music.get("title"), "?")
    tp = safe_str(music.get("type"), "?")
    bi = music.get("basic_info", {})
    artist = safe_str(bi.get("artist"), "?") if isinstance(bi, dict) else "?"
    version = safe_str(bi.get("from"), "?") if isinstance(bi, dict) else "?"
    genre = safe_str(bi.get("genre"), "?") if isinstance(bi, dict) else "?"
    bpm = bi.get("bpm", "?") if isinstance(bi, dict) else "?"
    ds_list = music.get("ds", [])
    level_list = music.get("level", [])
    diffs_parts = [f"{lvl}({ds})" for lvl, ds in zip(level_list, ds_list)]
    ds_str = " / ".join(diffs_parts)

    alias_text = ", ".join(aliases) if aliases else "无"
    genre_display = _html.escape(str(extra.get("genre_name", "") or genre))
    version_display = _html.escape(str(extra.get("version_name", "") or version))
    map_name = _html.escape(str(extra.get("map_name", "")))
    map_row = (
        f'<div class="row"><span class="label">出处</span>{map_name}</div>'
        if map_name
        else ""
    )

    diff_rows_html = ""
    if extra:
        diffs = extra.get("difficulties", {})
        for cat_key, cat_label in [("standard", "SD"), ("dx", "DX"), ("utage", "宴")]:
            cat_diffs = diffs.get(cat_key, [])
            if not cat_diffs:
                continue
            for d in cat_diffs:
                if not isinstance(d, dict):
                    continue
                diff_idx = d.get("difficulty", 0)
                level_label = level_list[diff_idx] if diff_idx < len(level_list) else "?"
                kanji = _html.escape(d.get("kanji", ""))
                designer = _html.escape(d.get("note_designer", ""))
                buddy = " [Buddy]" if d.get("is_buddy", False) else ""
                notes = d.get("notes", {})
                note_parts = []
                if isinstance(notes, dict):
                    for nk in ("tap", "hold", "slide", "touch", "break"):
                        v = notes.get(nk, 0)
                        if v > 0:
                            note_parts.append(f"{nk[0].upper()}{v}")
                note_str = "/".join(note_parts) if note_parts else ""
                diff_rows_html += (
                    f'<div class="diff-row">'
                    f'<span class="diff-type">[{cat_label}]</span>'
                    f'<span class="diff-lvl">{_html.escape(level_label)}{buddy}</span>'
                )
                if kanji:
                    diff_rows_html += f'<span class="diff-kanji">({kanji})</span>'
                if designer:
                    diff_rows_html += f'<span class="diff-designer">{designer}</span>'
                if note_str:
                    diff_rows_html += f'<span class="diff-notes">Notes: {note_str}</span>'
                diff_rows_html += "</div>"

    style = (
        "body{padding:28px 32px 14px 32px}"
        ".header{margin-bottom:24px}"
        ".header .type-badge{font-size:13px;color:#8888b0;margin-right:10px;vertical-align:middle}"
        ".header .title{font-size:22px;color:#e8e8f0;font-weight:600;vertical-align:middle;letter-spacing:1px}"
        ".header .id{font-size:13px;color:#6868a0;margin-top:6px}"
        ".body2{display:flex;gap:28px;margin-top:20px}"
        ".cover2{flex-shrink:0;width:200px;height:200px;border-radius:10px;overflow:hidden;border:2px solid #444460;box-shadow:0 2px 10px rgba(0,0,0,.3)}"
        ".cover2 img{width:100%;height:100%;object-fit:cover;display:block}"
        ".cover2-missing{display:flex;align-items:center;justify-content:center;font-size:14px;color:#6868a0;background:#24243a}"
        ".info{flex:1;display:flex;flex-direction:column;gap:10px;min-width:0}"
        ".info .row{font-size:15px;color:#c8c8d8}"
        ".info .row .label{color:#7878a8;margin-right:8px}"
        ".info .ds{font-size:14px;color:#9090b8;line-height:1.8}"
        ".aliases{margin-top:22px;padding-top:14px;border-top:1px solid #333350;font-size:13px;color:#7878a0}"
        ".diff-section{margin-top:14px}"
        ".diff-section .sec-label{font-size:14px;color:#9090b8;margin-bottom:6px}"
        ".diff-row{font-size:12px;color:#a0a0c0;padding:2px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center}"
        ".diff-type{color:#6868a0;font-size:11px;min-width:28px}"
        ".diff-lvl{color:#c8c8d8;font-weight:600;min-width:80px}"
        ".diff-kanji{color:#9090b8;font-size:11px}"
        ".diff-designer{color:#7878a0;font-size:11px}"
        ".diff-notes{color:#707098;font-size:11px}"
        ".footer-bar{display:flex;align-items:center;margin-top:18px;padding-top:10px;border-top:1px solid #333350;font-size:12px}"
        ".footer-source{color:#7878a8;flex:1;text-align:left}"
        ".footer-mai{color:#585878;flex:1;text-align:right}"
    )
    cover_html = (
        f'<div class="cover2"><img src="{cover_data_url}" /></div>'
        if cover_data_url
        else '<div class="cover2 cover2-missing">曲绘缺失</div>'
    )
    body = (
        '<div class="header">'
        f'<div><span class="type-badge">{_html.escape(tp)}</span>'
        f'<span class="title">{_html.escape(title)}</span></div>'
        f'<div class="id">ID: {_html.escape(sid)}</div></div>'
        '<div class="body2">'
        f"{cover_html}"
        '<div class="info">'
        f'<div class="row"><span class="label">作者</span>{_html.escape(artist)}</div>'
        f'<div class="row"><span class="label">BPM</span>{_html.escape(str(bpm))}</div>'
        f'<div class="row"><span class="label">分类</span>{genre_display}</div>'
        f'<div class="row"><span class="label">版本</span>{version_display}</div>'
        f"{map_row}"
        f'<div class="ds">定数: {_html.escape(ds_str)}</div>'
        "</div></div>"
        '<div class="diff-section"><div class="sec-label">谱面详情</div>'
        f"{diff_rows_html}</div>"
        f'<div class="aliases">别称: {_html.escape(alias_text)}</div>'
        '<div class="footer-bar">'
        f'<span class="footer-source">{"数据来源: lxns + diving-fish" if extra else "数据来源: diving-fish"}</span>'
        '<span class="footer-mai">MaiBot</span></div>'
    )
    return await renderer.render(
        doc(style, body),
        width=680,
        height=100,
        wait_images=bool(cover_data_url),
        strict_images=True,
    )
