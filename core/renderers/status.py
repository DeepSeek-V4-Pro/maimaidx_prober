# -*- coding: utf-8 -*-
"""服务器状态渲染（浅色面板风格）。"""

import html as _html

from ..services.renderer import HtmlRenderer
from .common import doc
from .theme import panel_style


async def render_status(
    renderer: HtmlRenderer,
    results: list[tuple[str, bool, str]],
) -> str:
    rows = []
    for name, ok, detail in results:
        cls = "ok" if ok else "bad"
        icon = "正常" if ok else "异常"
        rows.append(
            f'<div class="svc {cls}">'
            f'<span class="dot"></span>'
            f'<span class="name">{_html.escape(name)}</span>'
            f'<span class="state">{icon}</span>'
            f'<span class="detail">{_html.escape(detail)}</span>'
            "</div>"
        )
    extra = (
        ".svc{display:flex;align-items:center;gap:12px;background:#FFFFFF;border-radius:12px;padding:13px 16px;margin:10px 0;box-shadow:0 2px 8px rgba(120,80,160,.08)}"
        ".svc .dot{width:12px;height:12px;border-radius:50%;flex:none}"
        ".svc.ok .dot{background:#3FAE6D;box-shadow:0 0 0 4px rgba(63,174,109,.18)}"
        ".svc.bad .dot{background:#D9534F;box-shadow:0 0 0 4px rgba(217,83,79,.16)}"
        ".svc .name{font-size:16px;font-weight:700;color:#4A3B63;width:120px}"
        ".svc .state{font-size:14px;font-weight:800;width:44px}"
        ".svc.ok .state{color:#3FAE6D}"
        ".svc.bad .state{color:#D9534F}"
        ".svc .detail{font-size:13px;color:#8B7BA6;flex:1;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
    )
    body = (
        '<div class="panel">'
        '<div class="p-title">服务器状态</div>'
        '<div class="p-sub">diving-fish · lxns 双源检测</div>'
        + "".join(rows)
        + '<div class="p-footer">'
        '<span class="footer-source">MaiBot</span><span class="footer-mai"></span></div>'
        + "</div>"
    )
    return await renderer.render(doc(panel_style(extra), body), width=640, height=240)
