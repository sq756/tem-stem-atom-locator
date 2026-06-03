from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import DetectionParams
from .data_io import read_tiff_grayscale
from .detect import detect_candidates
from .export import save_json, save_sites_csv
from .fill import fill_lattice_gaps
from .graph import attach_neighbors
from .mask import exclusion_mask, filter_sites_by_mask
from .periodic import periodic_fill
from .preprocess import preprocess_image
from .refine import refine_candidates
from .visualize import save_mask_overlay, save_overlay, save_preprocessed


def run_detection(
    image_path: Path,
    output_dir: Path,
    params: DetectionParams,
    periodic_roi: dict | None = None,
) -> dict:
    image_path = image_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_image, image_meta = read_tiff_grayscale(image_path)
    preprocessed, normalized = preprocess_image(raw_image, params)
    candidates = detect_candidates(preprocessed, params)
    sites = refine_candidates(preprocessed, candidates, params)
    mask = exclusion_mask(normalized, params.mask_bottom_fraction, params.mask_dark_threshold)
    sites = filter_sites_by_mask(sites, mask)
    detected_count = len(sites)
    if params.fill_lattice:
        sites = fill_lattice_gaps(preprocessed, sites, mask, params.fill_strength, params.fill_iterations)
    local_fill_count = len(sites) - detected_count
    periodic_model = None
    periodic_start_count = len(sites)
    if periodic_roi is not None:
        sites, periodic_model = periodic_fill(preprocessed, sites, mask, periodic_roi, params.fill_strength)
    lattice = attach_neighbors(sites, params.neighbors_k)

    stem = safe_stem(image_path)
    json_path = output_dir / f"{stem}_sites.json"
    csv_path = output_dir / f"{stem}_sites.csv"
    overlay_path = output_dir / f"{stem}_overlay.png"
    preprocessed_path = output_dir / f"{stem}_preprocessed.png"
    mask_path = output_dir / f"{stem}_mask.png"

    save_preprocessed(preprocessed, preprocessed_path)
    save_overlay(normalized, sites, overlay_path)
    save_mask_overlay(normalized, mask, mask_path)

    payload = {
        "schema_version": 1,
        "algorithm_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "image": image_meta,
        "mode": params.mode,
        "parameters": params.to_dict(),
        "sites": sites,
        "lattice": {
            **lattice,
            "detected_site_count": detected_count,
            "filled_site_count": len(sites) - detected_count,
            "local_filled_site_count": local_fill_count,
            "periodic_filled_site_count": len(sites) - periodic_start_count,
            "periodic_model": periodic_model,
        },
        "outputs": {
            "json": str(json_path),
            "csv": str(csv_path),
            "overlay": str(overlay_path),
            "preprocessed": str(preprocessed_path),
            "mask": str(mask_path),
        },
    }
    save_sites_csv(sites, csv_path)
    save_json(payload, json_path)
    return payload


def safe_stem(path: Path) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in path.stem)
