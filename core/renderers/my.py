# -*- coding: utf-8 -*-
"""个人成绩摘要渲染。"""

import html as _html

from ..services.renderer import HtmlRenderer
from ..util import safe_float
from .common import doc, safe_str


async def render_my(
    renderer: HtmlRenderer,
    username: str,
    nickname: str,
    rating: int,
    additional_rating: int,
    plate: str,
    records: list[dict],
) -> str:
    seen_sd: set[str] = set()
    seen_dx: set[str] = set()
    best_per_song: dict[str, dict] = {}
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
        if sid not in best_per_song or ra > best_per_song[sid]["ra"]:
            best_per_song[sid] = {"level_index": r.get("level_index", 0), "ra": ra, "record": r}

    total = len(best_per_song)
    sd_count = len(seen_sd)
    dx_count = len(seen_dx)

    diff_names = ["Basic", "Advanced", "Expert", "Master", "Re:Master"]
    diff_counts = [0, 0, 0, 0, 0]
    for info in best_per_song.values():
        li = info["level_index"]
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

    style = (
        ".header{text-align:center;margin-bottom:20px}"
        ".header .nick{font-size:24px;color:#e8e8f0;font-weight:600;letter-spacing:2px}"
        ".header .user{font-size:14px;color:#7878a8;margin-top:4px}"
        ".rating{text-align:center;margin:16px 0}"
        ".rating .val{font-size:42px;font-weight:700;color:#f0c060}"
        ".rating .label{font-size:13px;color:#8888a8}"
        ".stats{display:flex;gap:20px;justify-content:center;margin:16px 0;flex-wrap:wrap}"
        ".stat-box{background:#24243a;border-radius:8px;padding:14px 20px;text-align:center;min-width:80px;box-shadow:0 2px 6px rgba(0,0,0,.2)}"
        ".stat-box .s-val{font-size:22px;font-weight:600;color:#e4e4f0}"
        ".stat-box .s-label{font-size:11px;color:#7878a8;margin-top:2px}"
        ".section-title{font-size:16px;color:#c0c0d8;font-weight:600;margin:18px 0 10px;padding-bottom:4px;border-bottom:1px solid #333350}"
        ".diff-row{display:flex;align-items:center;gap:10px;margin:6px 0}"
        ".diff-name{width:80px;font-size:13px;color:#a0a0c0;text-align:right}"
        ".diff-bar{flex:1;height:12px;background:#2a2a42;border-radius:6px;overflow:hidden}"
        ".diff-fill{height:100%;background:linear-gradient(90deg,#5b8fd4,#9b59b6);border-radius:6px}"
        ".diff-cnt{width:36px;font-size:13px;color:#8888a8;text-align:right}"
        ".table{width:100%;border-collapse:collapse;margin-top:6px}"
        ".table th{font-size:12px;color:#7878a8;padding:4px 6px;text-align:left;border-bottom:1px solid #2a2a42}"
        ".table td{font-size:13px;color:#c0c0d0;padding:3px 6px}"
        ".td-rank{width:32px;color:#6868a0}"
        ".td-title{max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".td-lvl{width:52px}"
        ".td-ach{width:80px;color:#f0d060}"
        ".td-ra{width:52px;color:#c0c0d4;text-align:right}"
    )
    body = (
        '<div class="header">'
        f'<div class="nick">{_html.escape(nickname or username)}</div>'
        f'<div class="user">@{_html.escape(username)}</div></div>'
        f'<div class="rating"><div class="val">{rating}</div><div class="label">DX Rating</div></div>'
        '<div class="stats">'
        f'<div class="stat-box"><div class="s-val">{_html.escape(safe_str(plate, "-"))}</div><div class="s-label">牌子</div></div>'
        f'<div class="stat-box"><div class="s-val">{additional_rating}</div><div class="s-label">段位</div></div>'
        f'<div class="stat-box"><div class="s-val">{total}</div><div class="s-label">总成绩数</div></div>'
        f'<div class="stat-box"><div class="s-val">{sd_count}</div><div class="s-label">SD 曲目</div></div>'
        f'<div class="stat-box"><div class="s-val">{dx_count}</div><div class="s-label">DX 曲目</div></div>'
        "</div>"
        '<div class="section-title">难度分布</div>'
        f"{diff_rows}"
        '<div class="section-title">Top 10 成绩</div>'
        '<table class="table"><tr><th>#</th><th>曲目</th><th>难度</th><th>达成率</th><th>RA</th></tr>'
        f"{top_rows}</table>"
        '<div style="text-align:right;margin-top:16px;font-size:12px;color:#585878">'
        "数据来源: diving-fish &middot; MaiBot</div>"
    )
    return await renderer.render(doc(style, body), width=680, height=600)
