from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit

from .config import DetectionParams


def refine_candidates(
    image: np.ndarray, candidates: list[dict], params: DetectionParams
) -> list[dict]:
    refined = []
    for candidate in candidates:
        if params.refine_method == "gaussian":
            site = refine_gaussian(image, candidate, params.refine_window)
        else:
            site = refine_centroid(image, candidate, params.refine_window)
        refined.append(site)
    return refined


def _window(image: np.ndarray, x: float, y: float, radius: int):
    xi = int(round(x))
    yi = int(round(y))
    y0 = max(0, yi - radius)
    y1 = min(image.shape[0], yi + radius + 1)
    x0 = max(0, xi - radius)
    x1 = min(image.shape[1], xi + radius + 1)
    return image[y0:y1, x0:x1], x0, y0


def refine_centroid(image: np.ndarray, candidate: dict, window_radius: int) -> dict:
    patch, x0, y0 = _window(image, candidate["x"], candidate["y"], window_radius)
    weights = patch - float(np.min(patch))
    total = float(np.sum(weights))
    if total <= 1e-8:
        x_refined = candidate["x"]
        y_refined = candidate["y"]
    else:
        yy, xx = np.indices(patch.shape)
        x_refined = float(np.sum((xx + x0) * weights) / total)
        y_refined = float(np.sum((yy + y0) * weights) / total)
    sigma = max(float(candidate["sigma"]), 1e-6)
    return {
        "id": int(candidate["id"]),
        "x_px": x_refined,
        "y_px": y_refined,
        "intensity": float(np.max(patch)),
        "sigma_x": sigma,
        "sigma_y": sigma,
        "ellipticity": 1.0,
        "local_contrast": float(np.max(patch) - np.median(patch)),
        "fit_error": 0.0,
        "confidence": confidence(float(candidate["response"]), 0.0, 1.0),
        "response": float(candidate["response"]),
    }


def _gaussian_2d(coords, amp, x0, y0, sx, sy, bg):
    x, y = coords
    sx = np.maximum(sx, 1e-3)
    sy = np.maximum(sy, 1e-3)
    return bg + amp * np.exp(-(((x - x0) ** 2) / (2 * sx**2) + ((y - y0) ** 2) / (2 * sy**2)))


def refine_gaussian(image: np.ndarray, candidate: dict, window_radius: int) -> dict:
    patch, x_offset, y_offset = _window(image, candidate["x"], candidate["y"], window_radius)
    yy, xx = np.indices(patch.shape)
    initial = [
        float(np.max(patch) - np.min(patch)),
        candidate["x"] - x_offset,
        candidate["y"] - y_offset,
        max(candidate["sigma"], 0.7),
        max(candidate["sigma"], 0.7),
        float(np.min(patch)),
    ]
    try:
        popt, _ = curve_fit(
            _gaussian_2d,
            (xx.ravel(), yy.ravel()),
            patch.ravel(),
            p0=initial,
            bounds=(
                [0, 0, 0, 0.2, 0.2, -np.inf],
                [np.inf, patch.shape[1], patch.shape[0], window_radius * 2, window_radius * 2, np.inf],
            ),
            maxfev=1200,
        )
        fitted = _gaussian_2d((xx, yy), *popt)
        error = float(np.sqrt(np.mean((patch - fitted) ** 2)))
        amp, x0, y0, sx, sy, bg = [float(v) for v in popt]
        return {
            "id": int(candidate["id"]),
            "x_px": x0 + x_offset,
            "y_px": y0 + y_offset,
            "intensity": amp + bg,
            "sigma_x": sx,
            "sigma_y": sy,
            "ellipticity": float(max(sx, sy) / max(min(sx, sy), 1e-6)),
            "local_contrast": float(np.max(patch) - np.median(patch)),
            "fit_error": error,
            "confidence": confidence(float(candidate["response"]), error, float(max(sx, sy) / max(min(sx, sy), 1e-6))),
            "response": float(candidate["response"]),
        }
    except Exception:
        return refine_centroid(image, candidate, window_radius)


def confidence(response: float, fit_error: float, ellipticity: float) -> float:
    score = response
    score *= max(0.0, 1.0 - min(fit_error, 1.0))
    score *= max(0.25, 1.0 / max(ellipticity, 1.0))
    return float(np.clip(score, 0.0, 1.0))
