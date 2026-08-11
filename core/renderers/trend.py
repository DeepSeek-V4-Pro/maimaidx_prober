# -*- coding: utf-8 -*-
"""DX Rating 趋势渲染（横向条形图）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from .common import doc, footer_bar, safe_str
from .theme import panel_style


async def render_trend(
    renderer: HtmlRenderer,
    trend: list[dict],
    username: str,
    query_time: str = "",
) -> str:
    """trend 为 ``[{date, total, standard, dx}]`` 数组（按日期升序）。"""

    items = [t for t in trend if isinstance(t, dict)]
    items.sort(key=lambda t: str(t.get("date", "")))
    items = items[-30:]
    if not items:
        body = (
            '<div class="panel">'
            f'<div class="p-title">{_html.escape(safe_str(username, "玩家"))} 的 DX Rating 趋势</div>'
            '<div class="p-sub">暂无趋势数据（可能需要在新版本爬取后生成）</div>'
            + footer_bar("数据来源: maimai", query_time or "MaiBot")
            + "</div>"
        )
        return await renderer.render(doc(panel_style(), body), width=680, height=240)

    max_total = max(int(t.get("total") or 0) for t in items) or 1
    rows: list[str] = []
    for t in reversed(items):
        date = str(t.get("date", ""))[:10]
        total = int(t.get("total") or 0)
        standard = int(t.get("standard") or 0)
        dx = int(t.get("dx") or 0)
        width = max(4, int(total * 100 / max_total))
        rows.append(
            '<div class="row">'
            f'<div class="date">{_html.escape(date)}</div>'
            f'<div class="bar-wrap"><div class="bar" style="width:{width}%"></div></div>'
            f'<div class="val">{total}</div>'
            f'<div class="detail">SD {standard} · DX {dx}</div>'
            "</div>"
        )

    style = (
        ".row{display:grid;grid-template-columns:96px 1fr 72px 110px;align-items:center;gap:12px;margin:10px 0}"
        ".date{font-size:16px;color:#6B5D8A;text-align:right}"
        ".bar-wrap{background:#F0EAF8;border-radius:8px;height:18px;overflow:hidden}"
        ".bar{height:100%;background:linear-gradient(90deg,#A78BFA,#7048E8);border-radius:8px}"
        ".val{font-size:17px;color:#7048E8;font-weight:800}"
        ".detail{font-size:14px;color:#8B7BA6}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">{_html.escape(safe_str(username, "玩家"))} 的 DX Rating 趋势</div>'
        f'<div class="p-sub">最近 {len(items)} 条 · 最高 {max_total}</div>'
        + "".join(rows)
        + footer_bar("数据来源: maimai", query_time or "MaiBot")
        + "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=760, height=320 + len(items) * 40)
