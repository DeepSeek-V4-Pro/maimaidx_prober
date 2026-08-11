# -*- coding: utf-8 -*-
"""落雪绑定状态渲染（浅色面板风格）。"""

import html as _html
from typing import Any, Optional

from ..services.renderer import HtmlRenderer
from ..util import fmt_utc
from .common import doc, footer_bar
from .theme import panel_style


async def render_lxns_status(
    renderer: HtmlRenderer,
    binding: Optional[dict[str, Any]],
    oauth_configured: bool,
    developer_configured: bool,
    developer_qq_count: int = 0,
) -> str:
    rows: list[tuple[str, str]] = []
    if not binding:
        rows.append(("状态", "未绑定"))
        rows.append(("绑定方式", "/mai lxns bind（OAuth）或 /mai lxns bind token <个人密钥>"))
    else:
        mode = "OAuth" if binding.get("mode") == "oauth" else "个人 API 密钥"
        rows.append(("状态", f"已绑定（{mode}）"))
        rows.append(("玩家", _html.escape(str(binding.get("username", "?")))))
        fc = binding.get("friend_code")
        if fc:
            rows.append(("好友码", str(fc)))
        if binding.get("mode") == "oauth":
            rows.append(("访问令牌过期", fmt_utc(binding.get("expires_at", "")) + "（自动刷新）"))
        rows.append(("绑定时间", str(binding.get("bound_at", ""))[:19].replace("T", " ")))
    rows.append(("OAuth 应用", "已配置" if oauth_configured else "未配置"))
    rows.append(("开发者密钥", "已配置" if developer_configured else "未配置"))
    rows.append((
        "开发者权限",
        f"已授权 {developer_qq_count} 个 QQ"
        if developer_qq_count > 0 else "未授权（开发者功能关闭）",
    ))

    row_html = "".join(
        '<div class="row">'
        f'<span class="label">{_html.escape(label)}</span>'
        f'<span class="value">{_html.escape(str(value))}</span>'
        "</div>"
        for label, value in rows
    )
    style = (
        ".row{display:flex;align-items:center;background:#FFFFFF;border-radius:12px;"
        "padding:12px 16px;margin:8px 0;box-shadow:0 2px 8px rgba(120,80,160,.08)}"
        ".row .label{width:110px;font-size:14px;color:#8B7BA6;flex:none}"
        ".row .value{font-size:15px;color:#4A3B63;font-weight:600}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">落雪绑定状态</div>'
        '<div class="p-sub">OAuth · 个人 API · 开发者密钥</div>'
        + row_html
        + footer_bar("数据来源: 本地")
        + "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=680, height=230 + len(rows) * 52)
