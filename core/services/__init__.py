"""业务服务层。"""

from .covers import CoverService
from .deps import check_dependencies, ensure_dependencies
from .diving_fish_auth import DivingFishOAuthService
from .lxns_auth import LxnsAuthService
from .maidle import MaidleManager
from .music import MusicService
from .player import PlayerQueryService
from .renderer import HtmlRenderer

__all__ = [
    "CoverService",
    "check_dependencies",
    "ensure_dependencies",
    "DivingFishOAuthService",
    "LxnsAuthService",
    "MaidleManager",
    "MusicService",
    "PlayerQueryService",
    "HtmlRenderer",
]
