# -*- coding: utf-8 -*-
"""落雪（lxns）认证服务。

职责：
- OAuth 授权链接生成（state + PKCE）、授权码换令牌、令牌单飞刷新；
- 个人 API 密钥绑定（校验后可存）；
- 为命令层提供可直接使用的鉴权描述（``LxnsApiClient`` 透传）。

安全约定：令牌只存本地 JSON，日志一律脱敏；授权 state 仅内存保留 10 分钟；
刷新令牌 30 天轮换，刷新失败时命令层提示重新绑定。
"""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..clients.lxns import LxnsApiClient, build_auth
from ..config import LxnsServerConfig
from ..stores.lxns_bindings import LxnsBindingStore
from ..util import error_msg, is_error

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LxnsAuthService:

    OAUTH_SCOPE = "read_player write_player read_user_profile"
    """插件需要的落雪权限（不申请 openid 等登录身份权限，保持最小化）。"""
    OOB_REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
    """无回调（OOB）模式使用的标准回调标识，必须与授权链接/兑换请求一致。"""

    def __init__(
        self,
        config: LxnsServerConfig,
        client: LxnsApiClient,
        store: LxnsBindingStore,
    ) -> None:
        self._config = config
        self._client = client
        self._store = store
        self._pending: dict[str, dict[str, Any]] = {}
        self._refresh_tasks: dict[str, asyncio.Task] = {}

    # ---- 能力开关 ----

    @property
    def oauth_enabled(self) -> bool:
        return bool(self._config.enable_oauth and self._config.oauth_client_id)

    @property
    def developer_enabled(self) -> bool:
        return bool(self._config.enable_developer_api and self._config.developer_api_key)

    def developer_auth(self) -> Optional[dict[str, str]]:
        if not self.developer_enabled:
            return None
        return build_auth("developer", self._config.developer_api_key)

    # ---- OAuth 绑定 ----

    async def create_authorize_url(self, user_id: str) -> tuple[bool, str]:
        """生成 OAuth 授权链接并记录 pending 状态。"""

        if not self.oauth_enabled:
            return False, "落雪 OAuth 未启用：请在 config.toml 配置 [lxns].enable_oauth 与 oauth_client_id"
        state = secrets.token_urlsafe(24)
        redirect_uri = self._config.oauth_redirect_uri.strip() or self.OOB_REDIRECT_URI
        scope = self._config.oauth_scope.strip() or self.OAUTH_SCOPE
        # 机密客户端（配置了 client_secret）走纯密钥模式；公共客户端才用 PKCE
        use_pkce = not bool(self._config.oauth_client_secret.strip())
        verifier, challenge = (
            LxnsApiClient.generate_pkce() if use_pkce else ("", "")
        )
        self._pending[user_id] = {
            "state": state,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        }
        url = LxnsApiClient.build_authorize_url(
            self._config.oauth_authorize_url,
            self._config.oauth_client_id,
            scope,
            state,
            redirect_uri=redirect_uri,
            code_challenge=challenge,
        )
        return True, url

    async def complete_oauth_bind(
        self, user_id: str, code: str, state: str,
    ) -> tuple[bool, str]:
        """用授权码完成绑定；成功后返回 (True, 玩家名)。"""

        pending = self._pending.pop(user_id, None)
        if not pending:
            return False, "未找到待完成的授权请求，请重新执行 /mai lxns bind"
        if state and pending.get("state") != state:
            return False, "授权 state 校验失败，请重新执行 /mai lxns bind"
        if datetime.now(timezone.utc) > pending["expires_at"]:
            return False, "授权请求已过期（10 分钟），请重新执行 /mai lxns bind"

        resp = await self._client.exchange_code(
            self._config.oauth_client_id,
            code,
            redirect_uri=pending["redirect_uri"],
            client_secret=self._config.oauth_client_secret.strip(),
            code_verifier=pending["code_verifier"],
        )
        if is_error(resp):
            return False, f"令牌换取失败: {error_msg(resp)}"

        access_token = str(resp.get("access_token", ""))
        refresh_token = str(resp.get("refresh_token", ""))
        expires_in = int(resp.get("expires_in") or 900)
        if not access_token or not refresh_token:
            return False, "令牌响应缺少 access_token/refresh_token"
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        ).isoformat()

        ok, info = await self._probe_and_save_oauth(
            user_id, access_token, refresh_token, expires_at,
            scope=str(resp.get("scope", "")),
        )
        return ok, info

    async def _probe_and_save_oauth(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: str,
        scope: str,
    ) -> tuple[bool, str]:
        auth = build_auth("oauth", access_token)
        player = await self._client.get_user_player(auth)
        if is_error(player):
            return False, f"无法读取玩家信息: {error_msg(player)}"
        data = player.get("data") if isinstance(player, dict) else None
        if not isinstance(data, dict):
            return False, "玩家信息响应结构异常"
        username = str(data.get("name", "未知玩家"))
        friend_code = data.get("friend_code")
        await self._store.set_oauth(
            user_id, username,
            int(friend_code) if isinstance(friend_code, int) else None,
            access_token, refresh_token, expires_at, scope=scope,
        )
        return True, username

    # ---- 个人 API 密钥绑定 ----

    async def bind_personal_token(
        self, user_id: str, token: str,
    ) -> tuple[bool, str]:
        """绑定个人 API 密钥；先调玩家接口校验有效性。"""

        token = token.strip()
        auth = build_auth("user", token)
        player = await self._client.get_user_player(auth)
        if is_error(player):
            status = player.get("_status", 0)
            if status == 401:
                return False, "个人 API 密钥无效或已失效，请在落雪查分器重新生成"
            return False, f"无法读取玩家信息: {error_msg(player)}"
        data = player.get("data") if isinstance(player, dict) else None
        if not isinstance(data, dict):
            return False, "玩家信息响应结构异常"
        username = str(data.get("name", "未知玩家"))
        friend_code = data.get("friend_code")
        await self._store.set_personal_token(
            user_id, username,
            int(friend_code) if isinstance(friend_code, int) else None,
            token,
        )
        return True, username

    # ---- 绑定管理 ----

    async def unbind(self, user_id: str) -> bool:
        task = self._refresh_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()
        self._pending.pop(user_id, None)
        return await self._store.delete(user_id)

    async def get_binding(self, user_id: str) -> Optional[dict[str, Any]]:
        return await self._store.get(user_id)

    async def get_auth(self, user_id: str) -> tuple[Optional[dict[str, str]], str]:
        """返回可用于客户端请求的鉴权描述；OAuth 过期时自动单飞刷新。

        返回值 (auth, err)：auth 为 None 时 err 说明原因。
        """

        binding = await self._store.get(user_id)
        if not binding:
            return None, "未绑定落雪账号，请先执行 /mai lxns bind"
        mode = binding.get("mode")
        if mode == "personal_token":
            token = str(binding.get("personal_token", ""))
            if not token:
                return None, "绑定数据异常（缺少个人密钥），请重新绑定"
            return build_auth("user", token), ""

        if mode != "oauth":
            return None, f"未知绑定模式: {mode}，请重新绑定"

        expires_at = binding.get("expires_at", "")
        try:
            expired = datetime.fromisoformat(expires_at) <= (
                datetime.now(timezone.utc) + timedelta(seconds=30)
            )
        except (TypeError, ValueError):
            expired = True
        if not expired:
            return build_auth("oauth", str(binding.get("access_token", ""))), ""

        fresh, err = await self._refresh_single_flight(user_id, binding)
        if fresh is None:
            return None, err
        return build_auth("oauth", fresh), ""

    async def _refresh_single_flight(
        self, user_id: str, binding: dict[str, Any],
    ) -> tuple[Optional[str], str]:
        task = self._refresh_tasks.get(user_id)
        if task is None or task.done():
            task = asyncio.create_task(self._do_refresh(user_id, binding))
            self._refresh_tasks[user_id] = task
        try:
            return await task
        except Exception as e:
            logger.warning("落雪令牌刷新任务异常: %s", e)
            return None, "令牌刷新失败，请重新绑定"

    async def _do_refresh(
        self, user_id: str, binding: dict[str, Any],
    ) -> tuple[Optional[str], str]:
        refresh_token = str(binding.get("refresh_token", ""))
        if not refresh_token:
            return None, "绑定数据缺少 refresh_token，请重新绑定"
        resp = await self._client.refresh_token(
            self._config.oauth_client_id,
            refresh_token,
            client_secret=self._config.oauth_client_secret.strip(),
        )
        if is_error(resp):
            status = resp.get("_status", 0)
            if status == 401 or "invalid_grant" in str(error_msg(resp)):
                return None, "授权已失效（刷新令牌过期），请重新执行 /mai lxns bind"
            return None, f"令牌刷新失败: {error_msg(resp)}"
        access_token = str(resp.get("access_token", ""))
        new_refresh = str(resp.get("refresh_token", ""))
        if not access_token or not new_refresh:
            return None, "刷新响应缺少令牌字段"
        expires_in = int(resp.get("expires_in") or 900)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        ).isoformat()
        ok = await self._store.update_tokens(
            user_id, access_token, new_refresh, expires_at,
        )
        if not ok:
            return None, "绑定数据已变更，请重新执行 /mai lxns bind"
        return access_token, ""
