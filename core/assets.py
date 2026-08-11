# -*- coding: utf-8 -*-
"""游戏本体素材（maimai / CHUNITHM 官方图标）内嵌加载。

素材位于插件根目录 ``assets/``（来自 maimai-prober-frontend，MIT，
详见 ``assets/NOTICE``）。渲染时以 base64 data URI 内嵌，保证图片在
宿主 html2png 与 Playwright 两种渲染路径下都无需网络即可显示。
"""

import base64
import functools
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"

MAIMAI_RATE_KEYS = {
    "d", "c", "b", "bb", "bbb",
    "a", "aa", "aaa", "s", "sp", "ss", "ssp", "sss", "sssp",
}
MAIMAI_MEDAL_KEYS = {
    "fc", "fcp", "ap", "app",
    "fs", "fsp", "fsd", "fsdp", "sync", "blank",
}
CHUNITHM_RANK_KEYS = MAIMAI_RATE_KEYS

_MIME = {
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".wav": "audio/wav",
}


@functools.lru_cache(maxsize=512)
def data_uri(rel: str) -> str:
    """返回 ``assets/<rel>`` 的 data URI；文件缺失时返回空字符串。"""
    path = ASSETS_ROOT / rel
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        logger.warning("素材缺失: assets/%s", rel)
        return ""
    mime = _MIME.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def maimai_rank(rate: str) -> str:
    """maimai 评级徽章 data URI（d~sssp）。"""
    key = (rate or "").strip().lower() or "d"
    if key not in MAIMAI_RATE_KEYS:
        return ""
    return data_uri(f"maimai/music_rank/{key}.webp")


def maimai_icon(name: str) -> str:
    """maimai 圆形奖牌 data URI（fc/fcp/ap/app/fs/…/sync/blank）。"""
    key = (name or "").strip().lower()
    if key not in MAIMAI_MEDAL_KEYS:
        return ""
    return data_uri(f"maimai/music_icon/{key}.webp")


def chunithm_rank(rank: str, small: bool = False) -> str:
    """CHUNITHM 评级徽章 data URI；small=True 取小尺寸（_s）。"""
    key = (rank or "").strip().lower() or "d"
    if key not in CHUNITHM_RANK_KEYS:
        return ""
    suffix = "_s" if small else ""
    return data_uri(f"chunithm/music_rank/{key}{suffix}.webp")
