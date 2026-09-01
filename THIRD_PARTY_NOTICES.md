# 第三方组件与素材许可说明

本插件（MaiMai DX 双源查分器）是组合与修改性作品，整体以 **AGPL-3.0-only**
分发（见仓库根目录 `LICENSE` 与 `_manifest.json` 的 license 字段；因 B50
渲染部分改编自 AGPL-3.0 项目，故采用 AGPL 而非 GPL）。本文件汇总所有被使用、
改编或引用的第三方项目、素材与字体及其许可，修订于 2026-09-02。

## 随插件分发的素材

| 内容 | 来源 | 许可 |
| --- | --- | --- |
| `assets/maimai/class_rank/`、`assets/maimai/course_rank/` | [Lxns-Network/maimai-prober-frontend](https://github.com/Lxns-Network/maimai-prober-frontend)（`public/assets/maimai/`） | MIT，Copyright (c) 2026 Lxns-Network |
| `assets/logo_background.webp` | 同上（`public/logo_background.webp`） | MIT，Copyright (c) 2026 Lxns-Network |
| `assets/awmc_core/mai/`（AWMC/Yuzu B50 静态素材） | [Yuri-YuzuChaN/maimaiDX](https://github.com/Yuri-YuzuChaN/maimaiDX)（Resource CN1.55 static 包） | MIT，Copyright (c) 2021 Yuri-YuzuChaN |
| `assets/awmc_core/font/ResourceHanRoundedCN-Bold.ttf` | [CyanoHao/Resource-Han-Rounded](https://github.com/CyanoHao/Resource-Han-Rounded) | SIL OFL 1.1，Copyright (c) 2018-2022 Cyano Hao / Portions (c) 2014-2021 Adobe |
| `assets/awmc_core/font/Torus SemiBold.otf` | Paulo Goode（Torus） | 商业字体，仅限非商业使用，详见 `assets/awmc_core/NOTICE` |
| `assets/fonts/VarelaRound-Regular.ttf` | Varela Round Project | SIL OFL 1.1，见 `assets/fonts/OFL.txt` |

## B50 渲染代码与版式的参考项目

| 项目 | 许可 |
| --- | --- |
| [AWMC-TEAM/maimaiDX-QueryBot](https://github.com/AWMC-TEAM/maimaiDX-QueryBot) | MIT，Copyright (c) 2023 柚子 |
| [Yuri-YuzuChaN/maimaiDX](https://github.com/Yuri-YuzuChaN/maimaiDX) | MIT，Copyright (c) 2021 Yuri-YuzuChaN |
| [frostfallx/astrbot_plugin_maimaib50](https://github.com/frostfallx/astrbot_plugin_maimaib50) | AGPL-3.0-only，Copyright (C) 2026 frostfallx and contributors |
| [HanYaaaaaaa/analyze-b50](https://github.com/HanYaaaaaaa/analyze-b50) | MIT，Copyright (c) 2026 |
| [HanYaaaaaaa/nonebot-plugin-b50-analysis](https://github.com/HanYaaaaaaa/nonebot-plugin-b50-analysis) | MIT，Copyright (c) 2026 HanYaaaaaaa |
| [Zeraora-807/astrbot_plugin_b50_analysis](https://github.com/Zeraora-807/astrbot_plugin_b50_analysis) | MIT，Copyright (c) 2026 HanYaaaaaaa |
| [ZhiheZier/astrbot_plugin_maimaidx](https://github.com/ZhiheZier/astrbot_plugin_maimaidx) | AGPL-3.0 |

版式设计署名（成品图中保留）：

- `Designed by Yuri-YuzuChaN & BlueDeer233`（B50 版式）
- `Designed by 寒桠@OneCatBot`（分析版式，上游保留署名）

## 数据与接口参考

| 项目 | 许可 |
| --- | --- |
| [Diving-Fish/maimaidx-prober](https://github.com/Diving-Fish/maimaidx-prober) | MIT |
| [Diving-Fish/mai-bot](https://github.com/Diving-Fish/mai-bot) | MIT |
| [Lxns-Network/maimai-prober-frontend](https://github.com/Lxns-Network/maimai-prober-frontend)（`src/utils/rating.ts` DX Rating 系数表） | MIT |

## MIT License 文本

以下 MIT 项目的许可文本一致，仅版权行不同（对应上表各项目）：

```
MIT License

Copyright (c) <年份> <版权人>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

AGPL-3.0 项目（frostfallx/astrbot_plugin_maimaib50、ZhiheZier/astrbot_plugin_maimaidx）
的完整许可文本见各自仓库的 `LICENSE` 文件。

## 游戏版权

maimai DX 及其图标、徽章、曲绘、称号、等级素材等版权归 SEGA 及其相关方所有，
本插件仅用于非商业的玩家成绩展示。使用第三方 API 与数据还可能受各服务条款约束。
