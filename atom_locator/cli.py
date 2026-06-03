from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .config import DetectionParams
from .data_io import list_tiff_images
from .pipeline import run_detection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect atom column sites in TEM/STEM TIFF images.")
    parser.add_argument("input", type=Path, help="Input TIFF file or directory.")
    parser.add_argument("--output-root", type=Path, default=Path("experimental_data/results"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--mode", choices=["bright", "dark"], default="bright")
    parser.add_argument("--sigma-min", type=float, default=1.0)
    parser.add_argument("--sigma-max", type=float, default=6.0)
    parser.add_argument("--num-sigma", type=int, default=10)
    parser.add_argument("--threshold-rel", type=float, default=0.08)
    parser.add_argument("--min-distance", type=int, default=4)
    parser.add_argument("--background-sigma", type=float, default=30.0)
    parser.add_argument("--refine-method", choices=["centroid", "gaussian"], default="centroid")
    parser.add_argument("--refine-window", type=int, default=7)
    parser.add_argument("--neighbors-k", type=int, default=6)
    return parser


def params_from_args(args: argparse.Namespace) -> DetectionParams:
    return DetectionParams(
        mode=args.mode,
        sigma_min=args.sigma_min,
        sigma_max=args.sigma_max,
        num_sigma=args.num_sigma,
        threshold_rel=args.threshold_rel,
        min_distance=args.min_distance,
        background_sigma=args.background_sigma,
        refine_method=args.refine_method,
        refine_window=args.refine_window,
        neighbors_k=args.neighbors_k,
    )


def main() -> None:
    args = build_parser().parse_args()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_root / run_id
    params = params_from_args(args)
    images = list_tiff_images(args.input)
    results = [run_detection(image, output_dir, params) for image in images]
    summary = {
        "run_id": run_id,
        "output_dir": str(output_dir),
        "image_count": len(results),
        "site_count": sum(len(result["sites"]) for result in results),
        "results": [
            {
                "image": result["image"]["name"],
                "site_count": len(result["sites"]),
                "json": result["outputs"]["json"],
                "csv": result["outputs"]["csv"],
                "overlay": result["outputs"]["overlay"],
                "preprocessed": result["outputs"]["preprocessed"],
                "mask": result["outputs"]["mask"],
            }
            for result in results
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
