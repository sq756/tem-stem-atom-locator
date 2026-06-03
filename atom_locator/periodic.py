from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from .fill import dedupe_proposals, local_peak


def estimate_periodic_model(sites: list[dict], roi: dict) -> dict | None:
    roi_sites = [
        site
        for site in sites
        if roi["x"] <= site["x_px"] <= roi["x"] + roi["width"]
        and roi["y"] <= site["y_px"] <= roi["y"] + roi["height"]
    ]
    if len(roi_sites) < 20:
        return None
    coords = np.array([[site["x_px"], site["y_px"]] for site in roi_sites], dtype=float)
    vectors = neighbor_vectors(coords)
    if len(vectors) < 2:
        return None
    a, b = choose_basis(vectors)
    if a is None or b is None:
        return None
    origin = choose_origin(coords)
    return {
        "origin": [float(origin[0]), float(origin[1])],
        "vectors": [[float(a[0]), float(a[1])], [float(b[0]), float(b[1])]],
        "roi_site_count": len(roi_sites),
    }


def periodic_fill(
    image: np.ndarray,
    sites: list[dict],
    mask: np.ndarray,
    roi: dict,
    strength: float,
) -> tuple[list[dict], dict | None]:
    model = estimate_periodic_model(sites, roi)
    if model is None:
        return sites, None
    coords = np.array([[site["x_px"], site["y_px"]] for site in sites], dtype=float)
    values = np.array([site.get("response", site.get("confidence", 0.0)) for site in sites], dtype=float)
    threshold = max(float(np.percentile(values, 20)) * max(strength * 0.75, 0.08), 0.015)
    proposals = []
    origin = np.array(model["origin"], dtype=float)
    basis = np.array(model["vectors"], dtype=float).T
    try:
        inverse = np.linalg.inv(basis)
    except np.linalg.LinAlgError:
        return sites, model
    corners = np.array(
        [
            [0, 0],
            [image.shape[1], 0],
            [0, image.shape[0]],
            [image.shape[1], image.shape[0]],
        ],
        dtype=float,
    )
    ij = (inverse @ (corners - origin).T).T
    i_min, j_min = np.floor(ij.min(axis=0)).astype(int) - 3
    i_max, j_max = np.ceil(ij.max(axis=0)).astype(int) + 3
    for i in range(i_min, i_max + 1):
        for j in range(j_min, j_max + 1):
            target = origin + basis @ np.array([i, j], dtype=float)
            x, y = float(target[0]), float(target[1])
            if x < 3 or y < 3 or x >= image.shape[1] - 3 or y >= image.shape[0] - 3:
                continue
            if bool(mask[int(round(y)), int(round(x))]):
                continue
            refined = local_peak(image, x, y, radius=4)
            if refined is None:
                continue
            rx, ry, response = refined
            if response < threshold:
                continue
            proposals.append(
                {
                    "id": 0,
                    "x_px": rx,
                    "y_px": ry,
                    "intensity": response,
                    "sigma_x": 1.0,
                    "sigma_y": 1.0,
                    "ellipticity": 1.0,
                    "local_contrast": response,
                    "fit_error": 0.0,
                    "confidence": float(np.clip(response, 0.0, 1.0)),
                    "response": response,
                    "filled": True,
                    "periodic_filled": True,
                }
            )
    min_distance = max(3.0, 0.35 * min(np.linalg.norm(basis[:, 0]), np.linalg.norm(basis[:, 1])))
    additions = dedupe_proposals(proposals, coords, min_distance=min_distance)
    max_additions = max(100, int(len(sites) * 1.2))
    filled = [dict(site) for site in sites] + additions[:max_additions]
    filled = merge_close_sites(filled, min_distance=min_distance)
    for idx, site in enumerate(filled, start=1):
        site["id"] = idx
    model["generated_candidate_count"] = len(proposals)
    model["accepted_periodic_count"] = len(filled) - len(sites)
    return filled, model


def neighbor_vectors(coords: np.ndarray) -> list[np.ndarray]:
    tree = cKDTree(coords)
    distances, indices = tree.query(coords, k=min(9, len(coords)))
    vectors = []
    nearest = np.median(np.atleast_1d(distances)[:, 1:4])
    for point, row_distances, row_indices in zip(coords, distances, indices, strict=False):
        for distance, index in zip(row_distances[1:], row_indices[1:], strict=False):
            if distance < nearest * 0.65 or distance > nearest * 1.8:
                continue
            vec = coords[int(index)] - point
            if vec[0] < 0 or (abs(vec[0]) < 1e-6 and vec[1] < 0):
                vec = -vec
            vectors.append(vec)
    return vectors


def choose_basis(vectors: list[np.ndarray]) -> tuple[np.ndarray | None, np.ndarray | None]:
    clusters: list[list[np.ndarray]] = []
    for vec in vectors:
        angle = np.arctan2(vec[1], vec[0])
        placed = False
        for cluster in clusters:
            ref = np.mean(cluster, axis=0)
            if angle_delta(angle, np.arctan2(ref[1], ref[0])) < 0.18:
                cluster.append(vec)
                placed = True
                break
        if not placed:
            clusters.append([vec])
    cluster_means = [np.mean(cluster, axis=0) for cluster in clusters if len(cluster) >= 6]
    cluster_means.sort(key=lambda v: np.linalg.norm(v))
    for i, a in enumerate(cluster_means):
        for b in cluster_means[i + 1 :]:
            area = abs(np.cross(a, b))
            if area < 0.35 * np.linalg.norm(a) * np.linalg.norm(b):
                continue
            return a, b
    return None, None


def choose_origin(coords: np.ndarray) -> np.ndarray:
    target = np.array([coords[:, 0].min(), coords[:, 1].min()])
    return coords[np.argmin(np.linalg.norm(coords - target, axis=1))]


def merge_close_sites(sites: list[dict], min_distance: float) -> list[dict]:
    if len(sites) < 2:
        return sites
    ordered = sorted(sites, key=lambda site: site.get("response", site.get("confidence", 0.0)), reverse=True)
    accepted: list[dict] = []
    for site in ordered:
        point = np.array([site["x_px"], site["y_px"]], dtype=float)
        if any(
            np.linalg.norm(point - np.array([other["x_px"], other["y_px"]], dtype=float)) < min_distance
            for other in accepted
        ):
            continue
        accepted.append(site)
    return accepted


def angle_delta(a: float, b: float) -> float:
    return abs((a - b + np.pi / 2) % np.pi - np.pi / 2)
