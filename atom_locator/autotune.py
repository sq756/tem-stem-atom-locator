from __future__ import annotations

from dataclasses import replace
from itertools import product
from pathlib import Path

import numpy as np

from .config import DetectionParams
from .data_io import read_tiff_grayscale
from .detect import detect_candidates
from .graph import attach_neighbors
from .preprocess import preprocess_image
from .refine import refine_candidates


def autotune_params(image_path: Path, roi: dict, base_params: DetectionParams) -> dict:
    raw_image, image_meta = read_tiff_grayscale(image_path)
    x0, y0, width, height = normalize_roi(roi, image_meta["width"], image_meta["height"])
    raw_crop = raw_image[y0 : y0 + height, x0 : x0 + width]
    candidates = []
    for params in parameter_grid(base_params):
        preprocessed, _ = preprocess_image(raw_crop, params)
        detected = detect_candidates(preprocessed, params)
        sites = refine_candidates(preprocessed, detected, params)
        lattice = attach_neighbors(sites, params.neighbors_k)
        score = score_sites(sites, lattice, width, height)
        candidates.append(
            {
                "score": score,
                "site_count": len(sites),
                "nearest_neighbor_distance_px": lattice.get("nearest_neighbor_distance_px"),
                "distance_std_px": lattice.get("distance_std_px"),
                "parameters": params.to_dict(),
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return {
        "roi": {"x": x0, "y": y0, "width": width, "height": height},
        "best_parameters": candidates[0]["parameters"],
        "top_candidates": candidates[:5],
    }


def normalize_roi(roi: dict, image_width: int, image_height: int) -> tuple[int, int, int, int]:
    x = int(round(float(roi["x"])))
    y = int(round(float(roi["y"])))
    width = int(round(float(roi["width"])))
    height = int(round(float(roi["height"])))
    x = max(0, min(x, image_width - 1))
    y = max(0, min(y, image_height - 1))
    width = max(16, min(width, image_width - x))
    height = max(16, min(height, image_height - y))
    return x, y, width, height


def parameter_grid(base: DetectionParams) -> list[DetectionParams]:
    sigma_min_values = [0.8, 1.2]
    sigma_max_values = [4.0, 6.0]
    threshold_values = [0.08, 0.12, 0.18]
    min_distance_values = [5, 8, 11]
    background_values = [30.0, 60.0]
    params = []
    for sigma_min, sigma_max, threshold, min_distance, background in product(
        sigma_min_values,
        sigma_max_values,
        threshold_values,
        min_distance_values,
        background_values,
    ):
        if sigma_min >= sigma_max:
            continue
        params.append(
            replace(
                base,
                sigma_min=sigma_min,
                sigma_max=sigma_max,
                threshold_rel=threshold,
                min_distance=min_distance,
                background_sigma=background,
                refine_method="centroid",
            )
        )
    return params


def score_sites(sites: list[dict], lattice: dict, width: int, height: int) -> float:
    if len(sites) < 12:
        return -1000.0 + len(sites)
    area_units = max((width * height) / 10000.0, 1.0)
    density = len(sites) / area_units
    median_distance = lattice.get("nearest_neighbor_distance_px") or 0.0
    distance_std = lattice.get("distance_std_px") or median_distance
    distance_cv = distance_std / max(median_distance, 1e-6)
    responses = np.array([site.get("response", site.get("confidence", 0.0)) for site in sites], dtype=float)
    peak_quality = float(np.clip(np.mean(responses), 0.0, 1.0))
    coverage = grid_coverage(sites, width, height)
    density_penalty = abs(density - 18.0) / 18.0
    crowd_penalty = max(0.0, 4.0 - median_distance) / 4.0
    return (
        2.2 * max(0.0, 1.0 - distance_cv)
        + 1.4 * peak_quality
        + 1.1 * coverage
        - 0.9 * density_penalty
        - 1.2 * crowd_penalty
    )


def grid_coverage(sites: list[dict], width: int, height: int) -> float:
    bins = np.zeros((4, 4), dtype=bool)
    for site in sites:
        x_bin = min(3, max(0, int(site["x_px"] / max(width, 1) * 4)))
        y_bin = min(3, max(0, int(site["y_px"] / max(height, 1) * 4)))
        bins[y_bin, x_bin] = True
    return float(np.mean(bins))
