# -*- coding: utf-8 -*-
"""帮助图片渲染：总览、水鱼专属、落雪专属与 Maidle 说明。"""

from ..services.renderer import HtmlRenderer
from .common import cmd_section, doc, footer_bar
from .theme import panel_style


async def _render_command_help(
    renderer: HtmlRenderer,
    title: str,
    subtitle: str,
    sections: list,
    width: int,
    height: int,
    style_extra: str = "",
    note: str = "",
    footer: str = "数据来源: maimai",
) -> str:
    """按同一设计系统渲染命令帮助页。"""
    note_html = f'<div class="help-note">{note}</div>' if note else ""
    style = (
        ".cmd-desc{font-size:18px}"
        ".help-note{margin-top:14px;padding:10px 14px;border-radius:10px;"
        "background:#F6F2FC;color:#6B5D8A;font-size:15px;line-height:1.7}"
        + style_extra
    )
    body = (
        '<div class="panel">'
        f'<div class="p-title">{title}</div>'
        f'<div class="p-sub">{subtitle}</div>'
        + "".join(cmd_section(label, cmds) for label, cmds in sections)
        + note_html
        + footer_bar(footer)
        + "</div>"
    )
    return await renderer.render(doc(panel_style(style), body), width=width, height=height)


async def render_help(renderer: HtmlRenderer) -> str:
    sections = [
        ("双源成绩查询 (/mai)",
         [
             ("/mai b50 [用户] [--lxns|--df]", "Best 50 成绩图，来源标志可放在用户前后"),
             ("/mai my [--lxns|--df]", "个人成绩摘要，可强制指定数据源"),
         ]),
        ("通用功能 (/mai)",
         [
             ("/mai song <关键词/ID>", "搜索曲目；ID 直接查看详情"),
             ("/mai today", "今日宜忌与推荐歌曲"),
             ("/mai charts", "全谱面难度分布统计"),
             ("/mai status", "水鱼 + 落雪服务器状态"),
             ("/mai pick <A> <B> [C] [D]", "随机选择（2~4 个选项）"),
             ("/mai maidle", "开始 Maidle 猜歌游戏"),
             ("/mai maidle guess <ID/名称>", "提交猜歌"),
             ("/mai maidle help", "猜歌规则说明"),
             ("/mai maidle answer", "查看答案并结束本轮"),
         ]),
        ("别称管理 (/mai alias)",
         [
             ("/mai alias add <ID> <名称>", "添加本地别称"),
             ("/mai alias del <ID> <名称>", "删除本地别称"),
             ("/mai alias list <ID>", "查看歌曲别称"),
             ("/mai alias import", "从 lxns 导入社区别名"),
         ]),
        ("平台帮助",
         [
             ("/mai df help", "水鱼（diving-fish）专属命令"),
             ("/mai lxns help", "落雪（lxns）专属命令"),
         ]),
    ]
    note = (
        "数据源自动选择顺序：强制来源优先；好友码 → 开发者落雪；已绑定落雪 → 落雪；否则 → 水鱼。"
        "需要固定来源时可使用 --lxns / --df。"
    )
    return await _render_command_help(
        renderer,
        "MaiMai DX 查分器",
        "命令总览 · 水鱼 / 落雪请查看对应专属帮助",
        sections,
        1080,
        980,
        note=note,
        footer="数据来源: diving-fish · lxns",
    )


async def render_df_help(renderer: HtmlRenderer) -> str:
    sections = [
        ("水鱼账号绑定 (/mai df)",
         [
             ("/mai df bind", "发起 OAuth 设备码绑定"),
             ("/mai df bind confirm", "确认绑定结果"),
             ("/mai df unbind", "解除水鱼 OAuth 绑定"),
             ("/mai df status", "查看 OAuth 绑定状态"),
             ("/mai bind <Token>", "绑定旧版成绩导入 Token"),
             ("/mai unbind", "解除旧版 Token 绑定（不影响 OAuth）"),
         ]),
        ("成绩与排行 (/mai)",
         [
             ("/mai b50 [用户] --df", "强制水鱼 Best 50"),
             ("/mai my --df", "强制水鱼个人成绩摘要"),
             ("/mai plate <版本代号>", "按版本查询已绑定账号（优先 OAuth）"),
             ("/mai hot [N]", "热门歌曲 TOP N（1~30）"),
             ("/mai ranking [N]", "DX Rating 排行 TOP N（1~50）"),
         ]),
        ("数据同步 (/mai df)",
         [
             ("/mai df upload", "落雪成绩同步到水鱼（只升不降）"),
         ]),
    ]
    note = (
        "水鱼 OAuth 查询对象由授权令牌决定，无需再传用户名。"
        "旧 Developer-Token 回退可用性以水鱼服务端为准，建议使用 OAuth。"
    )
    return await _render_command_help(
        renderer,
        "水鱼（diving-fish）命令",
        "OAuth 绑定、旧版 Token、成绩查询与同步",
        sections,
        1080,
        920,
        note=note,
        footer="数据来源: diving-fish",
    )


async def render_lxns_help(renderer: HtmlRenderer) -> str:
    sections = [
        ("落雪账号绑定 (/mai lxns)",
         [
             ("/mai lxns bind", "OAuth 授权绑定"),
             ("/mai lxns bind token <密钥>", "用个人 API 密钥绑定"),
             ("/mai lxns bind code <授权码>", "用授权码完成 OAuth 绑定"),
             ("/mai lxns unbind", "解除落雪绑定"),
             ("/mai lxns status", "查看绑定状态与开发者配置"),
         ]),
        ("玩家与成绩 (/mai lxns)",
         [
             ("/mai lxns player [好友码]", "玩家资料卡"),
             ("/mai lxns best [好友码] <曲名/ID>", "单曲所有谱面最佳成绩"),
             ("/mai lxns ap50 <好友码>", "All Perfect 50（开发者模式）"),
             ("/mai lxns qq <QQ号>", "按 QQ 查玩家（开发者模式）"),
             ("/mai b50 [用户] --lxns", "强制落雪 Best 50"),
             ("/mai my --lxns", "强制落雪个人成绩摘要"),
         ]),
        ("趋势与回顾 (/mai lxns)",
         [
             ("/mai lxns heatmap", "成绩上传热力图"),
             ("/mai lxns trend [版本号]", "DX Rating 趋势"),
             ("/mai lxns history <曲名/ID>", "单曲成绩上传历史"),
             ("/mai lxns rank <曲名/ID>", "单曲分数排行"),
             ("/mai lxns year [年份]", "年度回顾"),
             ("/mai lxns collections", "收藏品实物图"),
         ]),
        ("同步与评论 (/mai lxns)",
         [
             ("/mai lxns upload", "水鱼成绩同步到落雪（只升不降）"),
             ("/mai lxns comment list <曲名/ID>", "查看评论（OAuth）"),
             ("/mai lxns comment <曲名/ID> <内容>", "发表评论（OAuth）"),
             ("/mai lxns comment like <评论ID>", "点赞评论（OAuth）"),
         ]),
    ]
    note = (
        "AP50、按 QQ 查玩家和好友码查询需管理员配置落雪开发者密钥并把 QQ 加入白名单。"
        "评论接口仅支持 OAuth；落雪服务端暂未开放时会返回友好提示。"
    )
    style_extra = (
        ".cmd-name{font-size:17px}"
        ".cmd-desc{font-size:17px}"
        ".cmd-grid{display:grid;grid-template-columns:1fr 1fr;"
        "gap:6px 32px;align-items:start}"
    )
    sections = [
        (label, cmds, "350px", 2) for label, cmds in sections
    ]
    body = (
        '<div class="panel">'
        '<div class="p-title">落雪（lxns）命令</div>'
        '<div class="p-sub">绑定、玩家、趋势、同步与评论</div>'
        + "".join(cmd_section(label, cmds, name_width=width, columns=columns)
                  for label, cmds, width, columns in sections)
        + f'<div class="help-note">{note}</div>'
        + footer_bar("数据来源: maimai · lxns")
        + "</div>"
    )
    return await renderer.render(
        doc(panel_style(style_extra), body), width=1120, height=1040
    )


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
