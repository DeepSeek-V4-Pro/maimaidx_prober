# -*- coding: utf-8 -*-
"""落雪数据 → 水鱼风格数据归一化。

落雪（lxns）成绩字段与水鱼（diving-fish）不同，渲染器（b50/my）按水鱼
字段消费。本模块把 lxns MaimaiScore 转换成渲染器可直接使用的 dict，
并保留落雪特有字段（dx_score/dx_star/dx_rating）供扩展渲染。
"""

from typing import Any, Optional


def normalize_lxns_score(score: Any) -> Optional[dict]:
    """把单条 lxns MaimaiScore 归一化为渲染器字段。"""

    if not isinstance(score, dict):
        return None
    try:
        ra = float(score.get("dx_rating") or 0)
    except (TypeError, ValueError):
        ra = 0.0
    lxns_type = str(score.get("type", "") or "")
    display_type = "DX" if lxns_type == "dx" else ("SD" if lxns_type == "standard" else lxns_type)
    return {
        "song_id": score.get("id"),
        "title": score.get("song_name", ""),
        "level": score.get("level", "?"),
        "level_index": score.get("level_index", 0),
        "achievements": score.get("achievements"),
        "ra": int(ra),
        "rate": score.get("rate", ""),
        "fc": score.get("fc", "") or "",
        "fs": score.get("fs", "") or "",
        "type": display_type,
        "ds": 0,
        "dx_score": score.get("dx_score"),
        "dx_star": score.get("dx_star"),
        "dx_rating": score.get("dx_rating"),
        "play_time": score.get("play_time"),
        "upload_time": score.get("upload_time"),
        "last_played_time": score.get("last_played_time"),
        "source": "lxns",
    }


def normalize_lxns_bests(bests: Any) -> dict[str, list[dict]]:
    """把 lxns Best 50 响应归一化为 {sd: [...], dx: [...]}。"""

    if not isinstance(bests, dict):
        return {"sd": [], "dx": []}
    sd: list[dict] = []
    dx: list[dict] = []
    for rec in bests.get("standard", []) or []:
        item = normalize_lxns_score(rec)
        if item:
            item["type"] = "SD"
            sd.append(item)
    for rec in bests.get("dx", []) or []:
        item = normalize_lxns_score(rec)
        if item:
            item["type"] = "DX"
            dx.append(item)
    return {"sd": sd, "dx": dx}
