from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def save_preprocessed(image: np.ndarray, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gray = np.clip(image * 255, 0, 255).astype(np.uint8)
    Image.fromarray(gray, mode="L").save(output_path)


def save_overlay(base_image: np.ndarray, sites: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gray = np.clip(base_image * 255, 0, 255).astype(np.uint8)
    rgb = Image.fromarray(gray, mode="L").convert("RGB")
    draw = ImageDraw.Draw(rgb)
    radius = max(3, int(round(min(base_image.shape) / 450)))
    for site in sites:
        x = float(site["x_px"])
        y = float(site["y_px"])
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            outline=(255, 59, 48),
            width=max(1, radius // 2),
        )
    rgb.save(output_path)


def save_mask_overlay(base_image: np.ndarray, mask: np.ndarray, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gray = np.clip(base_image * 255, 0, 255).astype(np.uint8)
    rgba = Image.fromarray(gray, mode="L").convert("RGBA")
    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    mask_image = Image.fromarray((mask.astype(np.uint8) * 120), mode="L")
    tint = Image.new("RGBA", rgba.size, (255, 184, 28, 120))
    overlay.paste(tint, mask=mask_image)
    Image.alpha_composite(rgba, overlay).save(output_path)
