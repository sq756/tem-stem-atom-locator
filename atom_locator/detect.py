from __future__ import annotations

import numpy as np
from skimage.feature import blob_log

from .config import DetectionParams


def detect_candidates(image: np.ndarray, params: DetectionParams) -> list[dict]:
    blobs = blob_log(
        image,
        min_sigma=params.sigma_min,
        max_sigma=params.sigma_max,
        num_sigma=params.num_sigma,
        threshold=params.threshold_rel,
        overlap=0.45,
    )
    candidates: list[dict] = []
    for idx, blob in enumerate(blobs):
        y, x, sigma = blob[:3]
        xi = int(round(x))
        yi = int(round(y))
        if yi < 0 or yi >= image.shape[0] or xi < 0 or xi >= image.shape[1]:
            continue
        candidates.append(
            {
                "id": idx + 1,
                "x": float(x),
                "y": float(y),
                "sigma": float(sigma),
                "response": float(image[yi, xi]),
            }
        )
    candidates.sort(key=lambda c: c["response"], reverse=True)
    candidates = candidates[:3000]
    return suppress_by_distance(candidates, params.min_distance)


def suppress_by_distance(candidates: list[dict], min_distance: int) -> list[dict]:
    accepted: list[dict] = []
    min_distance_sq = float(min_distance * min_distance)
    for candidate in candidates:
        if all(
            (candidate["x"] - other["x"]) ** 2 + (candidate["y"] - other["y"]) ** 2
            >= min_distance_sq
            for other in accepted
        ):
            accepted.append(candidate)
    for idx, candidate in enumerate(accepted, start=1):
        candidate["id"] = idx
    return accepted
