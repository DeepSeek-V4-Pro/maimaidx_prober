# -*- coding: utf-8 -*-
"""插件配置模型。"""

from pydantic import Field

from maibot_sdk import PluginConfigBase


class PluginSectionConfig(PluginConfigBase):
    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0
    enabled: bool = Field(default=True, description="是否启用插件")
    config_version: str = Field(default="2.0.0", description="配置版本")
    auto_install_deps: bool = Field(
        default=False,
        description="依赖缺失时自动执行 pip 安装（默认关闭，建议手动执行 install_deps.py）",
    )


class ServerConfig(PluginConfigBase):
    __ui_label__ = "服务器"
    __ui_icon__ = "server"
    __ui_order__ = 1
    base_url: str = Field(
        default="https://www.diving-fish.com/api/maimaidxprober",
        description="API 服务器地址",
    )
    request_timeout: int = Field(default=30, description="请求超时时间(秒)")
    music_cache_ttl: int = Field(default=300, description="曲库缓存时间(秒)")


class LxnsServerConfig(PluginConfigBase):
    __ui_label__ = "lxns（落雪）服务器"
    __ui_icon__ = "cloud"
    __ui_order__ = 2
    enable: bool = Field(default=True, description="是否启用 lxns 公开数据补全")
    base_url: str = Field(
        default="https://maimai.lxns.net/api/v0",
        description="lxns API 服务器地址",
    )
    asset_url: str = Field(
        default="https://assets.lxns.net",
        description="lxns 资源 CDN 地址",
    )
    request_timeout: int = Field(default=30, description="请求超时时间(秒)")
    music_cache_ttl: int = Field(default=300, description="lxns 曲库缓存时间(秒)")


class RenderConfig(PluginConfigBase):
    __ui_label__ = "图片渲染"
    __ui_icon__ = "image"
    __ui_order__ = 3
    device_scale_factor: float = Field(
        default=2.0, description="渲染缩放倍率（2.0 为高清，1.0 为标准）"
    )
    image_timeout_ms: int = Field(
        default=15000, description="等待图片加载的超时时间(毫秒)"
    )
    browser_executable: str = Field(
        default="",
        description="Playwright 回退模式下的浏览器可执行文件路径（留空自动查找）",
    )
    headless: bool = Field(default=True, description="Playwright 回退模式是否无头运行")
    no_sandbox: bool = Field(
        default=True,
        description="Playwright 回退模式是否追加 --no-sandbox 参数（容器环境需要）",
    )


class MaiMaiDXConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    lxns: LxnsServerConfig = Field(default_factory=LxnsServerConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
