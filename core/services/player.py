# -*- coding: utf-8 -*-
"""统一玩家数据服务层（PlayerQueryService）。

所有查分命令只通过本服务取数，不直接触碰具体来源客户端：

    b50 / my / player  →  绑定的落雪账号优先 → 开发者密钥+好友码 → 水鱼兜底
    heatmap / trend / history / rank / year / collections / comment
                       →  仅落雪（水鱼无此能力），个人 token 或 OAuth

两源共有功能的命令与渲染器只实现一份，本服务负责选源、归一化与失败回退，
避免平行命令导致的重复代码。
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from ..clients.diving_fish import DivingFishApiClient
from ..clients.lxns import LxnsApiClient
from ..constants import DIFF_NAMES
from ..rating import compute_ra
from ..services.lxns_auth import LxnsAuthService
from ..services.diving_fish_auth import DivingFishOAuthService
from ..services.music import MusicService
from ..services.normalize import normalize_lxns_bests, normalize_lxns_score
from ..stores.bindings import BindingStore
from ..util import error_msg, fmt_utc, is_error

_DEV_PERMISSION_MSG = (
    "开发者功能仅限授权 QQ 使用：请联系管理员在 config.toml 的 "
    "[plugin].developer_qq 中加入你的 QQ 号"
)


def _fmt_utc(ts: Any) -> str:
    """UTC ISO 时间转北京时间展示；空值返回空串。"""
    return fmt_utc(ts)


def _is_friend_code(target: str) -> bool:
    return target.isdigit() and len(target) >= 12


def _normalize_source(force: str) -> str:
    """规范化强制数据源标志：返回 "" / "lxns" / "water_fish"。"""

    f = (force or "").strip().lower().lstrip("-")
    if f in ("lxns", "落雪"):
        return "lxns"
    if f in ("df", "water_fish", "diving_fish", "水鱼"):
        return "water_fish"
    return ""


class PlayerQueryService:

    def __init__(
        self,
        df: DivingFishApiClient,
        lxns: LxnsApiClient,
        auth_svc: LxnsAuthService,
        bindings: BindingStore,
        music: MusicService,
        df_oauth: Optional[DivingFishOAuthService] = None,
        game_version: int = 25500,
        df_developer_token: str = "",
        developer_qq: Optional[list] = None,
    ) -> None:
        self._df = df
        self._lxns = lxns
        self._auth_svc = auth_svc
        self._bindings = bindings
        self._music = music
        self._df_oauth = df_oauth
        self._game_version = game_version
        self._df_developer_token = df_developer_token
        self._developer_qq = {str(q) for q in (developer_qq or [])}

    # ---- 开发者权限 ----

    def _developer_allowed(self, user_id: str) -> bool:
        """判断 QQ 是否在开发者白名单内（空名单 = 禁止所有人）。"""

        return bool(self._developer_qq) and str(user_id) in self._developer_qq

    # ---- 源解析 ----

    async def _resolve(
        self, user_id: str, target: str = "", force: str = "",
    ) -> tuple[str, Optional[dict], Optional[dict], str]:
        """解析数据源。

        返回 (source, lxns_auth, df_binding, err)：
        source ∈ ``lxns_user`` / ``lxns_developer`` / ``water_fish``。
        force 为 ``lxns`` / ``water_fish`` 时跳过自动选源，强制使用指定数据源。
        """

        target = (target or "").strip()
        force = _normalize_source(force)

        # 强制水鱼：跳过落雪绑定与开发者分支
        if force == "water_fish":
            df_binding = await self._bindings.get(user_id)
            df_binding_exists = bool(df_binding)
            if self._df_oauth is not None and await self._df_oauth.get_binding(user_id):
                df_binding_exists = True
            if not df_binding_exists and not target:
                return "", None, None, (
                    "强制水鱼查询需要先 /mai bind <Token> 绑定水鱼，"
                    "或执行 /mai df bind 绑定水鱼 OAuth，或直接提供用户名"
                )
            return "water_fish", None, df_binding, ""

        if target and _is_friend_code(target):
            if not self._developer_allowed(user_id):
                return "", None, None, _DEV_PERMISSION_MSG
            dev_auth = self._auth_svc.developer_auth()
            if not dev_auth:
                return "", None, None, (
                    "好友码查询需要管理员在 config.toml 配置 [lxns].enable_developer_api "
                    "与 developer_api_key"
                )
            return "lxns_developer", dev_auth, None, ""

        binding = await self._auth_svc.get_binding(user_id)
        if binding:
            if target:
                return "", None, None, (
                    "已绑定落雪账号；查询他人请使用好友码"
                    "（需管理员配置 [lxns] 开发者密钥）。\n"
                    "或先 /mai lxns unbind 后再按用户名查询水鱼。"
                )
            auth, err = await self._auth_svc.get_auth(user_id)
            if auth is None:
                return "", None, None, err
            return "lxns_user", auth, None, ""
        if force == "lxns":
            return "", None, None, (
                "强制落雪查询需要先绑定落雪账号（/mai lxns bind）"
                "或使用好友码（需管理员配置开发者密钥）"
            )

        df_binding = await self._bindings.get(user_id)
        has_df_oauth = False
        if self._df_oauth is not None:
            has_df_oauth = bool(await self._df_oauth.get_binding(user_id))
        if df_binding or has_df_oauth:
            return "water_fish", None, df_binding, ""

        if target:
            # 水鱼支持用户名/QQ 查询（不要求绑定）
            return "water_fish", None, None, ""
        return "", None, None, (
            "未绑定任何账号。\n"
            "落雪: /mai lxns bind（OAuth）或 /mai lxns bind token <个人API密钥>\n"
            "水鱼: /mai bind <Token>"
        )

    # ---- 玩家信息 ----

    async def get_player(
        self, user_id: str, target: str = "",
    ) -> tuple[bool, dict, str]:
        source, auth, df_binding, err = await self._resolve(user_id, target)
        if not source:
            return False, {}, err
        if source == "lxns_user":
            resp = await self._lxns.get_user_player(auth)
            if is_error(resp):
                return False, {}, error_msg(resp)
            data = resp.get("data") or {}
            return True, {"source": "lxns", "player": data, "username": data.get("name", "")}, ""
        if source == "lxns_developer":
            resp = await self._lxns.get_player(int(target), auth)
            if is_error(resp):
                return False, {}, error_msg(resp)
            data = resp.get("data") or {}
            return True, {"source": "lxns", "player": data, "username": data.get("name", "")}, ""
        # water_fish
        query_target = target or (df_binding or {}).get("username", "")
        if not query_target and self._df_oauth is not None:
            df_oauth_binding = await self._df_oauth.get_binding(user_id)
            query_target = str((df_oauth_binding or {}).get("username", ""))
        df_auth = None
        if not target and self._df_oauth is not None:
            df_auth, _ = await self._df_oauth.get_auth(user_id)
        resp = await self._df.query_player(
            query_target,
            auth=df_auth if df_auth else None,
        )
        if is_error(resp):
            return False, {}, error_msg(resp)
        return True, {
            "source": "water_fish",
            "player": resp,
            "username": resp.get("nickname") or resp.get("username") or query_target,
        }, ""

    # ---- 水鱼互补（定数 / 封面 ID / 成绩上传映射）----

    async def _enrich_with_df(self, records: list[dict]) -> None:
        """用 水鱼曲库 补全落雪成绩的定数（ds）与水鱼歌曲 ID（df_song_id）。

        补全定数后，若落雪未返回 dx_rating（或为 0），按官方系数表回填 RA，
        保证 B50 / my 卡片不出现空的 RA 值。
        """

        for item in records:
            try:
                lid = int(item.get("song_id") or 0)
            except (TypeError, ValueError):
                continue
            if not lid:
                continue
            df_song = await self._music.get_df_song_by_lxns_id(lid)
            if not df_song:
                continue
            item["df_song_id"] = df_song.get("id")
            ds_list = df_song.get("ds") or []
            li = item.get("level_index")
            if isinstance(li, int) and 0 <= li < len(ds_list):
                item["ds"] = ds_list[li]
            if not item.get("title"):
                item["title"] = df_song.get("title", "")
            # 宴会场（utage）成绩的 RA 官方固定为 0，不参与系数表回填
            if str(item.get("type", "")).strip().lower() == "utage":
                continue
            try:
                ra = int(item.get("ra") or 0)
            except (TypeError, ValueError):
                ra = 0
            if ra <= 0:
                ds = item.get("ds")
                ach = item.get("achievements")
                if ds not in (None, "", 0) and ach not in (None, ""):
                    item["ra"] = compute_ra(ds, ach)

    @staticmethod
    def _detect_mask(records: list[dict]) -> bool:
        """启发式判断水鱼查询是否返回了掩码数据。

        水鱼对开启 ``mask`` 的第三方查询返回：``dxScore=0``、
        达成率为按 RA 反推的低精度值。若全部记录 dxScore 均为 0，
        大概率命中了查询掩码。
        """

        if not records:
            return False
        return all(
            isinstance(r, dict) and not r.get("dxScore")
            for r in records
        )

    # ---- B50 ----

    async def _df_b50(
        self, user_id: str, target: str, query_time: str,
    ) -> tuple[bool, dict, str]:
        """水鱼 B50（也作为落雪失败时的兜底）。"""

        df_binding = await self._bindings.get(user_id)
        query_target = target or (df_binding or {}).get("username", "")
        if not query_target and self._df_oauth is not None:
            df_oauth_binding = await self._df_oauth.get_binding(user_id)
            query_target = str((df_oauth_binding or {}).get("username", ""))
        auth = None
        if not target and self._df_oauth is not None:
            auth, _ = await self._df_oauth.get_auth(user_id)
        resp = await self._df.query_player(
            query_target,
            auth=auth if auth else None,
        )
        if is_error(resp):
            status = resp.get("_status", 0)
            msg = error_msg(resp)
            if status == 403:
                return False, {}, f"{query_target} 已设置隐私或未同意用户协议"
            return False, {}, msg
        charts = resp.get("charts", {})
        if not charts or (not charts.get("sd") and not charts.get("dx")):
            return False, {}, f"{query_target} 暂无成绩记录"
        all_records = (charts.get("sd") or []) + (charts.get("dx") or [])
        return True, {
            "source": "water_fish",
            "charts": charts,
            "username": resp.get("username", query_target),
            "nickname": resp.get("nickname", query_target),
            "rating": resp.get("rating", 0),
            "query_time": query_time,
            "version": self._game_version,
            "course_rank": None,
            "class_rank": None,
            "masked": self._detect_mask(all_records),
        }, ""

    async def get_b50(
        self, user_id: str, target: str = "", force: str = "",
    ) -> tuple[bool, dict, str]:
        force = _normalize_source(force)
        source, auth, df_binding, err = await self._resolve(user_id, target, force)
        if not source:
            return False, {}, err
        query_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if source == "lxns_user":
            bests = await self._lxns.get_user_bests(auth)
            if is_error(bests):
                if force != "lxns":
                    fb = await self._df_b50(user_id, target, query_time)
                    if fb[0]:
                        return fb
                return False, {}, f"落雪数据获取失败: {error_msg(bests)}"
            player = await self._lxns.get_user_player(auth)
            if is_error(player):
                if force != "lxns":
                    fb = await self._df_b50(user_id, target, query_time)
                    if fb[0]:
                        return fb
                return False, {}, f"落雪数据获取失败: {error_msg(player)}"
            name = ""
            rating = 0
            avatar_url = ""
            course_rank = None
            class_rank = None
            if not is_error(player) and isinstance(player.get("data"), dict):
                pdata = player["data"]
                name = str(pdata.get("name", ""))
                rating = int(pdata.get("rating") or 0)
                course_rank = pdata.get("course_rank")
                class_rank = pdata.get("class_rank")
                icon = pdata.get("icon")
                if isinstance(icon, dict) and icon.get("id"):
                    avatar_url = LxnsApiClient.get_icon_url(
                        self._lxns.asset_url, int(icon["id"])
                    )
            charts = normalize_lxns_bests(bests.get("data"))
            await self._enrich_with_df(charts.get("sd", []) + charts.get("dx", []))
            return True, {
                "source": "lxns",
                "charts": charts,
                "username": name,
                "nickname": name or "未知玩家",
                "rating": rating,
                "query_time": query_time,
                "avatar_url": avatar_url,
                "version": self._game_version,
                "course_rank": course_rank,
                "class_rank": class_rank,
            }, ""

        if source == "lxns_developer":
            fc = int(target)
            bests = await self._lxns.get_player_bests(fc, auth)
            if is_error(bests):
                return False, {}, error_msg(bests)
            player = await self._lxns.get_player(fc, auth)
            name = ""
            rating = 0
            avatar_url = ""
            course_rank = None
            class_rank = None
            if not is_error(player) and isinstance(player.get("data"), dict):
                pdata = player["data"]
                name = str(pdata.get("name", ""))
                rating = int(pdata.get("rating") or 0)
                course_rank = pdata.get("course_rank")
                class_rank = pdata.get("class_rank")
                icon = pdata.get("icon")
                if isinstance(icon, dict) and icon.get("id"):
                    avatar_url = LxnsApiClient.get_icon_url(
                        self._lxns.asset_url, int(icon["id"])
                    )
            charts = normalize_lxns_bests(bests.get("data"))
            await self._enrich_with_df(charts.get("sd", []) + charts.get("dx", []))
            return True, {
                "source": "lxns",
                "charts": charts,
                "username": name,
                "nickname": name or f"好友码 {fc}",
                "rating": rating,
                "query_time": query_time,
                "avatar_url": avatar_url,
                "version": self._game_version,
                "course_rank": course_rank,
                "class_rank": class_rank,
            }, ""

        return await self._df_b50(user_id, target, query_time)

    # ---- 个人成绩摘要 ----

    async def _df_my(self, user_id: str) -> tuple[bool, dict, str]:
        """水鱼个人成绩（也作为落雪失败时的兜底）。"""

        df_binding = await self._bindings.get(user_id)
        token = str((df_binding or {}).get("import_token", ""))
        auth = None
        if self._df_oauth is not None:
            auth, _ = await self._df_oauth.get_auth(user_id)
        if not token and not auth:
            return False, {}, "水鱼绑定数据异常，请重新 /mai bind"
        resp = await self._df.get_player_records(
            token if not auth else "",
            auth=auth if auth else None,
        )
        if is_error(resp):
            msg = error_msg(resp)
            if resp.get("_status") == 400 and "token" in msg.lower():
                return False, {}, f"Token 已失效: {msg}\n请重新绑定: /mai bind <Token>"
            return False, {}, f"获取数据失败: {msg}"
        return True, {
            "source": "water_fish",
            "username": str(
                resp.get("username", "")
                or (df_binding or {}).get("username", "")
            ),
            "nickname": str(resp.get("nickname", "") or "未设置"),
            "rating": resp.get("rating", 0),
            "additional_rating": resp.get("additional_rating", 0),
            "plate": resp.get("plate", "无"),
            "class_rank": None,
            "star": None,
            "records": resp.get("records", []) if isinstance(resp.get("records"), list) else [],
            "masked": self._detect_mask(
                resp.get("records", []) if isinstance(resp.get("records"), list) else []
            ),
        }, ""

    async def get_my(
        self, user_id: str, force: str = "",
    ) -> tuple[bool, dict, str]:
        force = _normalize_source(force)
        source, auth, df_binding, err = await self._resolve(user_id, force=force)
        if not source:
            return False, {}, err
        if source == "lxns_developer":
            return False, {}, "开发者模式不提供个人成绩统计，请绑定账号或使用 /mai b50 <好友码>"

        if source == "lxns_user":
            player = await self._lxns.get_user_player(auth)
            if is_error(player):
                if force != "lxns":
                    fb = await self._df_my(user_id)
                    if fb[0]:
                        return fb
                return False, {}, f"落雪数据获取失败: {error_msg(player)}"
            pdata = player.get("data") or {}
            scores = await self._lxns.get_user_scores(auth)
            if is_error(scores):
                if force != "lxns":
                    fb = await self._df_my(user_id)
                    if fb[0]:
                        return fb
                return False, {}, f"落雪数据获取失败: {error_msg(scores)}"
            records = [
                n for n in (normalize_lxns_score(s) for s in (scores.get("data") or []))
                if n is not None
            ]
            await self._enrich_with_df(records)
            name = str(pdata.get("name", "") or "未知玩家")
            trophy = pdata.get("trophy") or {}
            return True, {
                "source": "lxns",
                "username": name,
                "nickname": name,
                "rating": int(pdata.get("rating") or 0),
                "additional_rating": int(pdata.get("course_rank") or 0),
                "plate": str(trophy.get("name", "") or "无"),
                "class_rank": pdata.get("class_rank"),
                "star": pdata.get("star"),
                "records": records,
            }, ""

        return await self._df_my(user_id)

    # ---- 落雪独有能力 ----

    async def _resolve_lxns(self, user_id: str, target: str = "") -> tuple[Optional[dict], str]:
        source, auth, _, err = await self._resolve(user_id, target)
        if not source:
            return None, err
        if source == "water_fish":
            return None, "该功能仅落雪数据源可用（水鱼无此能力），请先绑定落雪账号"
        return auth, ""

    async def get_heatmap(
        self, user_id: str, target: str = "",
    ) -> tuple[bool, dict, str]:
        auth, err = await self._resolve_lxns(user_id, target)
        if not auth:
            return False, {}, err
        if target and _is_friend_code(target):
            resp = await self._lxns.get_player_heatmap(int(target), auth)
        else:
            resp = await self._lxns.get_user_heatmap(auth)
        if is_error(resp):
            return False, {}, error_msg(resp)
        return True, {"heatmap": resp.get("data") or {}, "source": "lxns"}, ""

    async def get_trend(
        self, user_id: str, target: str = "", version: int = 25500,
    ) -> tuple[bool, dict, str]:
        auth, err = await self._resolve_lxns(user_id, target)
        if not auth:
            return False, {}, err
        if target and _is_friend_code(target):
            resp = await self._lxns.get_player_trend(int(target), auth, version=version)
        else:
            resp = await self._lxns.get_user_trend(auth, version=version)
        if is_error(resp):
            return False, {}, error_msg(resp)
        return True, {"trend": resp.get("data") or [], "source": "lxns"}, ""

    async def _resolve_song(self, keyword: str) -> tuple[Optional[dict], str]:
        lxns_song, err = await self._music.find_lxns_song(keyword)
        if not lxns_song:
            return None, err
        return lxns_song, ""

    @staticmethod
    def _song_type_for(lxns_song: dict, level_index: int) -> str:
        diffs = lxns_song.get("difficulties") or {}
        utage = diffs.get("utage") or []
        if any(str(d.get("difficulty")) == str(level_index) for d in utage if isinstance(d, dict)):
            return "utage"
        dx = diffs.get("dx") or []
        if any(str(d.get("difficulty")) == str(level_index) for d in dx if isinstance(d, dict)):
            return "dx"
        return "standard"

    async def get_history(
        self, user_id: str, keyword: str,
    ) -> tuple[bool, dict, str]:
        auth, err = await self._resolve_lxns(user_id)
        if not auth:
            return False, {}, err
        lxns_song, err = await self._resolve_song(keyword)
        if not lxns_song:
            return False, {}, err
        sid = int(lxns_song["id"])
        title = str(lxns_song.get("title", ""))

        async def fetch(level_index: int) -> list[dict]:
            song_type = self._song_type_for(lxns_song, level_index)
            resp = await self._lxns.get_user_score_history(
                auth, sid, level_index, song_type,
            )
            if is_error(resp):
                return []
            return resp.get("data") or []

        results = await asyncio.gather(*(fetch(i) for i in range(5)))
        merged: list[dict] = []
        for level_index, recs in enumerate(results):
            for rec in recs:
                item = normalize_lxns_score(rec)
                if item:
                    item["level_index"] = level_index
                    item["level_name"] = DIFF_NAMES[level_index] if 0 <= level_index < 5 else str(level_index)
                    merged.append(item)
        merged.sort(key=lambda x: str(x.get("play_time") or ""), reverse=True)
        return True, {
            "song_id": sid,
            "title": title,
            "history": merged[:50],
            "source": "lxns",
        }, ""

    async def get_ranking(
        self, user_id: str, keyword: str,
    ) -> tuple[bool, dict, str]:
        auth, err = await self._resolve_lxns(user_id)
        if not auth:
            return False, {}, err
        lxns_song, err = await self._resolve_song(keyword)
        if not lxns_song:
            return False, {}, err
        sid = int(lxns_song["id"])
        title = str(lxns_song.get("title", ""))

        async def fetch(level_index: int) -> list[dict]:
            song_type = self._song_type_for(lxns_song, level_index)
            resp = await self._lxns.get_user_score_ranking(
                auth, sid, level_index, song_type,
            )
            if is_error(resp):
                return []
            return resp.get("data") or []

        results = await asyncio.gather(*(fetch(i) for i in range(5)))
        merged: list[dict] = []
        for level_index, recs in enumerate(results):
            for rec in recs:
                if not isinstance(rec, dict):
                    continue
                merged.append({
                    "level_name": DIFF_NAMES[level_index] if 0 <= level_index < 5 else str(level_index),
                    "ranking": rec.get("ranking"),
                    "achievements": rec.get("achievements"),
                    "dx_score": rec.get("dx_score"),
                    "upload_time": _fmt_utc(rec.get("upload_time")),
                })
        return True, {
            "song_id": sid,
            "title": title,
            "ranking": merged[:60],
            "source": "lxns",
        }, ""

    async def get_year_review(
        self, user_id: str, year: int,
    ) -> tuple[bool, dict, str]:
        auth, err = await self._resolve_lxns(user_id)
        if not auth:
            return False, {}, err
        resp = await self._lxns.get_user_year_review(auth, year)
        if is_error(resp):
            return False, {}, error_msg(resp)
        return True, {"year": resp.get("data") or {}, "source": "lxns"}, ""

    async def get_collections(
        self, user_id: str,
    ) -> tuple[bool, dict, str]:
        auth, err = await self._resolve_lxns(user_id)
        if not auth:
            return False, {}, err
        player = await self._lxns.get_user_player(auth)
        if is_error(player):
            return False, {}, error_msg(player)
        pdata = player.get("data") or {}

        async def fetch_list(ctype: str) -> list[dict]:
            resp = await self._lxns.get_user_collection_list(auth, ctype)
            if is_error(resp):
                return []
            data = resp.get("data")
            return data if isinstance(data, list) else []

        lists = await asyncio.gather(
            fetch_list("trophies"),
            fetch_list("icons"),
            fetch_list("plates"),
            fetch_list("frames"),
        )
        return True, {
            "player": pdata,
            "collections": {
                "trophies": lists[0],
                "icons": lists[1],
                "plates": lists[2],
                "frames": lists[3],
            },
            "source": "lxns",
        }, ""

    # ---- 落雪 All Perfect 50（开发者模式）----

    async def get_ap50(
        self, user_id: str, target: str,
    ) -> tuple[bool, dict, str]:
        """按好友码查询落雪 AP50（开发者 API 专属端点）。"""

        target = (target or "").strip()
        if not _is_friend_code(target):
            return False, {}, "用法: /mai lxns ap50 <好友码>（需管理员配置落雪开发者密钥）"
        if not self._developer_allowed(user_id):
            return False, {}, _DEV_PERMISSION_MSG
        dev_auth = self._auth_svc.developer_auth()
        if not dev_auth:
            return False, {}, (
                "好友码查询需要管理员在 config.toml 配置 [lxns].enable_developer_api "
                "与 developer_api_key"
            )
        fc = int(target)
        bests = await self._lxns.get_player_ap_bests(fc, dev_auth)
        if is_error(bests):
            return False, {}, error_msg(bests)
        player = await self._lxns.get_player(fc, dev_auth)
        name = ""
        rating = 0
        avatar_url = ""
        course_rank = None
        class_rank = None
        if not is_error(player) and isinstance(player.get("data"), dict):
            pdata = player["data"]
            name = str(pdata.get("name", ""))
            rating = int(pdata.get("rating") or 0)
            course_rank = pdata.get("course_rank")
            class_rank = pdata.get("class_rank")
            icon = pdata.get("icon")
            if isinstance(icon, dict) and icon.get("id"):
                avatar_url = LxnsApiClient.get_icon_url(
                    self._lxns.asset_url, int(icon["id"])
                )
        charts = normalize_lxns_bests(bests.get("data"))
        await self._enrich_with_df(charts.get("sd", []) + charts.get("dx", []))
        query_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return True, {
            "source": "lxns",
            "charts": charts,
            "username": name,
            "nickname": name or f"好友码 {fc}",
            "rating": rating,
            "query_time": query_time,
            "avatar_url": avatar_url,
            "version": self._game_version,
            "course_rank": course_rank,
            "class_rank": class_rank,
        }, ""

    # ---- 水鱼按版本查询（OAuth / Developer-Token）----

    async def get_plate(
        self, user_id: str, target: str, versions: list[str],
    ) -> tuple[bool, dict, str]:
        """按版本查询水鱼成绩（OAuth 优先，回退 Developer-Token）。"""

        if not versions:
            return False, {}, "请提供至少一个版本代号"
        target = (target or "").strip()
        is_self = not target
        auth = None
        if is_self and self._df_oauth is not None:
            auth, _ = await self._df_oauth.get_auth(user_id)
        if not auth and not self._developer_allowed(user_id):
            return False, {}, _DEV_PERMISSION_MSG
        if not target:
            df_binding = await self._bindings.get(user_id)
            target = str((df_binding or {}).get("username", ""))
            if not target and self._df_oauth is not None:
                df_oauth_binding = await self._df_oauth.get_binding(user_id)
                target = str((df_oauth_binding or {}).get("username", ""))
        if not target:
            return False, {}, (
                "用法: /mai plate <版本代号>\n"
                "版本代号示例: 真 超 檄 橙 暁 桃 櫻 紫 菫 白 雪 輝 舞 熊 華 爽 煌 宙 星 祭 祝 双 宴 鏡 鏡+"
            )
        if auth:
            resp = await self._df.query_plate("", versions, auth=auth)
        else:
            if not self._df_developer_token:
                return False, {}, (
                    "未配置水鱼 Developer-Token，请在 config.toml 的 [server] 段"
                    "填写 developer_token"
                )
            resp = await self._df.query_plate(
                target, versions, self._df_developer_token
            )
        if is_error(resp):
            return False, {}, error_msg(resp)
        verlist = resp.get("verlist", [])
        if not isinstance(verlist, list):
            verlist = []
        return True, {
            "source": "water_fish",
            "username": resp.get("username") or target,
            "versions": list(versions),
            "verlist": verlist,
        }, ""

    # ---- 水鱼 → 落雪 成绩上传 ----

    async def _map_df_records(
        self, records: list[dict],
    ) -> tuple[list[dict], int, list[str]]:
        """把水鱼成绩映射为落雪 Score[]；返回 (mapped, skipped, errors)。"""

        mapped: list[dict] = []
        skipped = 0
        for r in records:
            if not isinstance(r, dict):
                skipped += 1
                continue
            try:
                sid = int(r.get("song_id") or 0)
            except (TypeError, ValueError):
                skipped += 1
                continue
            lxns_song, err = await self._music.find_lxns_song(str(sid))
            if not lxns_song:
                skipped += 1
                continue
            try:
                lxns_id = int(lxns_song["id"])
            except (TypeError, ValueError):
                skipped += 1
                continue
            df_type = str(r.get("type", ""))
            lxns_type = (
                "standard" if df_type == "SD"
                else "dx" if df_type == "DX"
                else df_type or "standard"
            )
            mapped.append({
                "id": lxns_id,
                "song_name": str(lxns_song.get("title") or r.get("title") or ""),
                "level": r.get("level"),
                "level_index": r.get("level_index"),
                "achievements": r.get("achievements"),
                "fc": r.get("fc") or None,
                "fs": r.get("fs") or None,
                "dx_score": r.get("dxScore"),
                "dx_rating": r.get("ra"),
                "rate": r.get("rate"),
                "type": lxns_type,
            })
        return mapped, skipped, []

    async def upload_df_to_lxns(self, user_id: str) -> tuple[bool, dict, str]:
        """把水鱼成绩同步上传到落雪个人账号。

        需要水鱼绑定（数据源）+ 落雪绑定（上传目标，个人 token / OAuth）。
        水鱼无公开上传接口，本功能为单向同步（水鱼 → 落雪）。
        """

        df_binding = await self._bindings.get(user_id)
        lxns_auth, err = await self._auth_svc.get_auth(user_id)
        if not lxns_auth:
            return False, {}, f"未绑定落雪账号（上传目标）：{err}"
        df_auth = None
        if self._df_oauth is not None:
            df_auth, _ = await self._df_oauth.get_auth(user_id)
        if not df_binding and not df_auth:
            return False, {}, "未绑定水鱼账号（数据源），请先 /mai df bind 或 /mai bind <水鱼Token>"
        resp = await self._df.get_player_records(
            str(df_binding.get("import_token", "")) if not df_auth else "",
            auth=df_auth if df_auth else None,
        )
        if is_error(resp):
            return False, {}, f"获取水鱼成绩失败: {error_msg(resp)}"
        records = resp.get("records") if isinstance(resp, dict) else None
        if not isinstance(records, list) or not records:
            return False, {}, "水鱼账号暂无成绩数据"

        mapped, skipped, errors = await self._map_df_records(records)
        if not mapped:
            return False, {}, f"没有可映射到落雪曲库的成绩（共跳过 {skipped} 条）"

        # 保留最高成绩策略：缺失补齐；水鱼更高则覆盖（并保留落雪已有 play_time，
        # 因为水鱼记录不含 play_time）；相同或更低则跳过（成绩不倒退）。
        existing = await self._lxns.get_user_scores(lxns_auth)
        existing_by_key: dict[tuple, dict] = {}
        if not is_error(existing) and isinstance(existing.get("data"), list):
            for s in existing["data"]:
                if isinstance(s, dict):
                    existing_by_key[(s.get("id"), s.get("level_index"), s.get("type"))] = s

        to_upload: list[dict] = []
        new_count = 0
        upgraded_count = 0
        unchanged_count = 0
        for s in mapped:
            key = (s.get("id"), s.get("level_index"), s.get("type"))
            cur = existing_by_key.get(key)
            if cur is None:
                to_upload.append(s)
                new_count += 1
                continue
            try:
                cur_ach = float(cur.get("achievements") or 0)
                new_ach = float(s.get("achievements") or 0)
            except (TypeError, ValueError):
                unchanged_count += 1
                continue
            if new_ach > cur_ach + 0.0001:
                # 更高成绩：覆盖，但保留落雪已有 play_time
                s["play_time"] = cur.get("play_time")
                to_upload.append(s)
                upgraded_count += 1
            else:
                unchanged_count += 1

        uploaded = 0
        chunk_size = 100
        for i in range(0, len(to_upload), chunk_size):
            part = to_upload[i:i + chunk_size]
            resp2 = await self._lxns.upload_user_scores(lxns_auth, part)
            if is_error(resp2):
                errors.append(f"第 {i // chunk_size + 1} 批（{len(part)} 条）上传失败: {error_msg(resp2)}")
                break
            uploaded += len(part)

        return True, {
            "total": len(records),
            "mapped": len(mapped),
            "new": new_count,
            "upgraded": upgraded_count,
            "unchanged": unchanged_count,
            "uploaded": uploaded,
            "skipped": skipped,
            "errors": errors,
        }, ""

    # ---- 落雪 → 水鱼 成绩上传（水鱼 /player/update_records）----

    async def upload_lxns_to_df(
        self, user_id: str, dry_run: bool = False,
    ) -> tuple[bool, dict, str]:
        """把落雪成绩同步上传到水鱼账号（需水鱼绑定 Import-Token）。

        水鱼 ``update_records`` 以 ``title + type + level_index`` 定位成绩
        （不以 song_id 为准），因此先经曲库反查水鱼标题/类型，保证严格匹配；
        采用与 /mai lxns upload 一致的「只升不降」策略。
        ``dry_run=True`` 时只做映射与差异统计，不实际写入。
        """

        df_binding = await self._bindings.get(user_id)
        df_auth = None
        if self._df_oauth is not None:
            df_auth, _ = await self._df_oauth.get_auth(user_id)
        import_token = str(df_binding.get("import_token", ""))
        if not import_token and not df_auth:
            return False, {}, "未绑定水鱼账号（上传目标），请先 /mai df bind 或 /mai bind <水鱼Token>"
        lxns_auth, err = await self._auth_svc.get_auth(user_id)
        if not lxns_auth:
            return False, {}, f"未绑定落雪账号（数据源）：{err}"

        scores = await self._lxns.get_user_scores(lxns_auth)
        if is_error(scores):
            return False, {}, f"获取落雪成绩失败: {error_msg(scores)}"
        lxns_scores = scores.get("data") if isinstance(scores, dict) else None
        if not isinstance(lxns_scores, list) or not lxns_scores:
            return False, {}, "落雪账号暂无成绩数据"

        # 映射为水鱼 update_records 负载（title+type 以水鱼曲库为准）
        mapped: list[dict] = []
        skipped = 0
        for s in lxns_scores:
            if not isinstance(s, dict):
                skipped += 1
                continue
            # 宴会场难度映射不可靠且水鱼端 RA 语义不同，跳过
            if str(s.get("type", "")).strip().lower() == "utage":
                skipped += 1
                continue
            # 无达成率的记录上传到水鱼会被当作 0 分创建，跳过
            if s.get("achievements") in (None, ""):
                skipped += 1
                continue
            try:
                lid = int(s.get("id") or 0)
            except (TypeError, ValueError):
                skipped += 1
                continue
            df_song = await self._music.get_df_song_by_lxns_id(lid)
            if not df_song:
                skipped += 1
                continue
            li = s.get("level_index")
            if not isinstance(li, int) or li < 0:
                skipped += 1
                continue
            mapped.append({
                "title": str(df_song.get("title", "")),
                "type": str(df_song.get("type", "SD")),
                "level_index": li,
                "achievements": s.get("achievements"),
                "fc": s.get("fc") or "",
                "fs": s.get("fs") or "",
                "dxScore": s.get("dx_score") or 0,
            })
        if not mapped:
            return False, {}, f"没有可映射到水鱼曲库的成绩（共跳过 {skipped} 条）"

        # 只升不降：拉取水鱼现有成绩做对比
        existing = await self._df.get_player_records(
            import_token if not df_auth else "",
            auth=df_auth if df_auth else None,
        )
        existing_by_key: dict[tuple, dict] = {}
        if not is_error(existing) and isinstance(existing.get("records"), list):
            for r in existing["records"]:
                if isinstance(r, dict):
                    existing_by_key[(
                        str(r.get("title", "")), str(r.get("type", "")),
                        r.get("level_index"),
                    )] = r

        to_upload: list[dict] = []
        new_count = 0
        upgraded_count = 0
        unchanged_count = 0
        for s in mapped:
            key = (s["title"], s["type"], s["level_index"])
            cur = existing_by_key.get(key)
            try:
                new_ach = float(s.get("achievements") or 0)
            except (TypeError, ValueError):
                unchanged_count += 1
                continue
            if cur is None:
                to_upload.append(s)
                new_count += 1
                continue
            try:
                cur_ach = float(cur.get("achievements") or 0)
            except (TypeError, ValueError):
                cur_ach = 0.0
            if new_ach > cur_ach + 0.0001:
                to_upload.append(s)
                upgraded_count += 1
            else:
                unchanged_count += 1

        uploaded = 0
        errors: list[str] = []
        chunk_size = 100
        if dry_run:
            # 干跑：不调用写接口，仅统计待上传批次
            uploaded = 0
            for i in range(0, len(to_upload), chunk_size):
                errors.append(f"干跑：第 {i // chunk_size + 1} 批（{len(to_upload[i:i + chunk_size])} 条）未写入")
        else:
            for i in range(0, len(to_upload), chunk_size):
                part = to_upload[i:i + chunk_size]
                resp = await self._df.update_records(
                    import_token if not df_auth else "",
                    part,
                    auth=df_auth if df_auth else None,
                )
                if is_error(resp):
                    errors.append(f"第 {i // chunk_size + 1} 批（{len(part)} 条）上传失败: {error_msg(resp)}")
                    break
                uploaded += len(part)

        return True, {
            "total": len(lxns_scores),
            "mapped": len(mapped),
            "new": new_count,
            "upgraded": upgraded_count,
            "unchanged": unchanged_count,
            "planned": len(to_upload),
            "uploaded": uploaded,
            "skipped": skipped,
            "errors": errors,
            "dry_run": dry_run,
        }, ""

    # ---- 水鱼公共数据：热门歌曲 / 排行榜 ----

    async def get_hot_music_top(
        self, limit: int = 10,
    ) -> tuple[bool, list[dict], str]:
        """热门歌曲 TOP N（权重已含新曲/高难度加权，展示时取百分比）。"""

        resp = await self._df.get_hot_music()
        if is_error(resp):
            return False, [], error_msg(resp)
        if not isinstance(resp, dict) or not resp:
            return False, [], "暂无热门歌曲数据"
        weighted: list[tuple[str, float]] = []
        for k, v in resp.items():
            if not v:
                continue
            try:
                weighted.append((str(k), float(v)))
            except (TypeError, ValueError):
                continue
        weighted.sort(key=lambda x: x[1], reverse=True)
        items = weighted[:limit]
        songs = self._music._song_cache or await self._music.get_songs()
        by_id = {
            str(m.get("id")): m
            for m in songs if isinstance(m, dict)
        } if songs else {}
        result: list[dict] = []
        for sid, weight in items:
            music = by_id.get(sid) or {}
            result.append({
                "id": sid,
                "title": str(music.get("title", sid)),
                "type": str(music.get("type", "?")),
                "max_ds": max(music.get("ds", [0])) if music.get("ds") else 0,
                "is_new": bool((music.get("basic_info") or {}).get("is_new")),
                "weight": weight,
            })
        return True, result, ""

    async def get_rating_ranking(
        self, limit: int = 20,
    ) -> tuple[bool, list[dict], str]:
        """DX Rating 排行榜 TOP N（公开数据，服务端未排序需自行排序）。"""

        resp = await self._df.get_rating_ranking()
        if is_error(resp):
            return False, [], error_msg(resp)
        if not isinstance(resp, list):
            return False, [], "排行榜数据异常"
        items: list[dict] = []
        for x in resp:
            if not isinstance(x, dict):
                continue
            try:
                ra = int(x.get("ra") or 0)
            except (TypeError, ValueError):
                continue
            items.append({"username": str(x.get("username", "?")), "ra": ra})
        items.sort(key=lambda x: x["ra"], reverse=True)
        return True, items[:limit], ""

    # ---- 落雪单曲最佳 / 按 QQ 查玩家（开发者模式）----

    async def get_lxns_best(
        self, user_id: str, keyword: str, target_fc: str = "",
    ) -> tuple[bool, dict, str]:
        """单曲所有谱面的最佳成绩；好友码走开发者 API，否则用绑定账号。"""

        lxns_song, err = await self._resolve_song(keyword)
        if not lxns_song:
            return False, {}, err
        sid = int(lxns_song["id"])
        target_fc = (target_fc or "").strip()
        if target_fc:
            if not _is_friend_code(target_fc):
                return False, {}, "好友码格式不正确（应为 12 位以上数字）"
            if not self._developer_allowed(user_id):
                return False, {}, _DEV_PERMISSION_MSG
            dev_auth = self._auth_svc.developer_auth()
            if not dev_auth:
                return False, {}, (
                    "好友码查询需要管理员配置 [lxns].enable_developer_api "
                    "与 developer_api_key"
                )
            resp = await self._lxns.get_player_bests(int(target_fc), dev_auth)
        else:
            auth, aerr = await self._resolve_lxns(user_id)
            if not auth:
                return False, {}, aerr
            resp = await self._lxns.get_user_bests(auth)
        if is_error(resp):
            return False, {}, error_msg(resp)
        charts = normalize_lxns_bests(resp.get("data"))
        rows: list[dict] = []
        for section, is_dx in (("sd", False), ("dx", True)):
            for rec in charts.get(section, []):
                try:
                    rec_sid = int(rec.get("song_id") or 0)
                except (TypeError, ValueError):
                    rec_sid = 0
                if rec_sid != sid:
                    continue
                try:
                    li = int(rec.get("level_index", 0))
                except (TypeError, ValueError):
                    li = -1
                rows.append({
                    "level_name": DIFF_NAMES[li] if 0 <= li < 5 else str(rec.get("level_index", "?")),
                    "type": "DX" if is_dx else "SD",
                    "achievements": rec.get("achievements"),
                    "dx_score": rec.get("dx_score"),
                    "fc": rec.get("fc", ""),
                    "fs": rec.get("fs", ""),
                    "upload_time": _fmt_utc(
                        rec.get("play_time") or rec.get("last_played_time")
                    ),
                })
        return True, {
            "song_id": sid,
            "title": str(lxns_song.get("title", "")),
            "rows": rows,
            "source": "lxns",
        }, ""

    async def get_lxns_player_by_qq(
        self, user_id: str, qq: str,
    ) -> tuple[bool, dict, str]:
        """按 QQ 号查询落雪玩家（开发者 API）。"""

        qq = (qq or "").strip()
        if not qq.isdigit():
            return False, {}, "QQ 号格式不正确"
        if not self._developer_allowed(user_id):
            return False, {}, _DEV_PERMISSION_MSG
        dev_auth = self._auth_svc.developer_auth()
        if not dev_auth:
            return False, {}, (
                "按 QQ 查询需要管理员配置 [lxns].enable_developer_api "
                "与 developer_api_key"
            )
        resp = await self._lxns.get_player_by_qq(qq, dev_auth)
        if is_error(resp):
            if resp.get("_status") == 404:
                return False, {}, (
                    f"QQ {qq} 未绑定落雪玩家（或对方在落雪未公开绑定），"
                    "请确认 QQ 号后重试"
                )
            return False, {}, error_msg(resp)
        data = resp.get("data") or {}
        return True, {
            "source": "lxns",
            "player": data,
            "username": str(data.get("name", "") or f"QQ {qq}"),
        }, ""
