# -*- coding: utf-8 -*-
"""水鱼（diving-fish）OAuth 认证服务。

插件作为公开客户端接入：
  - 设备码绑定（用户打开链接完成授权）；
  - 每个用户保存自己的 access_token / refresh_token；
  - access token 15 分钟，refresh token 30 天且强制轮换；
  - 刷新必须单飞，新 refresh token 先持久化再继续使用。

配置中的 client_secret 不需要；client_id 来自用户自己在水鱼开发者控制台
登记的公开客户端。
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiohttp

from ..clients.diving_fish import DivingFishApiClient
from ..config import ServerConfig
from ..stores.diving_fish_bindings import DivingFishBindingStore

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DivingFishOAuthService:

    DEFAULT_SCOPE = "prober.records.read"
    BINDING_TTL = 600

    def __init__(
        self,
        config: ServerConfig,
        api_client: DivingFishApiClient,
        session: aiohttp.ClientSession,
        store: DivingFishBindingStore,
    ) -> None:
        self._config = config
        self._client = api_client
        self._session = session
        self._store = store
        self._issuer = (config.oauth_issuer or "").rstrip("/")
        self._discovery: dict[str, Any] = {}
        self._discovery_at = 0.0
        self._pending: dict[str, dict[str, Any]] = {}
        self._refresh_tasks: dict[str, asyncio.Task] = {}

    @property
    def enabled(self) -> bool:
        return bool(
            self._config.enable_oauth
            and self._config.oauth_client_id
            and self._issuer
        )

    @property
    def client_id(self) -> str:
        return (self._config.oauth_client_id or "").strip()

    @property
    def scope(self) -> str:
        return (self._config.oauth_scope or "").strip() or self.DEFAULT_SCOPE

    # ---- 发现文档 ----

    async def _discover(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        if self._discovery and now - self._discovery_at < 600:
            return self._discovery
        async with self._session.get(
            f"{self._issuer}/.well-known/openid-configuration",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        self._discovery = data
        self._discovery_at = now
        return data

    # ---- 绑定 ----

    async def start_binding(
        self, user_id: str, binding_label: str = ""
    ) -> tuple[bool, dict[str, Any]]:
        if not self.enabled:
            return False, {"_error": True, "message": (
                "水鱼 OAuth 未启用：请在 config.toml [server] 配置 enable_oauth = true "
                "与 oauth_client_id"
            )}
        try:
            doc = await self._discover()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return False, {"_error": True, "message": "无法连接水鱼授权服务器，请稍后重试"}
        endpoint = doc.get("device_authorization_endpoint", "")
        if not endpoint:
            return False, {"_error": True, "message": "授权服务器未提供设备码端点"}
        form = {
            "client_id": self.client_id,
            "scope": self.scope,
            "binding_label": binding_label or f"QQ {user_id}",
        }
        try:
            async with self._session.post(
                endpoint, data=form, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    return False, self._oauth_error(data, resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False, {"_error": True, "message": "无法连接水鱼授权服务器"}
        device_code = str(data.get("device_code", ""))
        user_code = str(data.get("user_code", ""))
        verification_uri = str(data.get(
            "verification_uri_complete"
            ) or data.get("verification_uri", ""))
        interval = int(data.get("interval") or 5)
        if not device_code or not verification_uri:
            return False, {"_error": True, "message": "设备码响应缺少必要字段"}
        self._pending[user_id] = {
            "device_code": device_code,
            "user_code": user_code,
            "verification_uri": verification_uri,
            "interval": interval,
            "expires_at": datetime.now(timezone.utc)
            + timedelta(seconds=int(data.get("expires_in") or self.BINDING_TTL)),
        }
        return True, {
            "user_code": user_code,
            "verification_uri": verification_uri,
        }

    async def poll_binding(
        self, user_id: str
    ) -> tuple[bool, str]:
        pending = self._pending.get(user_id)
        if not pending:
            return False, "当前没有进行中的水鱼绑定，请先执行 /mai df bind"
        if datetime.now(timezone.utc) > pending["expires_at"]:
            self._pending.pop(user_id, None)
            return False, "绑定请求已过期（10 分钟），请重新执行 /mai df bind"
        try:
            doc = await self._discover()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return False, "无法连接水鱼授权服务器，请稍后重试"
        endpoint = doc.get("token_endpoint", "")
        form = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": pending["device_code"],
            "client_id": self.client_id,
        }
        try:
            async with self._session.post(
                endpoint, data=form, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    error = str(data.get("error", ""))
                    if error == "authorization_pending":
                        return False, "pending"
                    if error == "slow_down":
                        return False, "slow_down"
                    return False, self._oauth_error(data, resp.status).get(
                        "message", error
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False, "无法连接水鱼授权服务器，请稍后重试"

        access_token = str(data.get("access_token", ""))
        refresh_token = str(data.get("refresh_token", ""))
        if not access_token or not refresh_token:
            return False, "设备码轮询成功但未返回 access_token/refresh_token"
        sub = str(data.get("sub", ""))
        probe = await self._client.get_player_records(
            auth={"scheme": "oauth", "token": access_token}
        )
        username = "未知玩家"
        if isinstance(probe, dict) and not probe.get("_error"):
            username = str(probe.get("username") or "未知玩家")
        elif sub:
            username = f"水鱼账号 {sub}"
        expires_in = int(data.get("expires_in") or 900)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        ).isoformat()
        # 拿到令牌后先持久化再返回，避免中途失效
        await self._store.set_oauth(
            user_id,
            username,
            sub,
            access_token,
            refresh_token,
            expires_at,
            scope=str(data.get("scope", self.scope)),
        )
        self._pending.pop(user_id, None)
        return True, username

    async def _fetch_userinfo(self, access_token: str) -> Optional[dict[str, Any]]:
        doc = await self._discover()
        endpoint = doc.get("userinfo_endpoint", "")
        if not endpoint:
            return None
        try:
            async with self._session.get(
                endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None

    @staticmethod
    def _oauth_error(data: Any, status: int) -> dict[str, Any]:
        if isinstance(data, dict):
            return {
                "_error": True,
                "_status": status,
                "message": str(
                    data.get("error_description")
                    or data.get("error")
                    or data.get("message")
                    or data
                ),
            }
        return {"_error": True, "_status": status, "message": str(data)}

    # ---- 令牌获取 ----

    async def get_auth(
        self, user_id: str
    ) -> tuple[Optional[dict[str, str]], str]:
        if not self.enabled:
            return None, "水鱼 OAuth 未启用，请先配置 enable_oauth 与 oauth_client_id"
        binding = await self._store.get(user_id)
        if not binding:
            return None, "未绑定水鱼账号，请先执行 /mai df bind"
        if binding.get("mode") != "oauth":
            return None, "水鱼绑定模式异常，请重新绑定"
        expires_at = binding.get("expires_at", "")
        try:
            expired = datetime.fromisoformat(expires_at) <= (
                datetime.now(timezone.utc) + timedelta(seconds=30)
            )
        except (TypeError, ValueError):
            expired = True
        if not expired:
            token = str(binding.get("access_token", ""))
            return {"scheme": "oauth", "token": token}, ""
        fresh, err = await self._refresh_single_flight(user_id, binding)
        if fresh is None:
            return None, err
        return {"scheme": "oauth", "token": fresh}, ""

    async def _refresh_single_flight(
        self, user_id: str, binding: dict[str, Any]
    ) -> tuple[Optional[str], str]:
        task = self._refresh_tasks.get(user_id)
        if task is None or task.done():
            task = asyncio.create_task(self._do_refresh(user_id, binding))
            self._refresh_tasks[user_id] = task
        try:
            return await task
        except Exception:
            return None, "水鱼令牌刷新失败，请重新绑定"

    async def _do_refresh(
        self, user_id: str, binding: dict[str, Any]
    ) -> tuple[Optional[str], str]:
        refresh_token = str(binding.get("refresh_token", ""))
        if not refresh_token:
            return None, "绑定数据缺少 refresh_token，请重新绑定"
        doc = await self._discover()
        endpoint = doc.get("token_endpoint", "")
        form = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        try:
            async with self._session.post(
                endpoint, data=form, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    err = self._oauth_error(data, resp.status)
                    if resp.status == 401 or "invalid_grant" in str(err.get("message")):
                        return None, "水鱼授权已失效，请重新执行 /mai df bind"
                    return None, str(err.get("message"))
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None, "无法连接水鱼授权服务器，请稍后重试"
        access_token = str(data.get("access_token", ""))
        new_refresh = str(data.get("refresh_token", ""))
        if not access_token or not new_refresh:
            return None, "水鱼刷新响应缺少令牌字段"
        expires_in = int(data.get("expires_in") or 900)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        ).isoformat()
        ok = await self._store.update_tokens(
            user_id, access_token, new_refresh, expires_at
        )
        if not ok:
            return None, "绑定数据已变更，请重新执行 /mai df bind"
        return access_token, ""

    # ---- 绑定管理 ----

    async def unbind(self, user_id: str) -> bool:
        task = self._refresh_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()
        self._pending.pop(user_id, None)
        return await self._store.delete(user_id)

    async def get_binding(self, user_id: str) -> Optional[dict[str, Any]]:
        return await self._store.get(user_id)
