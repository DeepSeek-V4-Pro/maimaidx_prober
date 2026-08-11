# -*- coding: utf-8 -*-
"""上传热力图渲染（GitHub 风格色阶日历）。"""

import html as _html
from datetime import datetime, timedelta, timezone
from typing import Any

from ..services.renderer import HtmlRenderer
from .common import doc, footer_bar, safe_str
from .theme import panel_style


def _heat_color(count: int) -> str:
    if count <= 0:
        return "#EFEAF5"
    if count < 10:
        return "#B7E0C8"
    if count < 30:
        return "#7CC9A0"
    if count < 60:
        return "#3FAE6D"
    return "#1F8A4E"


async def render_heatmap(
    renderer: HtmlRenderer,
    heatmap: dict[str, Any],
    username: str,
    rating: int = 0,
    query_time: str = "",
) -> str:
    """heatmap 为 ``YYYY-MM-DD -> 数量`` 映射。"""

    counts: dict[str, int] = {}
    total = 0
    max_day = 0
    for day, value in (heatmap or {}).items():
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        counts[str(day)] = count
        total += count
        max_day = max(max_day, count)

    # 以最近 84 天为窗口铺格子，缺失日补零
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=83)
    cells: list[str] = []
    for offset in range(84):
        day = start + timedelta(days=offset)
        key = day.isoformat()
        count = counts.get(key, 0)
        color = _heat_color(count)
        title = f"{key}: {count}" if count else key
        cells.append(
            f'<div class="cell" style="background:{color}" title="{_html.escape(title)}"></div>'
        )

    style = (
        ".grid{display:grid;grid-template-columns:repeat(12,1fr);gap:8px;margin-top:20px}"
        ".cell{aspect-ratio:1;border-radius:6px;border:1px solid rgba(120,80,160,.08)}"
        ".legend{display:flex;align-items:center;gap:8px;justify-content:flex-end;margin-top:16px;font-size:14px;color:#8B7BA6}"
        ".legend .sw{width:16px;height:16px;border-radius:3px}"
    )
    legend = (
        '<div class="legend">'
        "少"
        f'<span class="sw" style="background:{_heat_color(0)}"></span>'
        f'<span class="sw" style="background:{_heat_color(5)}"></span>'
        f'<span class="sw" style="background:{_heat_color(20)}"></span>'
        f'<span class="sw" style="background:{_heat_color(45)}"></span>'
        f'<span class="sw" style="background:{_heat_color(70)}"></span>'
        "多</div>"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">{_html.escape(safe_str(username, "玩家"))} 的上传热力图</div>'
        f'<div class="p-sub">最近 84 天 · 共 {total} 次上传'
        + (f" · 单日最高 {max_day}" if max_day else "")
        + "</div>"
        f'<div class="grid">{"".join(cells)}</div>'
        + legend
        + footer_bar("数据来源: maimai", query_time or "MaiBot")
        + "</div>"
    )
    return await renderer.render(
        doc(panel_style(style), body),
        width=760,
        height=340,
    )
