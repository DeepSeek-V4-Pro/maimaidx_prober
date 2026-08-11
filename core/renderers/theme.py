# -*- coding: utf-8 -*-
"""B50 官方版式设计系统（配色 / 字体 / 组件）。

以 maimai DX 官方 B50 印刷效果图为基准复刻（LxBot 生成图风格）：
- 马卡龙渐变背景 + 薄荷绿成绩区；
- 青绿分区条（BEST 35 / BEST 15）；
- 难度配色成绩卡片（文字居左、曲绘居右、右下编号框）；
- 圆润无衬线字体栈（离线渲染依赖系统字体回退）。
"""

import html as _html
import functools
from typing import Any

from ..assets import data_uri
from ..constants import DEFAULT_GAME_VERSION, GAME_VERSION_KEYS

FONT_STACK = (
    "'Varela Round','M PLUS Rounded 1c','Yu Gothic UI','Yu Gothic',"
    "'Noto Sans SC','Microsoft YaHei UI','Microsoft JhengHei UI',sans-serif"
)

# 舞萌难度配色：基色 / 深色 / 文字色
# 0=Basic 绿, 1=Advanced 橙, 2=Expert 红, 3=Master 紫,
# 4=Re:Master 淡白, 5=UTAGE 粉
DIFF_COLORS = [
    ((34, 187, 91), (14, 117, 54), (255, 255, 255)),
    ((251, 156, 45), (213, 117, 12), (255, 255, 255)),
    ((246, 72, 97), (188, 38, 52), (255, 255, 255)),
    ((158, 69, 226), (111, 24, 173), (255, 255, 255)),
    ((237, 232, 247), (154, 141, 192), (74, 59, 99)),
    ((234, 61, 232), (204, 12, 175), (255, 255, 255)),
]
DIFF_NAMES = ["Basic", "Advanced", "Expert", "Master", "Re:Master", "UTAGE"]

# DX Rating 分档配色（参照官方前端 getDeluxeRatingGradient 的渐变映射）
RATING_TIERS = [
    (0, "#4DABF7", "#4DABF7"),      # <1000 浅蓝
    (1000, "#228BE6", "#228BE6"),   # <2000 蓝
    (2000, "#82C91E", "#40C057"),   # <4000 黄绿
    (4000, "#FAB005", "#FD7E14"),   # <7000 黄橙
    (7000, "#F783AC", "#FA5252"),   # <10000 红
    (10000, "#BE4BDB", "#7048E8"),  # <12000 紫
    (12000, "#CD853F", "#A0522D"),  # <13000 棕
    (13000, "#4DABF7", "#228BE6"),  # <14000 浅蓝
    (14000, "#FCC419", "#F59F00"),  # <14500 金
    (14500, "#F0E68C", "#DAA520"),  # <15000 黄绿(卡其→金)
    (15000, "#7048E8", "#15AABF"),  # >=15000 彩虹紫青
]


def rating_tier_colors(rating: Any) -> tuple[str, str]:
    try:
        r = int(rating)
    except (TypeError, ValueError):
        r = 0
    colors = RATING_TIERS[0]
    for min_r, f_hex, t_hex in RATING_TIERS:
        if r >= min_r:
            colors = (f_hex, t_hex)
        else:
            break
    return colors


COLORS = {
    "page_top": "#E9E6F8",       # 页面顶部淡薰衣草
    "page_mid": "#F8E4F6",       # 页面中部淡粉紫
    "page_low": "#F6F1EF",       # 页面下部过渡
    "section_bg": "#EBFFF4",     # 成绩区薄荷绿
    "bar": "#2FD6B8",            # 分区条青绿
    "bar_hi": "#A9F3E6",         # 分区条高光
    "card_text": "#FFFFFF",
    "header_bg": "#FFF6D8",      # 头部浅黄
    "header_border": "#FFD54F",  # 头部描边
    "rating_strip": "#A4B5FD",   # DX Rating 蓝色条
    "footer_wave": "#02E4D9",    # 页脚青波
    "text_dark": "#4A3B63",
    "text_muted": "#8B7BA6",
}


@functools.lru_cache(maxsize=1)
def font_face_css() -> str:
    """内嵌圆体拉丁字体（Varela Round，SIL OFL 1.1，见 assets/fonts/OFL.txt）。"""
    uri = data_uri("fonts/VarelaRound-Regular.ttf")
    if not uri:
        return ""
    return (
        "@font-face{font-family:'Varela Round';"
        f"src:url({uri}) format('truetype');"
        "font-weight:400;font-style:normal;}"
    )


def _diff_css() -> str:
    """按难度生成卡片底色 / 封面渐变 / 编号框 / 类型标签的 CSS。"""
    parts = []
    for i, (base, dark, text) in enumerate(DIFF_COLORS):
        r, g, b = base
        dr, dg, db = dark
        tr, tg, tb = text
        grad = (
            f"linear-gradient(90deg,"
            f"rgba({r},{g},{b},.78) 0%,"
            f"rgba({r},{g},{b},.48) 18%,"
            f"rgba({r},{g},{b},.22) 40%,"
            f"rgba({r},{g},{b},.07) 60%,"
            f"rgba({r},{g},{b},0) 78%)"
        )
        parts.append(
            f".diff-{i}{{background:rgb({r},{g},{b})}}\n"
            f".diff-{i} .card-cover::before{{background:{grad}}}\n"
            f".diff-{i} .card-rank{{background:rgb({dr},{dg},{db})}}\n"
            f".diff-{i} .type-tag{{color:rgb({dr},{dg},{db})}}\n"
            f".diff-{i} .card-title{{color:rgb({tr},{tg},{tb})}}\n"
            f".diff-{i} .card-ach{{color:rgb({tr},{tg},{tb})}}\n"
            f".diff-{i} .card-stats{{color:rgb({tr},{tg},{tb})}}\n"
        )
    # Re:Master 淡白底上的斜纹改为浅灰，保持可见
    parts.append(
        ".diff-4::before{"
        "background:"
        "repeating-linear-gradient(-45deg,rgba(0,0,0,.05) 0 8px,transparent 8px 20px),"
        "repeating-linear-gradient(45deg,rgba(0,0,0,.03) 0 10px,transparent 10px 24px);}"
    )
    return "".join(parts)


def doc(style_extra: str, body: str) -> str:
    """组装 B50 页面文档（无默认深色底，body 由页面样式控制）。"""
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<style>{font_face_css()}html,body{{margin:0;padding:0;font-family:{FONT_STACK}}}"
        + style_extra
        + "</style></head><body>"
        + body
        + "</body></html>"
    )


def page_style() -> str:
    """页面背景（马卡龙渐变 + 装饰点）+ 公共组件样式。"""
    c = COLORS
    bg_uri = data_uri("logo_background.webp")
    bg_layer = f'url("{bg_uri}")' if bg_uri else "none"
    return f"""
body{{
  background:
    radial-gradient(circle at 8% 18%, rgba(255,255,255,.55) 0 34px, transparent 35px),
    radial-gradient(circle at 93% 12%, rgba(255,214,238,.65) 0 26px, transparent 27px),
    radial-gradient(circle at 16% 86%, rgba(180,240,225,.5) 0 22px, transparent 23px),
    radial-gradient(circle at 88% 78%, rgba(214,222,255,.6) 0 30px, transparent 31px),
    linear-gradient(180deg,rgba(233,230,248,.62) 0%,rgba(248,228,246,.52) 34%,rgba(246,241,239,.5) 55%,rgba(235,255,244,.78) 62%),
    {bg_layer};
  background-size:auto,auto,auto,auto,auto,cover;
  background-position:0 0,0 0,0 0,0 0,0 0,center top;
  color:{c['text_dark']};
}}
.page{{padding:26px 54px 0}}
.header{{
  display:flex;align-items:center;gap:22px;position:relative;
  background:{c['header_bg']};border:3px solid {c['header_border']};
  border-radius:22px;padding:18px 26px;box-shadow:0 6px 18px rgba(120,80,160,.18);
}}
.avatar{{
  width:86px;height:86px;border-radius:50%;flex:none;
  background:linear-gradient(135deg,#FFD7EC,#CDE4FF);
  display:flex;align-items:center;justify-content:center;
  font-size:42px;font-weight:800;color:#7A5B8F;border:3px solid #FFFFFF;
  position:relative;overflow:hidden;
}}
.avatar img{{
  position:absolute;inset:0;width:100%;height:100%;
  object-fit:cover;display:block;z-index:2;border-radius:50%;
}}
.avatar .avatar-fallback{{
  display:none;position:absolute;inset:0;z-index:1;
  align-items:center;justify-content:center;
}}
.avatar.no-avatar .avatar-fallback{{display:flex}}
.head-info{{flex:1;min-width:0}}
.name-row{{display:flex;align-items:center;gap:12px}}
.nick-chip{{
  display:inline-flex;align-items:center;justify-content:center;
  background:#FFFFFF;border-radius:14px;height:48px;padding:0 18px;
  min-width:240px;
  color:{c['text_dark']};font-size:24px;font-weight:800;
  letter-spacing:1px;box-shadow:0 3px 8px rgba(120,80,160,.14);
}}
.user{{font-size:15px;color:{c['text_muted']};margin-top:1px}}
.rating-row{{display:flex;align-items:center;gap:12px;margin-top:8px}}
.rating-chip{{
  display:inline-flex;align-items:center;justify-content:center;gap:10px;
  border-radius:14px;height:48px;padding:0 18px;color:#FFFFFF;
  min-width:240px;
  box-shadow:0 3px 10px rgba(120,140,255,.32);
}}
.rating-chip .rating-label{{font-size:16px;font-weight:700;letter-spacing:1px;opacity:.92}}
.rating-chip .rating-val{{font-size:34px;font-weight:800;line-height:1.1}}
.blessing{{font-size:14px;color:#C89B2E;margin-top:4px;font-weight:600}}
.rank-badge-img{{
  width:auto;display:block;flex:none;
  mix-blend-mode:multiply; /* 溶掉段位/阶级素材自带白底 */
}}
.rank-badge-img.class-badge{{height:52px}}
.rank-badge-img.course-badge{{height:38px}}
.version-box{{
  flex:none;padding:0;
}}
.version-box img{{
  height:110px;width:auto;display:block;
}}
.section-band{{background:{c['section_bg']};border-radius:24px;padding:20px 26px;margin:14px 0}}
.section-head{{
  display:flex;align-items:center;justify-content:center;gap:18px;
  background:linear-gradient(90deg,{c['bar']},#63E2C8 50%,{c['bar']});
  border-radius:999px;padding:9px 30px;margin-bottom:16px;
  color:#FFFFFF;font-size:26px;font-weight:800;letter-spacing:6px;
  box-shadow:0 4px 12px rgba(47,214,184,.35);
}}
.section-head .chev{{font-size:22px;opacity:.9;font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}}
.score-card{{
  position:relative;display:flex;border-radius:15px;overflow:hidden;
  min-height:126px;
  box-shadow:0 4px 12px rgba(80,30,120,.22);
}}
.score-card::before{{
  content:"";position:absolute;inset:0;pointer-events:none;
  background:
    repeating-linear-gradient(-45deg,rgba(255,255,255,.09) 0 8px,transparent 8px 20px),
    repeating-linear-gradient(45deg,rgba(255,255,255,.05) 0 10px,transparent 10px 24px);
}}
.score-card.b15::after{{
  content:"";position:absolute;left:0;top:0;bottom:0;width:16px;z-index:2;
  background:repeating-linear-gradient(180deg,rgba(255,255,255,.22) 0 6px,transparent 6px 12px);
  border-right:2px solid rgba(255,255,255,.25);
}}
.card-info{{
  flex:1;min-width:0;padding:10px 14px 10px 16px;position:relative;z-index:2;
  display:flex;flex-direction:column;gap:3px;
}}
.title-row{{display:flex;align-items:center;gap:6px;padding-right:56px}}
.card-title{{
  font-size:16px;font-weight:700;color:rgba(255,255,255,.95);
  flex:1;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}}
.dx-star{{height:20px;width:auto;display:block;flex:none}}
.card-ach{{font-size:22px;font-weight:800;color:#FFFFFF;line-height:1.15}}
.card-stats{{display:flex;gap:12px;font-size:14px;color:{c['card_text']};opacity:.95}}
.card-stats .card-lv{{color:#FFE9A8;font-weight:800}}
.card-time{{font-size:11px;color:{c['card_text']};opacity:.8;margin-top:2px}}
.card-badges{{display:flex;gap:5px;align-items:center;margin-top:auto}}
.badge-rate{{height:32px;width:auto;display:block}}
.badge-medal{{height:30px;width:auto;display:block}}
.card-placeholder{{
  align-items:center;justify-content:center;
  background:rgba(255,255,255,.30);border:2px dashed rgba(120,80,160,.35);
  box-shadow:none;min-height:126px;
}}
.card-placeholder::before{{display:none}}
.card-placeholder .ph-text{{
  width:100%;text-align:center;color:rgba(120,80,160,.55);
  font-size:15px;font-weight:700;letter-spacing:2px;
}}
.type-tag{{
  position:absolute;top:10px;right:10px;z-index:3;
  display:inline-flex;align-items:center;
  background:rgba(255,255,255,.92);border-radius:7px;
  font-size:13px;font-weight:800;padding:1px 8px;
}}
.card-cover{{
  width:38%;position:relative;z-index:1;flex:none;
  background:linear-gradient(135deg,#C99FF0 0%,#E3C6F7 55%,#F6E3FB 100%);
}}
.card-cover::before{{
  content:"";position:absolute;left:0;top:0;bottom:0;width:100%;z-index:2;pointer-events:none;
}}
.card-cover::after{{
  content:"\\266B";position:absolute;inset:0;z-index:0;
  display:flex;align-items:center;justify-content:center;
  font-size:40px;color:rgba(255,255,255,.55);
}}
.card-cover img{{
  width:100%;height:100%;object-fit:cover;display:block;position:relative;z-index:1;
}}
.card-rank{{
  position:absolute;right:10px;bottom:8px;z-index:3;
  color:#FFFFFF;border-radius:9px;
  font-size:15px;font-weight:800;padding:2px 9px;
  box-shadow:0 2px 6px rgba(40,10,80,.35);
}}
{_diff_css()}
.footer{{
  position:relative;margin:18px -54px 0;padding:26px 54px 20px;
  background:
    radial-gradient(circle at 3% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 9% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 15% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 21% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 27% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 33% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 39% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 45% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 51% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 57% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 63% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 69% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 75% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 81% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 87% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 93% 0,{c['footer_wave']} 0 20px,transparent 21px),
    radial-gradient(circle at 99% 0,{c['footer_wave']} 0 20px,transparent 21px),
    linear-gradient(180deg,{c['footer_wave']} 0%,#4FE3D2 100%);
}}
.footer-inner{{
  display:flex;align-items:center;gap:18px;color:#FFFFFF;
  font-size:17px;font-weight:600;text-shadow:0 1px 3px rgba(0,120,110,.35);
}}
.footer-time{{flex:1;text-align:left}}
.footer-src{{flex:1;text-align:right}}
"""


def panel_style(extra: str = "") -> str:
    """B50 同风格浅色面板 CSS（马卡龙背景 + 白色圆角面板 + 共享组件）。

    供 my / song / today / help / heatmap / trend / maidle 等渲染器使用；
    细节装饰后续再逐步完善，先统一字体与配色。
    """

    c = COLORS
    bg_uri = data_uri("logo_background.webp")
    bg_layer = f'url("{bg_uri}")' if bg_uri else "none"
    return f"""
body{{
  background:
    radial-gradient(circle at 7% 12%, rgba(255,255,255,.55) 0 30px, transparent 31px),
    radial-gradient(circle at 93% 9%, rgba(255,214,238,.65) 0 24px, transparent 25px),
    radial-gradient(circle at 12% 88%, rgba(180,240,225,.5) 0 22px, transparent 23px),
    linear-gradient(180deg,rgba(233,230,248,.62) 0%,rgba(248,228,246,.52) 40%,rgba(246,241,239,.5) 64%,rgba(235,255,244,.8) 100%),
    {bg_layer};
  background-size:auto,auto,auto,auto,cover;
  background-position:0 0,0 0,0 0,0 0,center top;
  color:{c['text_dark']};
  padding:34px 42px;
}}
.panel{{background:rgba(255,255,255,.9);border-radius:22px;padding:26px 30px;box-shadow:0 8px 26px rgba(120,80,160,.14)}}
.p-title{{font-size:30px;font-weight:800;color:{c['text_dark']};letter-spacing:2px;text-align:center}}
.p-sub{{font-size:15px;color:{c['text_muted']};text-align:center;margin-top:4px}}
.p-section{{font-size:17px;font-weight:700;color:{c['text_dark']};margin:16px 0 10px;padding-left:10px;border-left:4px solid {c['bar']}}}
.p-card{{background:#FFFFFF;border-radius:14px;padding:12px 16px;box-shadow:0 3px 10px rgba(120,80,160,.1)}}
.p-table{{width:100%;border-collapse:collapse}}
.p-table th{{font-size:12px;color:{c['text_muted']};text-align:left;padding:6px 8px;border-bottom:2px solid #EFE6F7}}
.p-table td{{font-size:14px;color:{c['text_dark']};padding:6px 8px;border-bottom:1px solid #F3EEF8}}
.p-row{{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #F3EEF8;font-size:14px}}
.p-footer{{display:flex;align-items:center;margin-top:16px;padding-top:10px;border-top:1px solid #E9E0F3;font-size:13px;color:{c['text_muted']}}}
.p-footer .footer-source{{flex:1;text-align:left}}
.p-footer .footer-mai{{flex:1;text-align:right}}
/* common.py 帮助/页脚组件兼容 */
.section{{margin-bottom:18px}}
.sec-label{{font-size:17px;font-weight:700;color:{c['text_dark']};margin-bottom:8px;padding-left:10px;border-left:4px solid {c['bar']}}}
.cmd{{display:flex;padding:7px 0}}
.cmd-name{{flex-shrink:0;width:360px;font-size:18px;color:#7A5BC8;font-family:'Consolas','Courier New',monospace}}
.cmd-desc{{font-size:18px;color:#6B5D8A}}
.footer-bar{{display:flex;align-items:center;margin-top:16px;padding-top:10px;border-top:1px solid #E9E0F3;font-size:13px}}
.footer-source{{color:{c['text_muted']};flex:1}}
.footer-mai{{color:#A99BC4;text-align:right}}
""" + extra


def header_html(
    nickname: str,
    username: str,
    rating: int,
    blessing: str = "",
    avatar_url: str = "",
    version: int = DEFAULT_GAME_VERSION,
    course_rank: Any = None,
    class_rank: Any = None,
) -> str:
    initial = (nickname or username or "?").strip()[:1] or "?"
    if avatar_url:
        avatar = (
            f'<img src="{avatar_url}" '
            'onerror="this.style.display=\'none\';'
            'this.parentElement.classList.add(\'no-avatar\')" />'
            f'<span class="avatar-fallback">{_html.escape(initial)}</span>'
        )
        avatar_class = ""
    else:
        avatar = f'<span class="avatar-fallback">{_html.escape(initial)}</span>'
        avatar_class = " no-avatar"
    f_hex, t_hex = rating_tier_colors(rating)
    rating_html = (
        f'<div class="rating-chip" style="background:linear-gradient(90deg,{f_hex},{t_hex})">'
        '<span class="rating-label">DX Rating</span>'
        f'<span class="rating-val">{rating}</span>'
        "</div>"
    )
    version_uri = ""
    try:
        if int(version) in GAME_VERSION_KEYS:
            version_uri = data_uri(f"maimai/version/{int(version)}.webp")
    except (TypeError, ValueError):
        pass
    version_html = (
        f'<div class="version-box"><img src="{version_uri}" /></div>'
        if version_uri
        else ""
    )
    class_badge = ""
    course_badge = ""
    for key, max_v in (("class_rank", 25), ("course_rank", 23)):
        try:
            val = int(locals().get(key))
        except (TypeError, ValueError):
            val = -1
        if 0 <= val <= max_v:
            uri = data_uri(f"maimai/{key}/{val}.webp")
            if uri:
                badge_html = f'<img class="rank-badge-img" src="{uri}" />'
                if key == "class_rank":
                    class_badge = badge_html.replace(
                        'class="rank-badge-img"', 'class="rank-badge-img class-badge"'
                    )
                else:
                    course_badge = badge_html.replace(
                        'class="rank-badge-img"', 'class="rank-badge-img course-badge"'
                    )
    parts = [
        '<div class="header">',
        f'<div class="avatar{avatar_class}">{avatar}</div>',
        '<div class="head-info">',
        '<div class="name-row">',
        f'<span class="nick-chip">{_html.escape(nickname)}</span>',
        class_badge,
        "</div>",
        f'<div class="user">@{_html.escape(username)}</div>',
        '<div class="rating-row">',
        rating_html,
        course_badge,
        "</div>",
    ]
    if blessing:
        parts.append(f'<div class="blessing">{_html.escape(blessing)}</div>')
    parts.extend(
        [
            "</div>",
            "</div>",
        ]
    )
    if version_html:
        parts.insert(-1, version_html)
    return "".join(parts)


def section_html(label: str, cards_html: str) -> str:
    return (
        '<div class="section-band"><div class="section-head">'
        f'<span class="chev">&#8249;</span>{_html.escape(label)}'
        '<span class="chev">&#8250;</span></div>'
        f'<div class="grid">{cards_html}</div></div>'
    )


def score_card_html(
    rank: int,
    *,
    title: str,
    achievements: str,
    ds: Any,
    ra: Any,
    rate_uri: str,
    fc_uri: str,
    fs_uri: str,
    cover_url: str,
    section: str = "sd",
    level: str = "",
    level_index: int = 2,
    dx_star: Any = None,
    level_text: str = "",
    play_time: str = "",
) -> str:
    """官方版式成绩卡片：文字居左、曲绘居右、右下编号框。"""
    b15 = " b15" if section == "dx" else ""
    try:
        li = int(level_index)
    except (TypeError, ValueError):
        li = 2
    if li < 0 or li >= len(DIFF_COLORS):
        li = 2
    badges = []
    if rate_uri:
        badges.append(f'<img class="badge-rate" src="{rate_uri}" />')
    if fc_uri:
        badges.append(f'<img class="badge-medal" src="{fc_uri}" />')
    if fs_uri:
        badges.append(f'<img class="badge-medal" src="{fs_uri}" />')
    badges_html = f'<div class="card-badges">{"".join(badges)}</div>' if badges else ""
    level_tag = f'<span class="type-tag">{_html.escape(level)}</span>' if level else ""
    lv_html = (
        f'<span class="card-lv">Lv.{_html.escape(level_text)}</span>'
        if level_text
        else ""
    )
    time_html = (
        f'<div class="card-time">{_html.escape(play_time)}</div>'
        if play_time
        else ""
    )
    star_uri = ""
    try:
        star_val = int(dx_star)
        if 1 <= star_val <= 5:
            star_val = min(star_val, 3)  # 素材仅 1~3 档
            star_uri = data_uri(f"maimai/dx_score/{star_val}.webp")
    except (TypeError, ValueError):
        pass
    star_html = f'<img class="dx-star" src="{star_uri}" />' if star_uri else ""
    return (
        f'<div class="score-card diff-{li}{b15}">'
        '<div class="card-info">'
        '<div class="title-row">'
        f'<div class="card-title">{_html.escape(title)}</div>'
        f"{star_html}{level_tag}"
        "</div>"
        f'<div class="card-ach">{_html.escape(achievements)}</div>'
        f'<div class="card-stats"><span>DS {ds}</span><span>RA {ra}</span>{lv_html}</div>'
        f"{badges_html}"
        f"{time_html}"
        "</div>"
        '<div class="card-cover">'
        f'<img src="{cover_url}" onerror="this.style.display=\'none\'" />'
        "</div>"
        f'<div class="card-rank">#{rank}</div>'
        "</div>"
    )


def placeholder_card_html() -> str:
    """「未游玩」占位卡，用于补齐 BEST 35 / BEST 15 网格。"""

    return (
        '<div class="score-card card-placeholder">'
        '<div class="ph-text">未游玩</div>'
        "</div>"
    )


def footer_html(query_time: str, source: str) -> str:
    return (
        '<div class="footer"><div class="footer-inner">'
        f'<span class="footer-time">{_html.escape(query_time)}</span>'
        f'<span class="footer-src">{_html.escape(source)}</span>'
        "</div></div>"
    )
