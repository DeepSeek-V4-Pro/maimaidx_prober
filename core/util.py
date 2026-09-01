# -*- coding: utf-8 -*-
"""通用工具函数。"""

import hashlib
import html as _html
from datetime import datetime, timedelta, timezone
from typing import Any


def get_user_id(kwargs: dict) -> str:
    uid = str(kwargs.get("user_id", "") or "")
    if not uid:
        msg = kwargs.get("message")
        if isinstance(msg, dict):
            try:
                uid = str(
                    msg.get("message_info", {})
                    .get("user_info", {})
                    .get("user_id", "")
                    or ""
                )
            except AttributeError:
                pass
    return uid


def stable_user_uid(user_id: str) -> int:
    digest = hashlib.sha256(user_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def fmt_utc(ts: Any) -> str:
    """UTC ISO 时间转北京时间展示；空值返回空串。"""

    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.astimezone(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M"
        )
    except (TypeError, ValueError):
        return str(ts)


def is_error(resp: Any) -> bool:
    return isinstance(resp, dict) and resp.get("_error", False)


def error_msg(resp: dict) -> str:
    return str(resp.get("message", "未知错误"))


def _is_green(result: Any) -> bool:
    return "green" in str(result or "").lower()


def _is_close(result: Any) -> bool:
    r = str(result or "").lower()
    return "amber" in r or "yellow" in r


def _result_marker(result: Any) -> str:
    if _is_green(result):
        return "✓"
    if _is_close(result):
        return "≈"
    return "✗"


def _fmt_number(value: Any) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def format_maidle_test(test: Any) -> str:
    """把水鱼 Maidle 的 test 响应格式化成可读线索。

    响应字段说明（diving-fish /maidle/single）：
    - 每个属性为 {result, value[, greater]}
    - result: "green lighten-1"=与目标相同, "amber lighten-1"=接近, 空=不同
    - greater: bpm/定数/版本的方向标记（猜测值是否高于目标）
    - type: 猜测曲目的类型列表，命中目标的类型标记为绿色
    - tags: 猜测曲目的谱面标签，绿色表示目标也有该标签
    """
    if isinstance(test, bool):
        return "🎯 正确!" if test else "❌ 不正确"
    if not isinstance(test, dict):
        return str(test) if test is not None else ""

    def val_of(key: str) -> Any:
        v = test.get(key)
        return v if isinstance(v, dict) else None

    lines: list[str] = []

    title = val_of("title")
    if title is not None:
        lines.append(f"曲名: {title.get('value', '')}")
    artist = val_of("artist")
    if artist is not None:
        lines.append(f"作者: {artist.get('value', '')}")

    # 类型（standard → SD, dx → DX；绿色 = 目标类型）
    type_list = test.get("type")
    if isinstance(type_list, list):
        parts: list[str] = []
        has_green = False
        for t in type_list:
            if not isinstance(t, dict):
                continue
            raw = str(t.get("value", ""))
            disp = "SD" if raw == "standard" else "DX" if raw == "dx" else raw
            if _is_green(t.get("result")):
                has_green = True
                parts.append(disp + "✓")
            else:
                parts.append(disp)
        if not has_green and parts:
            parts[0] = parts[0] + "✗"
        if parts:
            lines.append("类型: " + " / ".join(parts))

    def cmp_line(label: str, key: str, direction_kind: str = "") -> None:
        v = val_of(key)
        if v is None:
            return
        value = v.get("value")
        if key == "level":
            value = _fmt_number(value)
        elif key == "bpm":
            value = _fmt_number(value)
        line = f"{label}: {value} {_result_marker(v.get('result'))}"
        if direction_kind and not _is_green(v.get("result")):
            greater = v.get("greater")
            if greater is not None:
                if direction_kind == "version":
                    line += "（目标更新）" if not greater else "（目标更旧）"
                else:
                    line += "（目标更高↑）" if not greater else "（目标更低↓）"
        lines.append(line)

    cmp_line("分类", "genre")
    cmp_line("版本", "version", direction_kind="version")
    cmp_line("BPM", "bpm", direction_kind="number")
    cmp_line("定数", "level", direction_kind="number")

    # 谱面标签：绿色 = 目标也有
    tags = test.get("tags")
    if isinstance(tags, list):
        shared = [
            str(t.get("value", ""))
            for t in tags
            if isinstance(t, dict) and _is_green(t.get("result"))
        ]
        lines.append("目标共有标签: " + (", ".join(shared) if shared else "无"))

    if title is not None and _is_green(title.get("result")):
        lines.append("🎉 猜中啦！")
    return "\n".join(lines)


def format_music_summary(music: dict) -> str:
    sid = str(music.get("id", "") or "?")
    title = str(music.get("title", "") or "?")
    tp = str(music.get("type", "") or "?")
    bi = music.get("basic_info", {})
    artist = str(bi.get("artist", "") or "?") if isinstance(bi, dict) else "?"
    version = str(bi.get("from", "") or "?") if isinstance(bi, dict) else "?"
    ds_list = music.get("ds", [])
    max_ds = max(ds_list) if ds_list else 0
    return f"[{tp}] {title} — {artist}  |  ID: {sid}  |  {version}  |  定数: {max_ds}"


def build_difficulty_detail_text(difficulties: dict, level_names: list) -> str:
    lines: list[str] = []
    for cat_key, cat_label in [("standard", "SD"), ("dx", "DX"), ("utage", "宴")]:
        cat_diffs = difficulties.get(cat_key, [])
        if not cat_diffs:
            continue
        for d in cat_diffs:
            if not isinstance(d, dict):
                continue
            diff_idx = d.get("difficulty", 0)
            level_label = level_names[diff_idx] if diff_idx < len(level_names) else "?"
            kanji = d.get("kanji", "")
            designer = d.get("note_designer", "")
            buddy = " [Buddy]" if d.get("is_buddy", False) else ""
            notes = d.get("notes", {})
            note_parts = []
            if isinstance(notes, dict):
                for nk in ("tap", "hold", "slide", "touch", "break"):
                    if notes.get(nk, 0) > 0:
                        note_parts.append(f"{nk[0].upper()}{notes[nk]}")
            note_str = "/".join(note_parts) if note_parts else ""
            line = f"  [{cat_label}] {level_label}{buddy}"
            if kanji:
                line += f" ({kanji})"
            if designer:
                line += f"  谱师: {_html.escape(designer)}"
            if note_str:
                line += f"  Notes: {note_str}"
            lines.append(line)
    return "\n".join(lines)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
