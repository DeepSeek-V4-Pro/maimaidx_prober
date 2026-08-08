# -*- coding: utf-8 -*-
"""MaiMai DX 查分器插件主类。

v2.0 采用模块化架构：命令层（mixin）、服务层、渲染层、客户端、存储分离，
本文件只负责组装与生命周期管理。
"""

import asyncio
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import aiohttp
from maibot_sdk import MaiBotPlugin

from .clients.diving_fish import DivingFishApiClient
from .clients.lxns import LxnsApiClient
from .commands import (
    BasicCommandsMixin,
    MaidleCommandsMixin,
    ScoreCommandsMixin,
)
from .config import MaiMaiDXConfig
from .services import (
    CoverService,
    HtmlRenderer,
    MaidleManager,
    MusicService,
    check_dependencies,
    ensure_dependencies,
)
from .stores import AliasStore, BindingStore

logger = logging.getLogger(__name__)


class MaiMaiDXPlugin(
    BasicCommandsMixin,
    ScoreCommandsMixin,
    MaidleCommandsMixin,
    MaiBotPlugin,
):
    config_model = MaiMaiDXConfig

    async def on_load(self) -> None:
        # ---- 依赖自检（issue #1：容器部署依赖安装） ----
        missing = check_dependencies()
        if missing:
            ok, msg = ensure_dependencies(self.config.plugin.auto_install_deps)
            logger.warning("依赖自检: %s (%s)", msg, ", ".join(missing))

        base = Path(__file__).resolve().parent.parent
        self._aliases = AliasStore(str(base / "aliases.json"))
        await self._aliases.load()
        self._bindings = BindingStore(str(base / "bindings.json"))
        await self._bindings.load()

        self._stream_users: OrderedDict[str, str] = OrderedDict()
        self._stream_users_lock = asyncio.Lock()

        # 客户端与共享会话（懒初始化）
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._df: Optional[DivingFishApiClient] = None
        self._lxns: Optional[LxnsApiClient] = None
        self._client_lock = asyncio.Lock()

        # 服务
        self._renderer = HtmlRenderer(
            ctx_provider=lambda: self.ctx,
            device_scale_factor=self.config.render.device_scale_factor,
            image_timeout_ms=self.config.render.image_timeout_ms,
            browser_executable=self.config.render.browser_executable,
            headless=self.config.render.headless,
            no_sandbox=self.config.render.no_sandbox,
        )
        self._music: Optional[MusicService] = None
        self._covers: Optional[CoverService] = None
        self._maidle = MaidleManager()
        self._maidle.start()

    async def on_unload(self) -> None:
        await self._maidle.stop()
        await self._renderer.close()

        if self._http_session:
            await self._http_session.close()
            self._http_session = None
        self._df = None
        self._lxns = None
        self._music = None
        self._covers = None

    async def on_config_update(
        self, scope: str, config_data: dict[str, object], version: str,
    ) -> None:
        if scope == "self":
            await self._renderer.close()
            async with self._client_lock:
                if self._http_session:
                    await self._http_session.close()
                    self._http_session = None
                self._df = None
                self._lxns = None
            self._music = None
            self._covers = None
            self._renderer = HtmlRenderer(
                ctx_provider=lambda: self.ctx,
                device_scale_factor=self.config.render.device_scale_factor,
                image_timeout_ms=self.config.render.image_timeout_ms,
                browser_executable=self.config.render.browser_executable,
                headless=self.config.render.headless,
                no_sandbox=self.config.render.no_sandbox,
            )
        del scope, config_data, version

    # ---- 客户端/服务懒初始化 ----

    async def _ensure_clients(self) -> None:
        if self._df is not None:
            return
        async with self._client_lock:
            if self._df is not None:
                return
            self._http_session = aiohttp.ClientSession()
            self._df = DivingFishApiClient(
                self.config.server.base_url,
                self.config.server.request_timeout,
                self._http_session,
            )
            if self.config.lxns.enable:
                self._lxns = LxnsApiClient(
                    self.config.lxns.base_url,
                    self.config.lxns.asset_url,
                    self.config.lxns.request_timeout,
                    self._http_session,
                )
            else:
                self._lxns = None
            self._music = MusicService(
                self._df,
                self._lxns,
                self._aliases,
                server_ttl=self.config.server.music_cache_ttl,
                lxns_ttl=self.config.lxns.music_cache_ttl,
            )
            self._covers = CoverService(
                self._http_session,
                self._lxns,
                lxns_enabled=self.config.lxns.enable,
            )

def create_plugin() -> MaiMaiDXPlugin:
    return MaiMaiDXPlugin()
