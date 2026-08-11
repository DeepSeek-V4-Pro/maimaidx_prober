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
from zoneinfo import ZoneInfo

from ..clients.diving_fish import DivingFishApiClient
from ..clients.lxns import LxnsApiClient
from ..constants import DIFF_NAMES
from ..services.lxns_auth import LxnsAuthService
from ..services.music import MusicService
from ..services.normalize import normalize_lxns_bests, normalize_lxns_score
from ..stores.bindings import BindingStore
from ..util import error_msg, fmt_utc, is_error

_LOCAL_TZ = ZoneInfo("Asia/Shanghai")


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
        game_version: int = 25500,
    ) -> None:
        self._df = df
        self._lxns = lxns
        self._auth_svc = auth_svc
        self._bindings = bindings
        self._music = music
        self._game_version = game_version

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
            if not df_binding and not target:
                return "", None, None, (
                    "强制水鱼查询需要先 /mai bind <Token> 绑定水鱼，"
                    "或直接提供用户名"
                )
            return "water_fish", None, df_binding, ""

        if target and _is_friend_code(target):
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
        if df_binding:
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
        resp = await self._df.query_player(query_target)
        if is_error(resp):
            return False, {}, error_msg(resp)
        return True, {
            "source": "water_fish",
            "player": resp,
            "username": resp.get("nickname") or resp.get("username") or query_target,
        }, ""

    # ---- 水鱼互补（定数 / 封面 ID / 成绩上传映射）----

    async def _enrich_with_df(self, records: list[dict]) -> None:
        """用 水鱼曲库 补全落雪成绩的定数（ds）与水鱼歌曲 ID（df_song_id）。"""

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

    # ---- B50 ----

    async def _df_b50(
        self, user_id: str, target: str, query_time: str,
    ) -> tuple[bool, dict, str]:
        """水鱼 B50（也作为落雪失败时的兜底）。"""

        df_binding = await self._bindings.get(user_id)
        query_target = target or (df_binding or {}).get("username", "")
        resp = await self._df.query_player(query_target)
        if is_error(resp):
            status = resp.get("_status", 0)
            msg = error_msg(resp)
            if status == 403:
                return False, {}, f"{query_target} 已设置隐私或未同意用户协议"
            return False, {}, msg
        charts = resp.get("charts", {})
        if not charts or (not charts.get("sd") and not charts.get("dx")):
            return False, {}, f"{query_target} 暂无成绩记录"
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
        if not token:
            return False, {}, "水鱼绑定数据异常，请重新 /mai bind"
        resp = await self._df.get_player_records(token)
        if is_error(resp):
            msg = error_msg(resp)
            if resp.get("_status") == 400 and "token" in msg.lower():
                return False, {}, f"Token 已失效: {msg}\n请重新绑定: /mai bind <Token>"
            return False, {}, f"获取数据失败: {msg}"
        return True, {
            "source": "water_fish",
            "username": str(resp.get("username", "") or df_binding.get("username", "")),
            "nickname": str(resp.get("nickname", "") or "未设置"),
            "rating": resp.get("rating", 0),
            "additional_rating": resp.get("additional_rating", 0),
            "plate": resp.get("plate", "无"),
            "class_rank": None,
            "star": None,
            "records": resp.get("records", []) if isinstance(resp.get("records"), list) else [],
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

    # ---- 水鱼 → 落雪 成绩上传 ----

    async def _map_df_records(
        self, records: list[dict],
    ) -> tuple[list[dict], int, list[str]]:
        """把水鱼成绩映射为落雪 Score[]；返回 (mapped, skipped, errors)。"""

        mapped: list[dict] = []
        skipped = 0
        errors: list[str] = []
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
        return mapped, skipped, errors

    async def upload_df_to_lxns(self, user_id: str) -> tuple[bool, dict, str]:
        """把水鱼成绩同步上传到落雪个人账号。

        需要水鱼绑定（数据源）+ 落雪绑定（上传目标，个人 token / OAuth）。
        水鱼无公开上传接口，本功能为单向同步（水鱼 → 落雪）。
        """

        df_binding = await self._bindings.get(user_id)
        if not df_binding:
            return False, {}, "未绑定水鱼账号（数据源），请先 /mai bind <水鱼Token>"
        auth, err = await self._auth_svc.get_auth(user_id)
        if not auth:
            return False, {}, f"未绑定落雪账号（上传目标）：{err}"

        resp = await self._df.get_player_records(str(df_binding.get("import_token", "")))
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
        existing = await self._lxns.get_user_scores(auth)
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
            resp2 = await self._lxns.upload_user_scores(auth, part)
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
