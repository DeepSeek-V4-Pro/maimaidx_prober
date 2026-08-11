# -*- coding: utf-8 -*-
"""DX Rating 计算（与官方 / maimai-prober-frontend 系数表一致）。

来源：``maimai-prober-frontend/src/utils/rating.ts``（Lxns-Network，MIT）。
落雪 ``dx_rating`` 与水鱼 ``ra`` 均按同一系数表计算（最终向下取整），
本模块用于校验服务端返回、以及在定数补全后回填缺失的 RA。
"""

from typing import Any


# 达成率档位 -> 评级系数（按升序阈值）
MAIMAI_COEFFICIENTS: list[tuple[float, float]] = [
    (10.0, 0.0),
    (20.0, 1.6),
    (30.0, 3.2),
    (40.0, 4.8),
    (50.0, 6.4),
    (60.0, 8.0),
    (70.0, 9.6),
    (75.0, 11.2),
    (79.9999, 12.0),
    (80.0, 12.8),
    (90.0, 13.6),
    (94.0, 15.2),
    (96.9999, 16.8),
    (97.0, 17.6),
    (98.0, 20.0),
    (98.9999, 20.3),
    (99.0, 20.6),
    (99.5, 20.8),
    (99.9999, 21.1),
    (100.0, 21.4),
    (100.4999, 21.6),
    (100.5, 22.2),
]


def rate_coefficient(achievements: float) -> float:
    """按达成率返回评级系数；超过 100.5 取最高档 22.4。"""

    for threshold, coeff in MAIMAI_COEFFICIENTS:
        if achievements < threshold:
            return coeff
    return 22.4


def calculate_maimai_rating(chart_constant: Any, achievement_rate: Any) -> float:
    """计算单曲 DX Rating（未取整）。"""

    try:
        ds = float(chart_constant)
        acc = float(achievement_rate)
    except (TypeError, ValueError):
        return 0.0
    if ds <= 0 or acc <= 0:
        return 0.0
    acc = min(acc, 100.5)
    return acc / 100.0 * rate_coefficient(acc) * ds


def compute_ra(chart_constant: Any, achievement_rate: Any) -> int:
    """取整后的 RA（与落雪 dx_rating / 水鱼 ra 语义一致）。"""

    return int(calculate_maimai_rating(chart_constant, achievement_rate))
