# -*- coding: utf-8 -*-
"""热门歌曲渲染（水鱼 /hot_music，浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from .common import doc, footer_bar
from .theme import panel_style


async def render_hot(
    renderer: HtmlRenderer,
    items: list[dict],
    limit: int,
) -> str:
    rows = []
    for i, item in enumerate(items, 1):
        pct = item.get("weight", 0) * 100
        new_tag = '<span class="new">新曲</span>' if item.get("is_new") else ""
        rows.append(
            '<tr>'
            f'<td class="td-rank">#{i}</td>'
            f'<td class="td-title">{_html.escape(str(item.get("title", "?")))}'
            f' {new_tag}</td>'
            f'<td class="td-type">{_html.escape(str(item.get("type", "?")))}</td>'
            f'<td class="td-ds">{_html.escape(str(item.get("max_ds", "-")))}</td>'
            f'<td class="td-w"><div class="bar"><span style="width:{min(pct * 20, 100):.1f}%"></span></div>'
            f'<span class="wv">{pct:.2f}%</span></td>'
            "</tr>"
        )
    style = (
        ".table{width:100%;border-collapse:collapse;margin-top:12px}"
        ".table th{font-size:12px;color:#8B7BA6;padding:6px 10px;text-align:left;border-bottom:2px solid #EFE6F7}"
        ".table td{font-size:14px;color:#4A3B63;padding:7px 10px;border-bottom:1px solid #F3EEF8;vertical-align:middle}"
        ".td-rank{width:48px;color:#A78BFA;font-weight:800}"
        ".td-title{max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".td-type{width:60px;color:#7048E8;font-weight:700}"
        ".td-ds{width:64px;color:#C77D3A;font-weight:600}"
        ".td-w{display:flex;align-items:center;gap:10px}"
        ".td-w .bar{flex:1;height:10px;background:#F0EAF8;border-radius:5px;overflow:hidden;min-width:120px}"
        ".td-w .bar span{display:block;height:100%;background:linear-gradient(90deg,#A78BFA,#7048E8);border-radius:5px}"
        ".td-w .wv{width:54px;font-size:12px;color:#8B7BA6;text-align:right}"
        ".new{font-size:11px;color:#FFFFFF;background:#F472B6;border-radius:6px;padding:1px 6px;margin-left:6px;font-weight:700}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">热门歌曲</div>'
        f'<div class="p-sub">diving-fish 统计 · TOP {limit}（新曲/高难度加权）</div>'
        '<table class="table"><tr><th>#</th><th>曲目</th><th>类型</th><th>最高定数</th><th>热度</th></tr>'
        + "".join(rows)
        + "</table>"
        + footer_bar("数据来源: maimai · diving-fish")
        + "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=820, height=240 + len(rows) * 38)
