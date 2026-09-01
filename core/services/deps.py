# -*- coding: utf-8 -*-
"""依赖自检与安装（响应 GitHub issue #1：容器部署依赖安装）。"""

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

REQUIRED_PACKAGES = {
    "aiohttp": "aiohttp>=3.8",
    "playwright": "playwright>=1.40",
    "PIL": "Pillow>=10.0.0",
}


def check_dependencies() -> list[str]:
    """返回缺失的包名列表。"""
    missing: list[str] = []
    for module, _spec in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    return missing


def ensure_dependencies(auto_install: bool = False) -> tuple[bool, str]:
    """检查依赖；auto_install=True 时自动安装。

    Returns:
        (ok, message)
    """
    missing = check_dependencies()
    if not missing:
        return True, "依赖完整"
    if not auto_install:
        return False, (
            "缺少依赖: " + ", ".join(missing)
            + "。请执行 `python install_deps.py` 或参考 README/容器部署章节安装。"
        )
    specs = [REQUIRED_PACKAGES[m] for m in missing]
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *specs],
            timeout=600,
        )
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            timeout=1200,
        )
        return True, "依赖已自动安装"
    except Exception as e:
        logger.exception("自动安装依赖失败")
        return False, f"依赖自动安装失败: {e}"
