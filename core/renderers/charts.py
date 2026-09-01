# -*- coding: utf-8 -*-
"""全谱面难度分布统计渲染（数据来自水鱼 /chart_stats）。"""

import html as _html
from typing import Any

from ..constants import RATE_DISPLAY
from ..services.renderer import HtmlRenderer
from .common import doc, footer_bar
from .theme import panel_style


def _rate_dist_bar(dist: Any) -> str:
    """把 14 档评级分布（d~sssp）渲染成横向堆叠条。"""

    if not isinstance(dist, list):
        return ""
    order = ["sssp", "sss", "ss", "s", "sp", "aaa", "aa", "a", "bbb", "bb", "b", "c", "d"]
    try:
        values = [int(v) for v in dist[:14]]
    except (TypeError, ValueError):
        return ""
    total = sum(values) or 1
    colors = {
        "sssp": "#C084FC", "sss": "#A78BFA", "ss": "#818CF8",
        "s": "#60A5FA", "sp": "#38BDF8", "aaa": "#F472B6",
        "aa": "#FBBF24", "a": "#F97316", "bbb": "#4ADE80",
        "bb": "#34D399", "b": "#2DD4BF", "c": "#94A3B8", "d": "#CBD5E1",
    }
    idx_map = {
        "d": 0, "c": 1, "b": 2, "bb": 3, "bbb": 4, "a": 5, "aa": 6,
        "aaa": 7, "s": 8, "sp": 9, "ss": 10, "ssp": 11, "sss": 12, "sssp": 13,
    }
    segs = []
    for rate in order:
        idx = idx_map[rate]
        if idx >= len(values):
            continue
        width = values[idx] * 100 / total
        if width < 0.5:
            continue
        segs.append(
            f'<span class="seg" style="background:{colors[rate]};width:{width:.2f}%" '
            f'title="{RATE_DISPLAY[rate]}: {values[idx]}"></span>'
        )
    return f'<div class="dist-bar">{"".join(segs)}</div>'


async def render_charts(
    renderer: HtmlRenderer,
    diff_data: dict,
    total_songs: int,
) -> str:
    diff_order = [("0", "Basic"), ("1", "Advanced"), ("2", "Expert"), ("3", "Master"), ("4", "Re:Master")]
    rows = []
    for diff_idx, diff_label in diff_order:
        d = diff_data.get(diff_idx) or {}
        try:
            ach = float(d.get("achievements", 0))
        except (TypeError, ValueError):
            ach = 0.0
        fc_dist = d.get("fc_dist", [0, 0, 0, 0, 0])
        if not isinstance(fc_dist, list) or len(fc_dist) < 5:
            fc_dist = [0, 0, 0, 0, 0]
        total = sum(fc_dist) or 1
        ap_rate = (fc_dist[3] + fc_dist[4]) * 100 / total
        fc_rate = sum(fc_dist[1:]) * 100 / total
        rows.append(
            '<tr>'
            f'<td class="td-diff">{_html.escape(diff_label)}</td>'
            f'<td class="td-ach">{ach:.2f}%</td>'
            f'<td class="td-fc">{fc_rate:.1f}%</td>'
            f'<td class="td-ap">{ap_rate:.1f}%</td>'
            f'<td class="td-dist">{_rate_dist_bar(d.get("dist"))}</td>'
            "</tr>"
        )
    style = (
        ".table{width:100%;border-collapse:collapse;margin-top:12px}"
        ".table th{font-size:12px;color:#8B7BA6;padding:7px 10px;text-align:left;border-bottom:2px solid #EFE6F7}"
        ".table td{font-size:14px;color:#4A3B63;padding:8px 10px;border-bottom:1px solid #F3EEF8;vertical-align:middle}"
        ".td-diff{width:110px;color:#7048E8;font-weight:700}"
        ".td-ach{width:110px;color:#C77D3A;font-weight:600}"
        ".td-fc{width:90px;color:#3FAE6D;font-weight:600}"
        ".td-ap{width:90px;color:#7048E8;font-weight:600}"
        ".dist-bar{display:flex;height:14px;border-radius:7px;overflow:hidden;background:#F0EAF8;min-width:180px}"
        ".dist-bar .seg{height:100%}"
        ".legend{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}"
        ".legend span{font-size:12px;color:#6B5D8A;background:#F7F3FB;padding:2px 9px;border-radius:8px}"
        ".tip{font-size:12px;color:#8B7BA6;margin-top:12px;line-height:1.7}"
    )
    legend_parts = "".join(
        f"<span>{_html.escape(RATE_DISPLAY[k])}</span>"
        for k in ("sssp", "sss", "ss", "s", "sp", "aaa", "aa", "a", "bbb", "bb", "b", "c", "d")
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">全谱面难度分布统计</div>'
        f'<div class="p-sub">diving-fish 拟合数据 · 共 {total_songs} 首歌曲</div>'
        '<table class="table"><tr><th>难度</th><th>均达成率</th><th>FC 率</th><th>AP 率</th><th>评级分布</th></tr>'
        + "".join(rows)
        + "</table>"
        f'<div class="legend">{legend_parts}</div>'
        '<div class="tip">FC 率 = FC/FC+/AP/AP+ 占比；AP 率 = AP/AP+ 占比；'
        '评级分布按全部已游玩谱面统计（拟合难度参考值，非权威）。</div>'
        + footer_bar("数据来源: maimai")
        + "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=860, height=430)
