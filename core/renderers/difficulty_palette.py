"""AWMC 难度素材在加载时统一颜色，保留透明度与原图布局。"""
from PIL import Image

from ..constants import DIFF_RGBA

_ASSET_COLORS = {
    (129, 217, 85): DIFF_RGBA[0][:3],
    (245, 189, 21): DIFF_RGBA[1][:3],
    (255, 129, 141): DIFF_RGBA[2][:3],
    (159, 81, 220): DIFF_RGBA[3][:3],
    (176, 86, 245): DIFF_RGBA[3][:3],
    (230, 197, 255): DIFF_RGBA[4][:3],
}


def apply_difficulty_palette(image: Image.Image, filename: str) -> Image.Image:
    """仅处理难度 UI 素材；头像、曲绘、背景保持原样。"""
    if filename not in ("chart_info.png", "play_info.png") and not filename.startswith(("d_", "b50_score_")):
        return image
    pixels = list(image.getdata())
    image.putdata([(*_ASSET_COLORS.get(pixel[:3], pixel[:3]), pixel[3]) for pixel in pixels])
    return image
