"""图片渲染器。"""

from .b50 import render_b50
from .collections import render_collections
from .heatmap import render_heatmap
from .help import render_help, render_maidle_help
from .history import render_history
from .maidle import render_maidle_answer, render_maidle_guess
from .my import render_my
from .pick import render_pick
from .rank import render_rank
from .song import render_song_detail
from .status import render_status
from .today import render_today
from .trend import render_trend
from .year import render_year

__all__ = [
    "render_b50",
    "render_collections",
    "render_help",
    "render_heatmap",
    "render_history",
    "render_maidle_help",
    "render_maidle_answer",
    "render_maidle_guess",
    "render_my",
    "render_pick",
    "render_rank",
    "render_song_detail",
    "render_status",
    "render_today",
    "render_trend",
    "render_year",
]
