from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from .config import DetectionParams


def normalize_image(image: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(image[np.isfinite(image)], [1, 99])
    if hi <= lo:
        return np.zeros_like(image, dtype=np.float32)
    clipped = np.clip(image, lo, hi)
    return ((clipped - lo) / (hi - lo)).astype(np.float32)


def preprocess_image(image: np.ndarray, params: DetectionParams) -> tuple[np.ndarray, np.ndarray]:
    normalized = normalize_image(image)
    background = ndi.gaussian_filter(normalized, sigma=max(params.background_sigma, 0.1))
    corrected = normalized - background
    corrected -= float(np.min(corrected))
    max_value = float(np.max(corrected))
    if max_value > 0:
        corrected /= max_value
    if params.mode == "dark":
        corrected = 1.0 - corrected
    denoised = ndi.gaussian_filter(corrected, sigma=0.6)
    return denoised.astype(np.float32), normalized
