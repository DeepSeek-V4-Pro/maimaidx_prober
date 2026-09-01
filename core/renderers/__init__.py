"""图片渲染器。"""

from .aliases import render_aliases
from .b50_awmc_pillow import render_b50
from .best import render_best
from .charts import render_charts
from .collections import render_collections
from .heatmap import render_heatmap
from .help import render_help, render_maidle_help
from .history import render_history
from .hot import render_hot
from .lxns_status import render_lxns_status
from .maidle import render_maidle_answer, render_maidle_guess
from .my import render_my
from .pick import render_pick
from .plate import render_plate
from .player import render_player
from .rank import render_rank
from .ranking import render_ranking
from .song import render_song_detail
from .status import render_status
from .today import render_today
from .trend import render_trend
from .year import render_year

__all__ = [
    "render_aliases",
    "render_b50",
    "render_best",
    "render_charts",
    "render_collections",
    "render_help",
    "render_heatmap",
    "render_history",
    "render_hot",
    "render_lxns_status",
    "render_maidle_help",
    "render_maidle_answer",
    "render_maidle_guess",
    "render_my",
    "render_pick",
    "render_plate",
    "render_player",
    "render_rank",
    "render_ranking",
    "render_song_detail",
    "render_status",
    "render_today",
    "render_trend",
    "render_year",
]
