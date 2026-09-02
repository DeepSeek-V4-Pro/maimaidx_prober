# -*- coding: utf-8 -*-
"""lxns（落雪）API 客户端。

v3.0 扩展为三态鉴权客户端：
- 公开端点（曲库/别名/状态），无需认证；
- 开发者端点（好友码查询），``Authorization: <开发者密钥>``；
- 用户端点（个人 API / OAuth），``X-User-Token: <个人密钥>`` 或
  ``Authorization: Bearer <access_token>``。

同时提供 OAuth 2.0 / OIDC 令牌端点（授权链接、授权码换令牌、刷新令牌、
UserInfo、动态注册），以及按实测端点封装的舞萌数据接口。
"""

import asyncio
import base64
import hashlib
import secrets
import urllib.parse
from typing import Any, Optional

import aiohttp


def build_auth(scheme: str, token: str = "") -> dict[str, str]:
    """构造鉴权描述，供客户端方法透传。

    scheme 取值：``user``（个人 API）、``developer``（开发者密钥）、
    ``oauth``（Bearer access_token）。
    """

    return {"scheme": scheme, "token": token}


class LxnsApiClient:

    def __init__(
        self, base_url: str, asset_url: str, timeout: int,
        session: aiohttp.ClientSession,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._asset_url = asset_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session

    # ---- 基础请求 ----

    @staticmethod
    def _error(message: str, status: int = 0) -> dict:
        return {"_error": True, "_status": status, "message": message}

    @staticmethod
    def _is_error(resp: Any) -> bool:
        return isinstance(resp, dict) and resp.get("_error", False)

    @staticmethod
    def _auth_headers(auth: Optional[dict[str, str]]) -> dict[str, str]:
        if not auth:
            return {}
        scheme = str(auth.get("scheme", ""))
        token = str(auth.get("token", ""))
        if scheme == "user":
            return {"X-User-Token": token}
        if scheme == "developer":
            return {"Authorization": token}
        if scheme == "oauth":
            return {"Authorization": f"Bearer {token}"}
        return {}

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
        headers: Optional[dict] = None,
        auth: Optional[dict[str, str]] = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        kw: dict[str, Any] = {"timeout": self._timeout}
        merged = dict(headers or {})
        merged.update(self._auth_headers(auth))
        if merged:
            kw["headers"] = merged
        if params:
            kw["params"] = params
        if json_data is not None:
            kw["json"] = json_data
        try:
            async with self._session.request(method, url, **kw) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    text = await resp.text()
                    return self._error(f"响应不是 JSON: {text[:200]}", resp.status)
                if resp.status >= 400:
                    message = (
                        str(data.get("message") or data.get("error_description")
                           or data.get("error") or data)
                        if isinstance(data, dict) else str(data)
                    )
                    return self._error(message, resp.status)
                return data
        except asyncio.TimeoutError:
            return self._error("请求超时")
        except aiohttp.ClientError as e:
            return self._error(f"网络错误: {e}")
        except Exception as e:
            return self._error(f"未知错误: {e}")

    async def _get(
        self, path: str, params: Optional[dict] = None,
        headers: Optional[dict] = None, auth: Optional[dict[str, str]] = None,
    ) -> dict:
        return await self._request("GET", path, params=params, headers=headers, auth=auth)

    async def _post(
        self, path: str, json_data: Optional[dict] = None,
        headers: Optional[dict] = None, auth: Optional[dict[str, str]] = None,
    ) -> dict:
        return await self._request("POST", path, json_data=json_data, headers=headers, auth=auth)

    # ---- 公开端点 ----

    async def get_song_list(self) -> dict:
        return await self._get("/maimai/song/list")

    async def get_alias_list(self, page: int = 1) -> dict:
        return await self._get("/maimai/alias/list", params={"page": str(page)})

    async def alive_check(self) -> dict:
        return await self._get("/maimai/alias/list", params={"page": "1"})

    @staticmethod
    def get_cover_url(asset_url: str, song_id: int) -> str:
        resource_id = song_id % 10000
        # !webp 为 CDN 变换后缀，可绕过 WAF 挑战页并返回真实图片
        return f"{asset_url.rstrip('/')}/maimai/jacket/{resource_id}.png!webp"

    @staticmethod
    def get_icon_url(asset_url: str, icon_id: int) -> str:
        """玩家头像静态图 URL。

        ``assets.lxns.net`` 对服务端 Python 请求会返回 WAF HTML，
        头像实际走 ``assets2.lxns.net`` 的原始 PNG。
        """
        base = asset_url.rstrip("/")
        if "assets.lxns.net" in base and "assets2.lxns.net" not in base:
            base = base.replace("assets.lxns.net", "assets2.lxns.net")
        return f"{base}/maimai/icon/{int(icon_id)}.png"

    @staticmethod
    def get_collection_url(asset_url: str, collection_type: str, collection_id: int) -> str:
        """收藏品实物图 URL（trophy / icon / plate / frame）。"""

        return (
            f"{asset_url.rstrip('/')}/maimai/{collection_type}/"
            f"{int(collection_id)}.png!webp"
        )

    @property
    def asset_url(self) -> str:
        return self._asset_url

    # ---- OAuth 2.0 / OIDC ----

    @staticmethod
    def build_authorize_url(
        authorize_url: str,
        client_id: str,
        scope: str,
        state: str,
        redirect_uri: str = "",
        code_challenge: str = "",
        nonce: str = "",
    ) -> str:
        """拼接授权链接。

        redirect_uri 留空表示 OOB（无回调）模式；公共客户端应传入
        ``code_challenge``（PKCE S256）。
        """

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": client_id,
            "scope": scope,
            "state": state,
        }
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        if nonce:
            params["nonce"] = nonce
        query = urllib.parse.urlencode(params)
        return f"{authorize_url.rstrip('/')}?{query}"

    @staticmethod
    def generate_pkce() -> tuple[str, str]:
        """生成 PKCE 对（code_verifier, code_challenge）。"""

        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    async def exchange_code(
        self,
        client_id: str,
        code: str,
        redirect_uri: str = "",
        client_secret: str = "",
        code_verifier: str = "",
    ) -> dict:
        """授权码换令牌（POST /oauth/token）。"""

        body: dict[str, Any] = {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": code,
        }
        if redirect_uri:
            body["redirect_uri"] = redirect_uri
        if client_secret:
            body["client_secret"] = client_secret
        if code_verifier:
            body["code_verifier"] = code_verifier
        return await self._post("/oauth/token", json_data=body)

    async def refresh_token(
        self,
        client_id: str,
        refresh_token: str,
        client_secret: str = "",
    ) -> dict:
        """刷新令牌（每次刷新返回新 refresh_token，旧令牌立即失效）。"""

        body: dict[str, Any] = {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if client_secret:
            body["client_secret"] = client_secret
        return await self._post("/oauth/token", json_data=body)

    # ---- 用户端点（个人 API / OAuth）----

    async def get_user_player(self, auth: dict[str, str]) -> dict:
        return await self._get("/user/maimai/player", auth=auth)

    async def get_user_scores(self, auth: dict[str, str]) -> dict:
        return await self._get("/user/maimai/player/scores", auth=auth)

    async def upload_user_scores(
        self, auth: dict[str, str], scores: list[dict],
    ) -> dict:
        """上传成绩到个人账号（个人 API / OAuth）。"""

        return await self._post(
            "/user/maimai/player/scores",
            json_data={"scores": scores},
            auth=auth,
        )

    async def get_user_bests(
        self,
        auth: dict[str, str],
        song_id: Optional[int] = None,
        song_type: str = "",
        level_index: Optional[int] = None,
    ) -> dict:
        """Best 构成；带 song_id 时返回单曲所有谱面成绩。"""

        params: dict[str, str] = {}
        if song_id is not None:
            params["song_id"] = str(song_id)
        if song_type:
            params["song_type"] = song_type
        if level_index is not None:
            params["level_index"] = str(level_index)
        return await self._get(
            "/user/maimai/player/bests", params=params, auth=auth,
        )

    async def get_user_heatmap(self, auth: dict[str, str]) -> dict:
        return await self._get("/user/maimai/player/heatmap", auth=auth)

    async def get_user_trend(
        self, auth: dict[str, str], version: int = 25500,
    ) -> dict:
        return await self._get(
            "/user/maimai/player/trend",
            params={"version": str(version)},
            auth=auth,
        )

    async def get_user_score_history(
        self,
        auth: dict[str, str],
        song_id: int,
        level_index: int,
        song_type: str,
    ) -> dict:
        """单曲游玩历史；song_type 为 standard/dx/utage。"""

        return await self._get(
            "/user/maimai/player/score/history",
            params={
                "song_id": str(song_id),
                "level_index": str(level_index),
                "song_type": song_type,
            },
            auth=auth,
        )

    async def get_user_score_ranking(
        self,
        auth: dict[str, str],
        song_id: int,
        level_index: int,
        song_type: str,
    ) -> dict:
        return await self._get(
            "/user/maimai/player/score/ranking",
            params={
                "song_id": str(song_id),
                "level_index": str(level_index),
                "song_type": song_type,
            },
            auth=auth,
        )

    async def get_user_year_review(
        self, auth: dict[str, str], year: int, agree: bool = True,
    ) -> dict:
        return await self._get(
            f"/user/maimai/player/year-in-review/{year}",
            params={"agree": "true" if agree else "false"},
            auth=auth,
        )

    async def get_user_collection_list(
        self, auth: dict[str, str], collection_type: str,
    ) -> dict:
        """玩家收藏品列表（前端实测路径为复数：
        ``user/maimai/player/trophies|icons|plates|frames``）。"""

        return await self._get(
            f"/user/maimai/player/{collection_type}", auth=auth,
        )

    async def get_user_comment_list(
        self,
        auth: dict[str, str],
        song_id: int,
        song_type: str = "",
        level_index: int = 0,
        page: int = 1,
    ) -> dict:
        """曲目评论列表（OAuth 专属前端接口，实测个人 token 返回 404）。"""

        params: dict[str, str] = {
            "song_id": str(song_id),
            "level_index": str(level_index),
            "page": str(page),
        }
        if song_type:
            params["song_type"] = song_type
        return await self._get(
            "/user/maimai/comment/list",
            params=params,
            auth=auth,
        )

    async def post_user_comment(
        self,
        auth: dict[str, str],
        song_id: int,
        content: str,
        song_type: str = "",
        level_index: int = 0,
        rating: int = 0,
    ) -> dict:
        """发表评论；字段与前端一致（difficulty 即 level_index）。"""

        return await self._post(
            "/user/maimai/comment",
            json_data={
                "song_id": song_id,
                "song_type": song_type,
                "difficulty": level_index,
                "comment": content,
                "rating": rating,
            },
            auth=auth,
        )

    async def like_user_comment(
        self, auth: dict[str, str], comment_id: int, like: bool = True,
    ) -> dict:
        method = "POST" if like else "DELETE"
        return await self._request(
            method, f"/user/maimai/comment/{comment_id}/like", auth=auth,
        )

    # ---- 开发者端点（好友码 + 开发者密钥）----

    async def get_player(
        self, friend_code: int, auth: dict[str, str],
    ) -> dict:
        return await self._get(f"/maimai/player/{friend_code}", auth=auth)

    async def get_player_by_qq(
        self, qq: str, auth: dict[str, str],
    ) -> dict:
        """通过查分器绑定的 QQ 号查询玩家信息（开发者 API）。"""

        return await self._get(f"/maimai/player/qq/{qq}", auth=auth)

    async def get_player_bests(
        self,
        friend_code: int,
        auth: dict[str, str],
        song_id: Optional[int] = None,
        song_name: str = "",
        song_type: str = "",
        level_index: Optional[int] = None,
    ) -> dict:
        """Best 50；带 song_id/song_name 时返回单曲所有谱面成绩。"""

        params: dict[str, str] = {}
        if song_id is not None:
            params["song_id"] = str(song_id)
        if song_name:
            params["song_name"] = song_name
        if song_type:
            params["song_type"] = song_type
        if level_index is not None:
            params["level_index"] = str(level_index)
        return await self._get(
            f"/maimai/player/{friend_code}/bests",
            params=params,
            auth=auth,
        )

    async def get_player_ap_bests(
        self, friend_code: int, auth: dict[str, str],
    ) -> dict:
        """All Perfect 50（开发者 API 专属，响应结构同 Best 50）。"""

        return await self._get(
            f"/maimai/player/{friend_code}/bests/ap", auth=auth,
        )

    async def get_player_heatmap(
        self, friend_code: int, auth: dict[str, str],
    ) -> dict:
        return await self._get(f"/maimai/player/{friend_code}/heatmap", auth=auth)

    async def get_player_trend(
        self, friend_code: int, auth: dict[str, str], version: int = 25500,
    ) -> dict:
        return await self._get(
            f"/maimai/player/{friend_code}/trend",
            params={"version": str(version)},
            auth=auth,
        )
