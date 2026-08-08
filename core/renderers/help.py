# -*- coding: utf-8 -*-
"""帮助图片渲染（v2.0 起统一命令前缀 /mai）。"""

from ..services.renderer import HtmlRenderer
from .common import cmd_section, doc, footer_bar


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
         [("/mai b50 [用户]", "生成 Best 50 成绩图片"),
          ("/mai my", "查看个人成绩摘要"),
          ("/mai bind <Token>", "绑定成绩导入 Token"),
          ("/mai unbind", "解除绑定")]),
    ]
    style = (
        "body{padding:36px 48px}"
        ".header{text-align:center;margin-bottom:30px}"
        ".header h2{font-size:40px;color:#e8e8f0;letter-spacing:4px;margin-bottom:8px}"
        ".header .sub{font-size:18px;color:#7878a8}"
        ".section{margin-bottom:24px}"
        ".sec-label{font-size:24px;color:#c0c0d8;font-weight:600;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #2e2e48}"
        ".cmd{display:flex;padding:8px 0}"
        ".cmd-name{flex-shrink:0;width:380px;font-size:22px;color:#5b8fd4;font-family:'Consolas','Courier New',monospace}"
        ".cmd-desc{font-size:22px;color:#9090b8}"
        ".footer-bar{display:flex;margin-top:20px;padding-top:10px;border-top:1px solid #333350;font-size:14px}"
        ".footer-source{color:#7878a8;flex:1}"
        ".footer-mai{color:#585878;text-align:right}"
    )
    body = (
        '<div class="header"><h2>MaiMai DX 查分器</h2>'
        '<div class="sub">diving-fish 查分 + lxns 数据补全 · 统一 /mai 前缀</div></div>'
        + "".join(cmd_section(label, cmds) for label, cmds in sections)
        + footer_bar("数据来源: diving-fish + lxns")
    )
    return await renderer.render(doc(style, body), width=1060, height=760)


async def render_maidle_help(renderer: HtmlRenderer) -> str:
    style = (
        "body{width:520px;padding:32px}"
        "h2{font-size:20px;color:#e8e8f0;text-align:center;letter-spacing:2px;margin-bottom:16px}"
        "p{font-size:14px;color:#c0c0d0;line-height:1.7;margin-bottom:12px}"
        ".legend{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}"
        ".legend span{font-size:13px;background:#24243a;padding:3px 10px;border-radius:4px;color:#c8c8d8}"
        ".legend .hl{color:#5b8fd4}"
        ".sep{border-top:1px solid #333350;margin:16px 0}"
        ".cmds{font-size:13px;color:#9090b8;line-height:2;text-align:center}"
    )
    body = (
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
        '<div style="text-align:right;margin-top:16px;font-size:12px;color:#585878">MaiBot</div>'
    )
    return await renderer.render(doc(style, body), width=520, height=400)
