from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def exclusion_mask(normalized_image: np.ndarray, bottom_fraction: float, dark_threshold: float) -> np.ndarray:
    mask = np.zeros(normalized_image.shape, dtype=bool)
    if bottom_fraction > 0:
        bottom_start = int(round(normalized_image.shape[0] * (1.0 - bottom_fraction)))
        mask[max(bottom_start, 0) :, :] = True
    if dark_threshold > 0:
        dark = normalized_image <= dark_threshold
        seeds = np.zeros_like(dark, dtype=bool)
        seeds[0, :] = dark[0, :]
        seeds[-1, :] = dark[-1, :]
        seeds[:, 0] = dark[:, 0]
        seeds[:, -1] = dark[:, -1]
        mask |= ndi.binary_propagation(seeds, mask=dark)
    return mask


def filter_sites_by_mask(sites: list[dict], mask: np.ndarray) -> list[dict]:
    filtered = []
    for site in sites:
        x = int(round(site["x_px"]))
        y = int(round(site["y_px"]))
        if y < 0 or y >= mask.shape[0] or x < 0 or x >= mask.shape[1]:
            continue
        if not bool(mask[y, x]):
            filtered.append(site)
    for idx, site in enumerate(filtered, start=1):
        site["id"] = idx
    return filtered
