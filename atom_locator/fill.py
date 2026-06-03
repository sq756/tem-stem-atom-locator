from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def fill_lattice_gaps(
    image: np.ndarray,
    sites: list[dict],
    mask: np.ndarray,
    strength: float,
    iterations: int,
) -> list[dict]:
    if len(sites) < 20 or iterations <= 0:
        return sites
    filled = [dict(site) for site in sites]
    for _ in range(iterations):
        vectors = estimate_lattice_vectors(filled)
        if not vectors:
            break
        additions = propose_sites(image, filled, mask, vectors, strength)
        if not additions:
            break
        max_additions = max(50, int(len(filled) * 0.8))
        additions = additions[:max_additions]
        filled.extend(additions)
        for idx, site in enumerate(filled, start=1):
            site["id"] = idx
    return filled


def estimate_lattice_vectors(sites: list[dict]) -> list[np.ndarray]:
    coords = np.array([[site["x_px"], site["y_px"]] for site in sites], dtype=float)
    if len(coords) < 20:
        return []
    tree = cKDTree(coords)
    distances, indices = tree.query(coords, k=min(7, len(coords)))
    neighbor_vectors = []
    nearest = []
    for row_distances, row_indices, point in zip(distances, indices, coords, strict=False):
        for distance, index in zip(np.atleast_1d(row_distances)[1:], np.atleast_1d(row_indices)[1:], strict=False):
            if distance <= 0:
                continue
            nearest.append(float(distance))
            vec = coords[int(index)] - point
            if vec[0] < 0 or (abs(vec[0]) < 1e-6 and vec[1] < 0):
                vec = -vec
            neighbor_vectors.append(vec)
    if not neighbor_vectors:
        return []
    nn = float(np.median(nearest))
    vectors = []
    for vec in neighbor_vectors:
        length = float(np.linalg.norm(vec))
        if length < nn * 0.65 or length > nn * 1.45:
            continue
        angle = np.arctan2(vec[1], vec[0])
        if all(abs(angle_delta(angle, np.arctan2(v[1], v[0]))) > 0.30 for v in vectors):
            vectors.append(vec)
        if len(vectors) >= 4:
            break
    return vectors[:4]


def propose_sites(
    image: np.ndarray,
    sites: list[dict],
    mask: np.ndarray,
    vectors: list[np.ndarray],
    strength: float,
) -> list[dict]:
    coords = np.array([[site["x_px"], site["y_px"]] for site in sites], dtype=float)
    tree = cKDTree(coords)
    values = np.array([image[int(round(site["y_px"])), int(round(site["x_px"]))] for site in sites])
    threshold = max(float(np.percentile(values, 25)) * strength, 0.02)
    proposals = []
    for point in coords:
        for vec in vectors:
            for sign in (-1, 1):
                target = point + sign * vec
                x, y = float(target[0]), float(target[1])
                if x < 2 or y < 2 or x >= image.shape[1] - 2 or y >= image.shape[0] - 2:
                    continue
                if bool(mask[int(round(y)), int(round(x))]):
                    continue
                distance, _ = tree.query([x, y], k=1)
                if distance < max(3.0, float(np.linalg.norm(vec)) * 0.45):
                    continue
                refined = local_peak(image, x, y, radius=3)
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
                    }
                )
    return dedupe_proposals(proposals, coords, min_distance=4.0)


def local_peak(image: np.ndarray, x: float, y: float, radius: int):
    xi = int(round(x))
    yi = int(round(y))
    patch = image[yi - radius : yi + radius + 1, xi - radius : xi + radius + 1]
    if patch.size == 0:
        return None
    max_index = np.unravel_index(int(np.argmax(patch)), patch.shape)
    py = yi - radius + max_index[0]
    px = xi - radius + max_index[1]
    response = float(image[py, px])
    return float(px), float(py), response


def dedupe_proposals(proposals: list[dict], existing: np.ndarray, min_distance: float) -> list[dict]:
    accepted = []
    if len(existing):
        existing_tree = cKDTree(existing)
    else:
        existing_tree = None
    for proposal in sorted(proposals, key=lambda item: item["response"], reverse=True):
        point = np.array([proposal["x_px"], proposal["y_px"]], dtype=float)
        if existing_tree is not None and existing_tree.query(point, k=1)[0] < min_distance:
            continue
        if any(np.linalg.norm(point - np.array([p["x_px"], p["y_px"]])) < min_distance for p in accepted):
            continue
        accepted.append(proposal)
    return accepted


def angle_delta(a: float, b: float) -> float:
    return abs((a - b + np.pi / 2) % np.pi - np.pi / 2)
