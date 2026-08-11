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
    LxnsCommandsMixin,
    MaidleCommandsMixin,
    ScoreCommandsMixin,
)
from .config import MaiMaiDXConfig
from .services import (
    CoverService,
    HtmlRenderer,
    LxnsAuthService,
    MaidleManager,
    MusicService,
    PlayerQueryService,
    check_dependencies,
    ensure_dependencies,
)
from .stores import AliasStore, BindingStore, LxnsBindingStore

logger = logging.getLogger(__name__)


class MaiMaiDXPlugin(
    BasicCommandsMixin,
    LxnsCommandsMixin,
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
        data_dir = self.ctx.paths.data_dir

        # ---- 数据目录迁移（v3.0）：旧插件目录 → data/plugins/<plugin_id>/ ----
        aliases_path = data_dir / "aliases.json"
        bindings_path = data_dir / "bindings.json"
        old_aliases = base / "aliases.json"
        old_bindings = base / "bindings.json"
        if old_aliases.exists() and not aliases_path.exists():
            tmp = AliasStore(str(old_aliases))
            await tmp.load()
            await AliasStore(str(aliases_path)).replace_all(await tmp.all())
            logger.info("已迁移 aliases.json 到数据目录 %s", data_dir)
        if old_bindings.exists() and not bindings_path.exists():
            tmp = BindingStore(str(old_bindings))
            await tmp.load()
            await BindingStore(str(bindings_path)).replace_all(await tmp.all())
            logger.info("已迁移 bindings.json 到数据目录 %s", data_dir)

        self._aliases = AliasStore(str(aliases_path))
        await self._aliases.load()
        self._bindings = BindingStore(str(bindings_path))
        await self._bindings.load()
        self._lxns_bindings = LxnsBindingStore(str(data_dir / "lxns_bindings.json"))
        await self._lxns_bindings.load()

        self._stream_users: OrderedDict[str, str] = OrderedDict()
        self._stream_users_lock = asyncio.Lock()

        # 客户端与共享会话（懒初始化）
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._df: Optional[DivingFishApiClient] = None
        self._lxns: Optional[LxnsApiClient] = None
        self._lxns_auth: Optional[LxnsAuthService] = None
        self._players: Optional[PlayerQueryService] = None
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
        self._lxns_auth = None
        self._players = None
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
            self._lxns_auth = None
            self._players = None
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
            self._lxns = LxnsApiClient(
                self.config.lxns.base_url,
                self.config.lxns.asset_url,
                self.config.lxns.request_timeout,
                self._http_session,
            )
            self._lxns_auth = LxnsAuthService(
                self.config.lxns,
                self._lxns,
                self._lxns_bindings,
            )
            self._music = MusicService(
                self._df,
                self._lxns if self.config.lxns.enable else None,
                self._aliases,
                server_ttl=self.config.server.music_cache_ttl,
                lxns_ttl=self.config.lxns.music_cache_ttl,
            )
            self._players = PlayerQueryService(
                self._df,
                self._lxns,
                self._lxns_auth,
                self._bindings,
                self._music,
                game_version=getattr(self.config.plugin, "game_version", 25500),
            )
            self._covers = CoverService(
                self._http_session,
                self._lxns,
                lxns_enabled=self.config.lxns.enable,
            )

def create_plugin() -> MaiMaiDXPlugin:
    return MaiMaiDXPlugin()
