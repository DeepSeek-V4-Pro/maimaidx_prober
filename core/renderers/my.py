# -*- coding: utf-8 -*-
"""个人成绩摘要渲染（B50 同风格浅色面板）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from ..util import safe_float
from .common import doc, safe_str
from .theme import panel_style


async def render_my(
    renderer: HtmlRenderer,
    username: str,
    nickname: str,
    rating: int,
    additional_rating: int,
    plate: str,
    records: list[dict],
    class_rank: int = None,
    star: int = None,
) -> str:
    seen_sd: set[str] = set()
    seen_dx: set[str] = set()
    best_per_song: dict[tuple[str, str], dict] = {}
    for r in records:
        if not isinstance(r, dict):
            continue
        sid = str(r.get("song_id", "") or "")
        if not sid:
            continue
        tp = r.get("type", "SD")
        try:
            ra = int(r.get("ra") or 0)
        except (TypeError, ValueError):
            ra = 0
        if tp == "SD":
            seen_sd.add(sid)
        else:
            seen_dx.add(sid)
        key = (sid, tp)
        if key not in best_per_song or ra > best_per_song[key]["ra"]:
            best_per_song[key] = {"level_index": r.get("level_index", 0), "ra": ra, "record": r}

    total = len(best_per_song)
    sd_count = len(seen_sd)
    dx_count = len(seen_dx)

    diff_names = ["Basic", "Advanced", "Expert", "Master", "Re:Master"]
    diff_counts = [0, 0, 0, 0, 0]
    for info in best_per_song.values():
        try:
            li = int(info["level_index"])
        except (TypeError, ValueError):
            li = -1
        if 0 <= li < 5:
            diff_counts[li] += 1

    top_items = sorted(best_per_song.values(), key=lambda x: x["ra"], reverse=True)[:10]
    top_rows = "".join(
        f'<tr><td class="td-rank">#{i+1}</td>'
        f'<td class="td-title">{_html.escape(safe_str(x["record"].get("title"), "?"))}</td>'
        f'<td class="td-lvl">{_html.escape(safe_str(x["record"].get("level"), "?"))}</td>'
        f'<td class="td-ach">{safe_float(x["record"].get("achievements")):.4f}%</td>'
        f'<td class="td-ra">{x["ra"]}</td></tr>'
        for i, x in enumerate(top_items)
    )

    diff_rows = "".join(
        f'<div class="diff-row"><span class="diff-name">{diff_names[i]}</span>'
        f'<span class="diff-bar"><span class="diff-fill" style="width:{min(diff_counts[i]*100//max(total,1),100)}%"></span></span>'
        f'<span class="diff-cnt">{diff_counts[i]}</span></div>'
        for i in range(5)
    )

    extra = (
        ".rating{text-align:center;margin:14px 0}"
        ".rating .val{font-size:40px;font-weight:800;color:#7048E8;line-height:1.1}"
        ".rating .label{font-size:13px;color:#8B7BA6}"
        ".stats{display:flex;gap:14px;justify-content:center;margin:14px 0;flex-wrap:wrap}"
        ".stat-box{background:#FFFFFF;border-radius:14px;padding:12px 18px;text-align:center;min-width:76px;box-shadow:0 3px 10px rgba(120,80,160,.1)}"
        ".stat-box .s-val{font-size:20px;font-weight:800;color:#4A3B63}"
        ".stat-box .s-label{font-size:11px;color:#8B7BA6;margin-top:2px}"
        ".diff-row{display:flex;align-items:center;gap:10px;margin:7px 0}"
        ".diff-name{width:80px;font-size:13px;color:#6B5D8A;text-align:right}"
        ".diff-bar{flex:1;height:12px;background:#F0EAF8;border-radius:6px;overflow:hidden}"
        ".diff-fill{height:100%;background:linear-gradient(90deg,#A78BFA,#7048E8);border-radius:6px}"
        ".diff-cnt{width:36px;font-size:13px;color:#8B7BA6;text-align:right}"
        ".table{width:100%;border-collapse:collapse;margin-top:4px}"
        ".table th{font-size:12px;color:#8B7BA6;padding:5px 8px;text-align:left;border-bottom:2px solid #EFE6F7}"
        ".table td{font-size:13px;color:#4A3B63;padding:5px 8px;border-bottom:1px solid #F3EEF8}"
        ".td-rank{width:32px;color:#A78BFA;font-weight:700}"
        ".td-title{max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".td-lvl{width:52px;color:#6B5D8A}"
        ".td-ach{width:84px;color:#C77D3A;font-weight:600}"
        ".td-ra{width:52px;color:#7048E8;text-align:right;font-weight:700}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">{_html.escape(nickname or username)}</div>'
        f'<div class="p-sub">@{_html.escape(username)}</div>'
        f'<div class="rating"><div class="val">{rating}</div><div class="label">DX Rating</div></div>'
        '<div class="stats">'
        f'<div class="stat-box"><div class="s-val">{_html.escape(safe_str(plate, "-"))}</div><div class="s-label">牌子</div></div>'
        f'<div class="stat-box"><div class="s-val">{additional_rating}</div><div class="s-label">段位</div></div>'
        f'<div class="stat-box"><div class="s-val">{total}</div><div class="s-label">曲目数</div></div>'
        f'<div class="stat-box"><div class="s-val">{sd_count}</div><div class="s-label">SD 曲目</div></div>'
        f'<div class="stat-box"><div class="s-val">{dx_count}</div><div class="s-label">DX 曲目</div></div>'
        + (
            f'<div class="stat-box"><div class="s-val">{class_rank}</div><div class="s-label">阶级</div></div>'
            if class_rank is not None else ""
        )
        + (
            f'<div class="stat-box"><div class="s-val">{star}</div><div class="s-label">搭档觉醒</div></div>'
            if star is not None else ""
        )
        + "</div>"
        '<div class="p-section">难度分布</div>'
        f"{diff_rows}"
        '<div class="p-section">Top 10 成绩</div>'
        '<table class="table"><tr><th>#</th><th>曲目</th><th>难度</th><th>达成率</th><th>RA</th></tr>'
        f"{top_rows}</table>"
        '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(extra), body), width=680, height=620)
