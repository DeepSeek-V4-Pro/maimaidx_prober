# -*- coding: utf-8 -*-
"""落雪年度回顾渲染（多维度浅色面板）。"""

import html as _html
from typing import Any

from ..constants import RATE_DISPLAY
from ..services.renderer import HtmlRenderer
from .common import doc, safe_str
from .theme import panel_style


def _top_n(mapping: Any, n: int = 5) -> list[tuple[str, int]]:
    if not isinstance(mapping, dict):
        return []
    items = [
        (str(k), int(v))
        for k, v in mapping.items()
        if isinstance(v, (int, float)) and v > 0
    ]
    items.sort(key=lambda x: x[1], reverse=True)
    return items[:n]


def _kv_list(items: list[tuple[str, int]], fmt: str = "{k}（{v}）") -> str:
    return " · ".join(fmt.format(k=_html.escape(k), v=v) for k, v in items) if items else "暂无"


def _bar_section(
    label: str, mapping: Any, order: list[str] | None = None, limit: int = 12,
) -> str:
    """把 {key: 数量} 渲染成横向条形区块。"""

    if not isinstance(mapping, dict) or not mapping:
        return ""
    items = [(str(k), int(v)) for k, v in mapping.items() if isinstance(v, (int, float)) and v > 0]
    if not items:
        return ""
    if order:
        ordered = []
        for key in order:
            if str(key) in mapping:
                ordered.append((str(key), int(mapping[str(key)])))
        if ordered:
            items = ordered
    items = items[-limit:]
    max_v = max(v for _, v in items) or 1
    rows = "".join(
        '<div class="bar-row">'
        f'<span class="bar-key">{_html.escape(k)}</span>'
        f'<span class="bar-track"><span class="bar-fill" style="width:{v * 100 / max_v:.1f}%"></span></span>'
        f'<span class="bar-val">{v}</span>'
        "</div>"
        for k, v in items
    )
    return (
        f'<div class="p-section">{_html.escape(label)}</div>'
        f'<div class="bars">{rows}</div>'
    )


async def render_year(
    renderer: HtmlRenderer,
    review: dict,
    songs: list[tuple[str, int]] = None,
) -> str:
    year = safe_str(review.get("year"), "?")
    name = safe_str(review.get("player_name"), "玩家")
    uploads = review.get("player_total_uploads") or {}
    total = sum(int(v) for v in uploads.values() if isinstance(v, (int, float)))
    days = review.get("player_upload_days", 0)

    monthly = review.get("player_monthly_uploads") or {}
    top_months = _top_n(monthly, 3)
    top_songs = songs or []
    hourly = _top_n(review.get("player_hourly_uploads") or {}, 3)

    sections = ""
    # 评级 / FC / 难度分布（2025 年及以后数据）
    rate_map = review.get("rate_distribute") or {}
    rate_disp = {
        str(k): v for k, v in rate_map.items()
    }
    rate_key = {
        str(k): RATE_DISPLAY.get(str(k), str(k)) for k in rate_disp
    }
    if rate_disp:
        rate_order = ["D", "C", "B", "BB", "BBB", "A", "AA", "AAA", "S", "S+", "SS", "SS+", "SSS", "SSS+"]
        ordered: list[tuple[str, int]] = []
        for rk in rate_order:
            for k, v in rate_disp.items():
                if rate_key[str(k)] == rk and int(v) > 0:
                    ordered.append((rk, int(v)))
        if ordered:
            sections += _bar_section("评级分布", dict(ordered), limit=14)
    sections += _bar_section("FC / 完成分布", review.get("full_combo_distribute"))
    sections += _bar_section("难度分布", review.get("difficulty_distribute"))

    genres = _top_n(review.get("most_played_genres") or {}, 5)
    bpms = _top_n(review.get("most_played_bpm_ranges") or {}, 5)
    if genres or bpms:
        sections += '<div class="p-section">常玩偏好</div>'
        sections += (
            f'<div class="chip-line"><span class="chip-label">分类</span>'
            f'<span class="chips">{_kv_list(genres)}</span></div>'
            if genres else ""
        )
        sections += (
            f'<div class="chip-line"><span class="chip-label">BPM</span>'
            f'<span class="chips">{_kv_list(bpms)}</span></div>'
            if bpms else ""
        )

    # Rating 成长：年初/年末 Best 构成对比
    growth = review.get("rating_growth")
    growth_html = ""
    if isinstance(growth, dict):
        def _total(bests: Any) -> int:
            if not isinstance(bests, dict):
                return 0
            try:
                return int(bests.get("standard_total") or 0) + int(bests.get("dx_total") or 0)
            except (TypeError, ValueError):
                return 0

        earliest = _total(growth.get("earliest_bests"))
        latest = _total(growth.get("latest_bests"))
        if earliest or latest:
            diff = latest - earliest
            diff_str = f"（+{diff}）" if diff > 0 else f"（{diff}）" if diff < 0 else ""
            growth_html = (
                '<div class="p-section">Rating 成长</div>'
                '<div class="info-card">'
                f'<div class="row"><span class="label">年初</span><span class="value">{earliest}</span></div>'
                f'<div class="row"><span class="label">年末</span><span class="value">{latest} {diff_str}</span></div>'
                "</div>"
            )

    style = (
        ".stat-grid{display:flex;gap:14px;justify-content:center;margin:18px 0;flex-wrap:wrap}"
        ".stat-box{background:#FFFFFF;border-radius:14px;padding:14px 22px;text-align:center;min-width:110px;box-shadow:0 3px 10px rgba(120,80,160,.1)}"
        ".stat-box .s-val{font-size:30px;font-weight:800;color:#7048E8}"
        ".stat-box .s-label{font-size:12px;color:#8B7BA6;margin-top:3px}"
        ".info-card{background:#F7F3FB;border-radius:14px;padding:14px 18px;margin-top:12px}"
        ".info-card .row{font-size:15px;color:#4A3B63;padding:5px 0}"
        ".info-card .row .label{color:#8B7BA6;margin-right:10px}"
        ".bars{margin-top:6px}"
        ".bar-row{display:flex;align-items:center;gap:10px;margin:6px 0}"
        ".bar-key{width:110px;font-size:13px;color:#6B5D8A;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".bar-track{flex:1;height:12px;background:#F0EAF8;border-radius:6px;overflow:hidden}"
        ".bar-fill{height:100%;background:linear-gradient(90deg,#A78BFA,#7048E8);border-radius:6px}"
        ".bar-val{width:40px;font-size:13px;color:#8B7BA6;text-align:right}"
        ".chip-line{display:flex;align-items:flex-start;gap:10px;margin:8px 0;font-size:14px;color:#4A3B63}"
        ".chip-label{flex:none;color:#8B7BA6;width:46px}"
        ".chips{line-height:1.9}"
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">年度回顾 {_html.escape(year)}</div>'
        f'<div class="p-sub">{_html.escape(name)}</div>'
        '<div class="stat-grid">'
        f'<div class="stat-box"><div class="s-val">{total}</div><div class="s-label">总上传</div></div>'
        f'<div class="stat-box"><div class="s-val">{days}</div><div class="s-label">出勤天数</div></div>'
        "</div>"
        '<div class="info-card">'
        f'<div class="row"><span class="label">最活跃月份</span>'
        f'<span>{_kv_list(top_months, "{k}月（{v}次）") if top_months else "暂无"}</span></div>'
        f'<div class="row"><span class="label">打得最多</span>'
        f'<span>{_kv_list(top_songs[:5]) if top_songs else "暂无"}</span></div>'
        f'<div class="row"><span class="label">最常时段</span>'
        f'<span>{_kv_list(hourly, "{k}点（{v}次）") if hourly else "暂无"}</span></div>'
        "</div>"
        + sections
        + growth_html
        + '<div class="p-footer">'
        '<span class="footer-source">数据来源: maimai · 落雪</span>'
        '<span class="footer-mai">MaiBot</span></div>'
        "</div>"
    )
    estimated = 460 + (sections.count("p-section") + (1 if growth_html else 0)) * 90 + len(top_songs) * 0
    return await renderer.render(doc(panel_style(style), body), width=860, height=max(460, estimated))
