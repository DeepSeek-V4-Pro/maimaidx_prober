# -*- coding: utf-8 -*-
"""浅色面板设计系统（字体 / 配色）。

my / song / today / help / heatmap / trend / maidle / history / rank / year /
collections / pick / status / charts / aliases / lxns status / player / plate
等渲染器共用：Varela Round 圆体 + 马卡龙渐变背景 + 白色圆角面板。
B50 / AP50 使用 AWMC/Yuzu 原版贴图（b50_awmc_pillow.py），不走本设计系统。
"""

import functools

from ..assets import data_uri

FONT_STACK = (
    "'Varela Round','M PLUS Rounded 1c','Yu Gothic UI','Yu Gothic',"
    "'Noto Sans SC','Microsoft YaHei UI','Microsoft JhengHei UI',sans-serif"
)

COLORS = {
    "bar": "#2FD6B8",       # 强调条青绿
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


def panel_style(extra: str = "") -> str:
    """浅色面板 CSS（马卡龙背景 + 白色圆角面板 + 共享组件）。

    供 my / song / today / help / heatmap / trend / maidle / history / rank /
    year / collections / pick / status / charts / aliases / lxns status /
    player / plate 等渲染器使用。
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
