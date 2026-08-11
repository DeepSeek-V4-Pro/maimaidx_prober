# -*- coding: utf-8 -*-
"""帮助图片渲染（v2.0 起统一命令前缀 /mai；v3.0 加入落雪账号功能）。"""

from ..services.renderer import HtmlRenderer
from .common import cmd_section, doc, footer_bar
from .theme import panel_style


async def render_help(renderer: HtmlRenderer) -> str:
    sections = [
        ("基础功能 (/mai)",
         [("/mai song <关键词>", "搜索曲目，ID 直接查看详情"),
          ("/mai today", "今日运势 — 随机推荐歌曲"),
          ("/mai maidle", "猜歌游戏 (Maidle)"),
          ("/mai charts", "全谱面难度分布统计"),
          ("/mai status", "服务器状态检测 (双服)"),
          ("/mai pick <A> <B> [C] [D]", "随机帮你选一个"),
          ("/mai help", "显示本帮助")]),
        ("别称管理 (/mai alias)",
         [("/mai alias add <ID> <名称>", "添加别称"),
          ("/mai alias del <ID> <名称>", "删除别称"),
          ("/mai alias list <ID>", "查看别称"),
          ("/mai alias import", "导入 lxns 社区别名")]),
        ("成绩查询 (/mai)",
         [("/mai b50 [用户] [--lxns|--df]", "Best 50 图片；可强制指定数据源"),
          ("/mai my [--lxns|--df]", "个人成绩摘要；可强制指定数据源"),
          ("/mai bind <Token>", "绑定成绩导入 Token"),
          ("/mai unbind", "解除绑定")]),
        ("落雪账号 (/mai lxns)",
         [("/mai lxns bind", "OAuth 授权绑定落雪账号"),
          ("/mai lxns bind token <密钥>", "用个人 API 密钥绑定"),
          ("/mai lxns bind code <授权码>", "用授权码完成 OAuth 绑定"),
          ("/mai lxns unbind", "解除落雪绑定"),
          ("/mai lxns status", "查看绑定状态"),
          ("/mai lxns heatmap", "上传热力图"),
          ("/mai lxns trend [版本]", "DX Rating 趋势"),
          ("/mai lxns history <曲名>", "单曲游玩历史"),
          ("/mai lxns rank <曲名>", "单曲分数排行"),
          ("/mai lxns year [年份]", "年度回顾"),
          ("/mai lxns collections", "收藏品（称号/头像等）"),
          ("/mai lxns upload", "水鱼成绩同步到落雪（只升不降）"),
          ("/mai lxns comment list <曲名>", "查看曲目评论（服务端未开放时不可用）")]),
    ]
    style = ".cmd-name{width:380px;font-size:20px}.cmd-desc{font-size:20px}"
    body = (
        '<div class="panel">'
        '<div class="p-title">MaiMai DX 查分器</div>'
        '<div class="p-sub">diving-fish + lxns 双源查分 · 绑定落雪后自动使用落雪数据</div>'
        + "".join(cmd_section(label, cmds) for label, cmds in sections)
        + footer_bar("数据来源: maimai")
        + "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=1060, height=940)


async def render_maidle_help(renderer: HtmlRenderer) -> str:
    style = (
        "h2{font-size:20px;color:#4A3B63;text-align:center;letter-spacing:2px;margin-bottom:14px}"
        "p{font-size:14px;color:#6B5D8A;line-height:1.7;margin-bottom:12px}"
        ".legend{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}"
        ".legend span{font-size:13px;background:#F0EAF8;padding:3px 10px;border-radius:8px;color:#4A3B63}"
        ".legend .hl{color:#7048E8;font-weight:700}"
        ".sep{border-top:1px solid #EFE6F7;margin:16px 0}"
        ".cmds{font-size:13px;color:#6B5D8A;line-height:2;text-align:center}"
    )
    body = (
        '<div class="panel">'
        "<h2>Maidle 猜歌说明</h2>"
        "<p>系统从曲库中随机选取一首隐藏歌曲，玩家通过不断输入歌曲 ID 进行猜测。"
        "每次猜测后，系统会返回线索，指示猜测曲目与目标曲目的属性差异。</p>"
        '<div class="legend"><span class="hl">&#10003; 匹配</span><span>&#10007; 不匹配</span>'
        '<span>&#8593; 更高</span><span>&#8595; 更低</span>'
        '<span>&#8776; 接近</span><span>&#8596; 较远</span></div>'
        "<p>推测属性可能包括：类型(SD/DX)、分类、版本、作者、BPM 等。"
        "通过不断缩小范围，最终找到目标歌曲!</p>"
        '<div class="sep"></div>'
        '<div class="cmds">开始游戏: /mai maidle<br/>提交猜测: /mai maidle guess &lt;歌曲ID&gt;<br/>查看答案: /mai maidle answer</div>'
        '<div class="p-footer">'
        '<span class="footer-source">MaiBot</span><span class="footer-mai"></span></div>'
        "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=520, height=400)
