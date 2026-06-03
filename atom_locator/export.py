from __future__ import annotations

import csv
import json
from pathlib import Path


CSV_FIELDS = [
    "site_id",
    "x_px",
    "y_px",
    "intensity",
    "sigma_x",
    "sigma_y",
    "ellipticity",
    "local_contrast",
    "fit_error",
    "confidence",
    "nearest_neighbor_distance",
    "neighbor_ids",
]


def save_sites_csv(sites: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for site in sites:
            writer.writerow(
                {
                    "site_id": site["id"],
                    "x_px": site["x_px"],
                    "y_px": site["y_px"],
                    "intensity": site["intensity"],
                    "sigma_x": site["sigma_x"],
                    "sigma_y": site["sigma_y"],
                    "ellipticity": site["ellipticity"],
                    "local_contrast": site["local_contrast"],
                    "fit_error": site["fit_error"],
                    "confidence": site["confidence"],
                    "nearest_neighbor_distance": site.get("nearest_neighbor_distance"),
                    "neighbor_ids": " ".join(str(n) for n in site.get("neighbors", [])),
                }
            )


def save_json(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
