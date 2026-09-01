"""命令处理模块（以 mixin 形式挂载到插件主类）。"""

from .base import SharedHelpersMixin
from .basic import BasicCommandsMixin
from .diving_fish import DivingFishCommandsMixin
from .lxns import LxnsCommandsMixin
from .maidle import MaidleCommandsMixin
from .score import ScoreCommandsMixin

__all__ = [
    "SharedHelpersMixin",
    "BasicCommandsMixin",
    "DivingFishCommandsMixin",
    "LxnsCommandsMixin",
    "MaidleCommandsMixin",
    "ScoreCommandsMixin",
]
