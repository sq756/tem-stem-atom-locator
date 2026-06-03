from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def attach_neighbors(sites: list[dict], neighbors_k: int) -> dict:
    if not sites:
        return {
            "nearest_neighbor_distance_px": None,
            "distance_mean_px": None,
            "distance_std_px": None,
            "site_count": 0,
        }
    coords = np.array([[s["x_px"], s["y_px"]] for s in sites], dtype=float)
    if len(sites) == 1:
        sites[0]["neighbors"] = []
        sites[0]["nearest_neighbor_distance"] = None
        return {
            "nearest_neighbor_distance_px": None,
            "distance_mean_px": None,
            "distance_std_px": None,
            "site_count": 1,
        }
    tree = cKDTree(coords)
    k = min(neighbors_k + 1, len(sites))
    distances, indices = tree.query(coords, k=k)
    nearest = []
    for i, site in enumerate(sites):
        row_distances = np.atleast_1d(distances[i])[1:]
        row_indices = np.atleast_1d(indices[i])[1:]
        site["neighbors"] = [int(sites[int(j)]["id"]) for j in row_indices]
        nn = float(row_distances[0]) if len(row_distances) else None
        site["nearest_neighbor_distance"] = nn
        if nn is not None:
            nearest.append(nn)
    nearest_array = np.array(nearest, dtype=float)
    return {
        "nearest_neighbor_distance_px": float(np.median(nearest_array)) if len(nearest_array) else None,
        "distance_mean_px": float(np.mean(nearest_array)) if len(nearest_array) else None,
        "distance_std_px": float(np.std(nearest_array)) if len(nearest_array) else None,
        "site_count": len(sites),
    }
