# -*- coding: utf-8 -*-
"""本地静态素材内嵌加载。

素材位于插件根目录 ``assets/``（maimai 图标来自 maimai-prober-frontend，MIT，
详见 ``assets/NOTICE``）。渲染时以 base64 data URI 内嵌，保证宿主 html2png
与 Playwright 两种渲染路径都无需网络即可显示。
"""

import base64
import functools
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"

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
