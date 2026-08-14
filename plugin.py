"""MaiMai DX 查分器插件入口 (v3.1)。

从模块化的 ``core`` 包导入插件主类，保持 MaiBot 要求的
``plugin.py + create_plugin()`` 入口形态。
"""

from .core import MaiMaiDXPlugin, create_plugin

__all__ = ["MaiMaiDXPlugin", "create_plugin"]
