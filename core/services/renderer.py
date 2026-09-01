# -*- coding: utf-8 -*-
"""HTML → PNG 渲染器。

v2.0 渲染链路：
1. 优先调用 MaiBot 宿主提供的 ``render.html2png`` 能力
   （宿主统一管理 Chromium、并发与 --no-sandbox 等参数，容器部署更可靠）；
2. 宿主能力不可用时回退到插件内置 Playwright（懒加载单例浏览器）。

所有渲染默认使用 2x 设备像素比输出高清图片。
"""

import asyncio
import base64
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class HtmlRenderer:

    def __init__(
        self,
        ctx_provider: Callable[[], Any],
        device_scale_factor: float = 2.0,
        image_timeout_ms: int = 15000,
        browser_executable: str = "",
        headless: bool = True,
        no_sandbox: bool = True,
    ) -> None:
        self._ctx_provider = ctx_provider
        self._device_scale_factor = device_scale_factor
        self._image_timeout_ms = image_timeout_ms
        self._browser_executable = browser_executable
        self._headless = headless
        self._no_sandbox = no_sandbox

        self._playwright_inst = None
        self._browser = None
        self._browser_lock = asyncio.Lock()

    # ---- 生命周期 ----

    async def close(self) -> None:
        async with self._browser_lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    logger.debug("关闭 browser 时出错", exc_info=True)
                self._browser = None
            if self._playwright_inst:
                try:
                    await self._playwright_inst.stop()
                except Exception:
                    logger.debug("关闭 playwright 时出错", exc_info=True)
                self._playwright_inst = None

    # ---- 渲染 ----

    async def render(
        self,
        html: str,
        width: int = 680,
        height: int = 500,
        wait_images: bool = False,
        image_timeout: int = 0,
        allow_network: bool = False,
        strict_images: bool = True,
    ) -> str:
        """渲染 HTML 并返回 PNG base64。"""
        image_timeout = image_timeout or self._image_timeout_ms
        try:
            result = await self._render_via_host(
                html, width, height, allow_network,
                wait_for_timeout_ms=(
                    min(image_timeout, 3000) if wait_images else 800
                ),
            )
            if result:
                return result
        except Exception as e:
            logger.debug("宿主渲染能力不可用，回退 Playwright: %s", e)
        return await self._render_via_playwright(
            html, width, height, wait_images, image_timeout, strict_images,
        )

    async def _render_via_host(
        self,
        html: str,
        width: int,
        height: int,
        allow_network: bool,
        wait_for_timeout_ms: int = 800,
    ) -> Optional[str]:
        ctx = self._ctx_provider()
        result = await ctx.render.html2png(
            html,
            selector="body",
            viewport={"width": width, "height": height},
            device_scale_factor=self._device_scale_factor,
            full_page=True,
            wait_until="load",
            wait_for_timeout_ms=wait_for_timeout_ms,
            allow_network=allow_network,
        )
        if isinstance(result, dict):
            b64 = result.get("image_base64") or ""
        else:
            b64 = getattr(result, "image_base64", "") or ""
        return b64 or None

    async def _ensure_browser(self):
        if self._browser is None:
            async with self._browser_lock:
                if self._browser is None:
                    try:
                        from playwright.async_api import async_playwright
                    except ImportError:
                        raise RuntimeError(
                            "playwright 未安装，请执行: python install_deps.py "
                            "（或 pip install playwright && python -m playwright install chromium）"
                        )
                    self._playwright_inst = await async_playwright().start()
                    launch_args: dict[str, Any] = {
                        "headless": self._headless,
                    }
                    if self._browser_executable:
                        launch_args["executable_path"] = self._browser_executable
                    args: list[str] = []
                    if self._no_sandbox:
                        args += ["--no-sandbox", "--disable-setuid-sandbox"]
                    if args:
                        launch_args["args"] = args
                    self._browser = await self._playwright_inst.chromium.launch(
                        **launch_args
                    )
        return self._browser

    async def _render_via_playwright(
        self,
        html: str,
        width: int,
        height: int,
        wait_images: bool,
        image_timeout: int,
        strict_images: bool,
    ) -> str:
        browser = await self._ensure_browser()
        page = await browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=self._device_scale_factor,
        )
        try:
            await page.set_content(html)
            await page.wait_for_load_state("domcontentloaded")
            if wait_images:
                expr = (
                    "() => [...document.querySelectorAll('img')]"
                    ".every(i => i.complete && i.naturalWidth > 0)"
                    if strict_images
                    else "() => [...document.querySelectorAll('img')].every(i => i.complete)"
                )
                try:
                    await page.wait_for_function(expr, timeout=image_timeout)
                except Exception:
                    logger.debug("等待封面图片加载超时或失败，继续渲染")
            await page.wait_for_timeout(500)
            shot = await page.screenshot(full_page=True, type="png")
        finally:
            await page.close()
        return base64.b64encode(shot).decode()
