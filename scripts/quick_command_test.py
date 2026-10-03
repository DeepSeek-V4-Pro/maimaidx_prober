#!/usr/bin/env python3
"""快速回归脚本：覆盖插件主要命令背后的服务层与渲染器。

读取部署配置/绑定，调用真实只读 API。不会执行水鱼或落雪的写操作；
水鱼上传命令只跑 dry_run。输出 PASS/FAIL 摘要和保存渲染样本。
"""

import asyncio
import base64
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

import pydantic

# 本脚本不内置任何真实账号或本机路径：运行时通过环境变量注入，
# 请勿把 QQ 号 / 密钥 / 本机路径写进本文件。
ROOT = Path(os.environ.get("MAIBOT_PLUGIN_ROOT", ""))
CONFIG_ROOT = Path(os.environ.get("MAIBOT_CONFIG_ROOT", str(ROOT)))
ONKEY_SP = Path(os.environ.get("MAIBOT_PYTHON_SP", ""))
DATA = Path(os.environ.get("MAIBOT_PLUGIN_DATA", ""))
QQ = os.environ.get("MAIBOT_TEST_QQ", "")

if ROOT and ROOT.is_dir():
    sys.path.insert(0, str(ROOT))
if ONKEY_SP and ONKEY_SP.is_dir():
    sys.path.insert(0, str(ONKEY_SP))


# ---- 最小 maibot_sdk stub，避免依赖部署 Runner 的运行时注入 ----
class _Command:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, fn):
        return fn


class _MaiBotPlugin:
    pass


_sdk = type(sys)("maibot_sdk")
_sdk.Command = _Command
_sdk.Tool = _Command
_sdk.MaiBotPlugin = _MaiBotPlugin
_sdk.PluginConfigBase = pydantic.BaseModel
sys.modules["maibot_sdk"] = _sdk


class FakeRenderer:
    def __init__(self) -> None:
        self.items: list[str] = []

    async def render(self, html: str, **kwargs: Any) -> str:
        self.items.append(html)
        return "ok"


RESULTS: list[tuple[str, bool, str]] = []
OUT_DIR = Path(os.environ.get("MAIBOT_TEST_OUT", "")) or (
    Path(tempfile.gettempdir()) / "maib50_quick_test"
)


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ((" :: " + detail) if detail else ""))


async def expect(name: str, coro, predicate=None):
    try:
        value = await (coro() if callable(coro) else coro)
        ok = predicate(value) if predicate else bool(value)
        detail = ""
        if isinstance(value, tuple):
            if len(value) >= 2:
                ok = bool(value[0]) if predicate is None else predicate(value)
                if len(value) >= 3 and isinstance(value[0], bool) and not value[0]:
                    detail = str(value[2])[:160]
                else:
                    detail = ""
            elif isinstance(value, dict):
                ok = not value.get("_error", False)
                detail = str(value.get("message", ""))[:120]
        record(name, ok, detail)
        return value
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {exc}")
        return None


async def render_check(name: str, coro):
    renderer = FakeRenderer()
    try:
        result = await coro(renderer)
        ok = bool(renderer.items) or (
            isinstance(result, str) and len(result) > 10
        )
        record(name, ok, f"html={len(renderer.items)}")
        if isinstance(result, str) and not renderer.items:
            png = base64.b64decode(result)
            if png.startswith(b"\x89PNG"):
                (OUT_DIR / f"{name}.png").write_bytes(png)
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {exc}")


async def main():
    missing = []
    if not (CONFIG_ROOT / "config.toml").is_file():
        missing.append("MAIBOT_PLUGIN_ROOT（需指向 plugins/maimaidx_prober 目录）")
    if not DATA.is_dir():
        missing.append("MAIBOT_PLUGIN_DATA（需指向 data/plugins/<plugin_id> 目录）")
    if not QQ:
        missing.append("MAIBOT_TEST_QQ（测试用 QQ 号）")
    if missing:
        print("缺少运行所需环境变量（本脚本不内置账号/路径，请勿把真实密钥写入代码）:")
        for item in missing:
            print("  -", item)
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    import aiohttp
    import tomllib

    from core.clients.diving_fish import DivingFishApiClient
    from core.clients.lxns import LxnsApiClient
    from core.config import MaiMaiDXConfig
    from core.services import (
        CoverService,
        DivingFishOAuthService,
        LxnsAuthService,
        MusicService,
        PlayerQueryService,
    )
    from core.stores import (
        AliasStore,
        BindingStore,
        DivingFishBindingStore,
        LxnsBindingStore,
    )
    from core.renderers import (
        render_b50,
        render_best,
        render_charts,
        render_collections,
        render_df_help,
        render_heatmap,
        render_help,
        render_history,
        render_hot,
        render_lxns_help,
        render_lxns_status,
        render_maidle_answer,
        render_maidle_guess,
        render_maidle_help,
        render_my,
        render_pick,
        render_plate,
        render_play_info,
        render_player,
        render_rank,
        render_ranking,
        render_song_detail,
        render_song_info,
        render_status,
        render_today,
        render_trend,
        render_year,
    )

    config = MaiMaiDXConfig()
    raw = tomllib.loads((CONFIG_ROOT / "config.toml").read_text(encoding="utf-8"))
    config.plugin.developer_qq = raw["plugin"].get("developer_qq", [])
    config.server.base_url = raw["server"]["base_url"]
    config.server.request_timeout = raw["server"]["request_timeout"]
    config.server.music_cache_ttl = raw["server"].get("music_cache_ttl", 300)
    config.server.developer_token = raw["server"].get("developer_token", "")
    config.server.enable_oauth = raw["server"].get("enable_oauth", False)
    config.server.oauth_issuer = raw["server"].get(
        "oauth_issuer", "https://auth.diving-fish.com"
    )
    config.server.oauth_client_id = raw["server"].get("oauth_client_id", "")
    config.server.oauth_scope = raw["server"].get(
        "oauth_scope", "prober.records.read"
    )
    config.lxns.enable = raw["lxns"].get("enable", True)
    config.lxns.base_url = raw["lxns"]["base_url"]
    config.lxns.asset_url = raw["lxns"]["asset_url"]
    config.lxns.request_timeout = raw["lxns"]["request_timeout"]
    config.lxns.music_cache_ttl = raw["lxns"].get("music_cache_ttl", 300)
    config.lxns.enable_oauth = raw["lxns"].get("enable_oauth", False)
    config.lxns.oauth_client_id = raw["lxns"].get("oauth_client_id", "")
    config.lxns.oauth_client_secret = raw["lxns"].get("oauth_client_secret", "")
    config.lxns.oauth_authorize_url = raw["lxns"].get("oauth_authorize_url", "")
    config.lxns.oauth_redirect_uri = raw["lxns"].get("oauth_redirect_uri", "")
    config.lxns.oauth_scope = raw["lxns"].get("oauth_scope", "")
    config.lxns.enable_developer_api = raw["lxns"].get("enable_developer_api", False)
    config.lxns.developer_api_key = raw["lxns"].get("developer_api_key", "")
    config.plugin.game_version = raw["plugin"].get("game_version", 25500)

    aliases = AliasStore(str(DATA / "aliases.json"))
    bindings = BindingStore(str(DATA / "bindings.json"))
    lxns_bindings = LxnsBindingStore(str(DATA / "lxns_bindings.json"))
    df_oauth_bindings = DivingFishBindingStore(str(DATA / "df_oauth_bindings.json"))
    await aliases.load()
    await bindings.load()
    await lxns_bindings.load()
    await df_oauth_bindings.load()

    async with aiohttp.ClientSession() as session:
        df_client = DivingFishApiClient(
            config.server.base_url,
            config.server.request_timeout,
            session,
            developer_token=config.server.developer_token,
        )
        lxns_client = LxnsApiClient(
            config.lxns.base_url,
            config.lxns.asset_url,
            config.lxns.request_timeout,
            session,
        )
        lxns_auth = LxnsAuthService(config.lxns, lxns_client, lxns_bindings)
        df_oauth = DivingFishOAuthService(
            config.server, df_client, session, df_oauth_bindings
        )
        music = MusicService(
            df_client,
            lxns_client if config.lxns.enable else None,
            aliases,
            server_ttl=config.server.music_cache_ttl,
            lxns_ttl=config.lxns.music_cache_ttl,
        )
        players = PlayerQueryService(
            df_client,
            lxns_client,
            lxns_auth,
            bindings,
            music,
            df_oauth=df_oauth,
            game_version=config.plugin.game_version,
            df_developer_token=config.server.developer_token,
            developer_qq=config.plugin.developer_qq,
        )
        covers = CoverService(
            session, lxns_client, lxns_enabled=config.lxns.enable
        )

        # ---- 基础服务 ----
        df_auth, df_auth_err = await df_oauth.get_auth(QQ)
        record("df_oauth_get_auth", bool(df_auth), df_auth_err)
        df_auth = df_auth or {}
        df_binding = await bindings.get(QQ) or {}

        await expect(
            "df_oauth_status",
            lambda: df_oauth.get_binding(QQ),
            lambda x: bool(x),
        )
        await expect(
            "df_player_records",
            lambda: df_client.get_player_records(str(df_binding.get("import_token", "")), auth=df_auth),
            lambda x: isinstance(x, dict) and not x.get("_error") and len(x.get("records", [])) > 0,
        )
        await expect(
            "df_b50",
            lambda: players.get_b50(QQ, "", "--df"),
            lambda x: x[0] and (x[1].get("charts", {}).get("sd") or x[1].get("charts", {}).get("dx")),
        )
        b50_data = await players.get_b50(QQ, "", "--df")
        await expect(
            "df_my",
            lambda: players.get_my(QQ, "--df"),
            lambda x: x[0],
        )
        my_data = await players.get_my(QQ, "--df")
        await expect(
            "df_plate",
            lambda: players.get_plate(QQ, "", ["真", "超"]),
            lambda x: x[0],
        )
        plate_data = await players.get_plate(QQ, "", ["真", "超"])
        await expect(
            "df_player",
            lambda: players.get_player(QQ, ""),
            lambda x: x[0],
        )
        player_data = await players.get_player(QQ, "")
        await expect(
            "df_hot",
            lambda: players.get_hot_music_top(10),
            lambda x: x[0],
        )
        hot_data = await players.get_hot_music_top(10)
        await expect(
            "df_ranking",
            lambda: players.get_rating_ranking(10),
            lambda x: x[0],
        )
        ranking_data = await players.get_rating_ranking(10)
        await expect(
            "music_songs",
            lambda: music.get_songs(),
            lambda x: bool(x),
        )
        songs = await music.get_songs()
        await expect(
            "music_chart_stats",
            lambda: music.get_chart_stats(),
            lambda x: bool(x),
        )
        chart_stats = await music.get_chart_stats()
        await expect(
            "music_match_song",
            lambda: music.match_songs("QZKago Requiem"),
            lambda x: bool(x),
        )
        matched = await music.match_songs("QZKago Requiem")
        song = matched[0] if matched else {}
        cover = await covers.get_cover_data_url(str(song.get("id", "0")))
        record("cover_cover", bool(cover), "")
        song_png = await render_song_info(
            song, cover or "", {"genre_name": "测试", "difficulties": {}}
        )
        record("render_song_info_pillow", bool(song_png), f"png={len(song_png)}")
        play_png = await render_play_info(
            song,
            [{
                "music_id": str(song.get("id", "1")),
                "level_index": 3,
                "achievement": 100.5,
                "ra": 300,
                "dxScore": 100,
                "fc": "ap",
                "fs": "fsd",
            }],
            "落雪",
            cover or "",
        )
        record("render_play_info_pillow", bool(play_png), f"png={len(play_png)}")

        # ---- 落雪服务 ----
        lxns_auth_data, lxns_auth_err = await lxns_auth.get_auth(QQ)
        record("lxns_get_auth", bool(lxns_auth_data), lxns_auth_err)
        if lxns_auth_data:
            await expect(
                "lxns_player",
                lambda: lxns_client.get_user_player(lxns_auth_data),
                lambda x: isinstance(x, dict) and not x.get("_error"),
            )
            await expect(
                "lxns_scores",
                lambda: lxns_client.get_user_scores(lxns_auth_data),
                lambda x: isinstance(x, dict) and not x.get("_error"),
            )
            await expect(
                "lxns_bests",
                lambda: lxns_client.get_user_bests(lxns_auth_data),
                lambda x: isinstance(x, dict) and not x.get("_error"),
            )
        await expect(
            "lxns_heatmap",
            lambda: players.get_heatmap(QQ, ""),
            lambda x: x[0],
        )
        heatmap_data = await players.get_heatmap(QQ, "")
        await expect(
            "lxns_trend",
            lambda: players.get_trend(QQ, ""),
            lambda x: x[0],
        )
        trend_data = await players.get_trend(QQ, "")
        await expect(
            "lxns_history",
            lambda: players.get_history(QQ, "QZKago Requiem"),
            lambda x: x[0],
        )
        history_data = await players.get_history(QQ, "QZKago Requiem")
        await expect(
            "lxns_rank",
            lambda: players.get_ranking(QQ, "QZKago Requiem"),
            lambda x: x[0],
        )
        rank_data = await players.get_ranking(QQ, "QZKago Requiem")
        await expect(
            "lxns_year",
            lambda: players.get_year_review(QQ, year=2025),
            lambda x: x[0],
        )
        year_data = await players.get_year_review(QQ, year=2025)
        await expect(
            "lxns_collections",
            lambda: players.get_collections(QQ),
            lambda x: x[0],
        )
        collections_data = await players.get_collections(QQ)
        await expect(
            "lxns_best_song",
            lambda: players.get_lxns_best(QQ, "QZKago Requiem"),
            lambda x: x[0],
        )
        best_data = await players.get_lxns_best(QQ, "QZKago Requiem")
        if best_data[0]:
            best_png = await render_play_info(best_data[1]["song"], best_data[1]["rows"], "落雪", cover or "")
            (OUT_DIR / "single_song_best.png").write_bytes(base64.b64decode(best_png))
            record("render_real_single_song_best", bool(best_png))
        binding = await lxns_bindings.get(QQ)
        fc = str((binding or {}).get("friend_code") or "")
        if fc:
            await expect(
                "lxns_ap50",
                lambda: players.get_ap50(QQ, fc),
                lambda x: x[0],
            )
        else:
            record("lxns_ap50", False, "绑定数据无好友码，跳过")
        await expect(
            "df_upload_dry_run",
            lambda: players.upload_lxns_to_df(QQ, dry_run=True),
            lambda x: x[0],
        )

        await expect(
            "lxns_upload_dry_run",
            lambda: players.upload_df_to_lxns(QQ, dry_run=True),
            lambda x: x[0],
        )
        await expect(
            "lxns_qq_bound_account",
            lambda: players.get_lxns_player_by_qq(QQ, QQ),
            lambda x: x[0],
        )

        # ---- 渲染器 ----
        await render_check("render_help", render_help)
        await render_check("render_df_help", render_df_help)
        await render_check("render_lxns_help", render_lxns_help)
        await render_check("render_maidle_help", render_maidle_help)
        if song:
            extra = await music.enrich_with_lxns(song)
            aliases_song = await aliases.list_aliases(str(song.get("id", "")))
            await render_check(
                "render_song_detail",
                lambda r: render_song_detail(r, song, cover, aliases_song, extra),
            )
        if chart_stats:
            await render_check(
                "render_charts",
                lambda r: render_charts(
                    r, (chart_stats or {}).get("diff_data", {}), len(songs or [])
                ),
            )
        if hot_data[0]:
            await render_check(
                "render_hot", lambda r: render_hot(r, hot_data[1], 10)
            )
        if ranking_data[0]:
            await render_check(
                "render_ranking", lambda r: render_ranking(r, ranking_data[1], 10)
            )
        await render_check(
            "render_status",
            lambda r: render_status(
                r,
                [
                    ("diving-fish", True, "ok"),
                    ("lxns", True, "ok"),
                ],
            ),
        )
        if song:
            await render_check(
                "render_today",
                lambda r: render_today(
                    r, 12929, ["测试"], ["测试"], song, cover, "test"
                ),
            )
        await render_check(
            "render_pick",
            lambda r: render_pick(r, ["A", "B", "C"], "B", "test"),
        )
        if my_data[0]:
            await render_check(
                "render_my",
                lambda r: render_my(
                    r,
                    my_data[1]["username"],
                    my_data[1]["nickname"],
                    my_data[1]["rating"],
                    my_data[1]["additional_rating"],
                    my_data[1]["plate"],
                    my_data[1]["records"],
                ),
            )
        if plate_data[0]:
            await render_check(
                "render_plate",
                lambda r: render_plate(
                    r, plate_data[1]["username"], plate_data[1]["versions"],
                    plate_data[1]["verlist"],
                ),
            )
        if player_data[0]:
            await render_check(
                "render_player",
                lambda r: render_player(
                    r, player_data[1]["player"], player_data[1]["username"],
                    player_data[1].get("source", ""),
                ),
            )
        await render_check(
            "render_lxns_status",
            lambda r: render_lxns_status(
                r, binding, True, True, QQ in config.plugin.developer_qq
            ),
        )
        if heatmap_data[0]:
            await render_check(
                "render_heatmap",
                lambda r: render_heatmap(r, heatmap_data[1].get("heatmap", {}), "玩家"),
            )
        if trend_data[0]:
            await render_check(
                "render_trend",
                lambda r: render_trend(r, trend_data[1].get("trend", []), "玩家"),
            )
        if history_data[0]:
            await render_check(
                "render_history",
                lambda r: render_history(r, "QZKago Requiem", history_data[1]["history"]),
            )
        if rank_data[0]:
            await render_check(
                "render_rank",
                lambda r: render_rank(r, "QZKago Requiem", rank_data[1]["ranking"]),
            )
        if year_data[0]:
            await render_check(
                "render_year", lambda r: render_year(r, year_data[1].get("year", {}))
            )
        if collections_data[0]:
            await render_check(
                "render_collections",
                lambda r: render_collections(r, collections_data[1]["player"], collections_data[1].get("collections", {})),
            )
        if best_data[0]:
            await render_check(
                "render_best",
                lambda r: render_best(r, "QZKago Requiem", best_data[1]["rows"]),
            )
        if b50_data[0]:
            await render_check(
                "render_b50",
                lambda r: render_b50(
                    r,
                    b50_data[1]["charts"],
                    b50_data[1]["username"],
                    b50_data[1]["nickname"],
                    b50_data[1]["rating"],
                    source=b50_data[1].get("source", ""),
                ),
            )
        await render_check(
            "render_maidle_guess",
            lambda r: render_maidle_guess(r, 1, {"type": "test"}),
        )
        await render_check(
            "render_maidle_answer",
            lambda r: render_maidle_answer(r, "test", "test", "1", cover),
        )

        # ---- 输出摘要 ----
        passed = sum(1 for _, ok, _ in RESULTS if ok)
        failed = sum(1 for _, ok, _ in RESULTS if not ok)
        print(f"\nSUMMARY: {passed} passed, {failed} failed, total {len(RESULTS)}")
        (OUT_DIR / "quick_command_summary.json").write_text(
            json.dumps(
                [{"name": n, "ok": ok, "detail": d} for n, ok, d in RESULTS],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"REPORT: {OUT_DIR / 'quick_command_summary.json'}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
