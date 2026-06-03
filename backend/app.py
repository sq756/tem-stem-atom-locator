from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from atom_locator import __version__
from atom_locator.autotune import autotune_params
from atom_locator.config import DetectionParams
from atom_locator.data_io import list_tiff_images, read_tiff_grayscale
from atom_locator.pipeline import run_detection, safe_stem
from atom_locator.preprocess import normalize_image
from atom_locator.visualize import save_preprocessed


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "experimental_data" / "raw_tif"
RESULTS_DIR = ROOT / "experimental_data" / "results"
WEB_DIST = ROOT / "web" / "dist"
RAW_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="TEM/STEM Atom Locator API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")


class DetectionRequest(BaseModel):
    image: str | None = Field(default=None, description="Image filename. Omit to process all images.")
    mode: Literal["bright", "dark"] = "bright"
    sigma_min: float = 1.0
    sigma_max: float = 6.0
    num_sigma: int = 10
    threshold_rel: float = 0.08
    min_distance: int = 4
    background_sigma: float = 30.0
    refine_method: Literal["centroid", "gaussian"] = "centroid"
    refine_window: int = 7
    neighbors_k: int = 6
    mask_bottom_fraction: float = 0.10
    mask_dark_threshold: float = 0.03
    fill_lattice: bool = True
    fill_strength: float = 0.35
    fill_iterations: int = 1

    def params(self) -> DetectionParams:
        return DetectionParams(
            mode=self.mode,
            sigma_min=self.sigma_min,
            sigma_max=self.sigma_max,
            num_sigma=self.num_sigma,
            threshold_rel=self.threshold_rel,
            min_distance=self.min_distance,
            background_sigma=self.background_sigma,
            refine_method=self.refine_method,
            refine_window=self.refine_window,
            neighbors_k=self.neighbors_k,
            mask_bottom_fraction=self.mask_bottom_fraction,
            mask_dark_threshold=self.mask_dark_threshold,
            fill_lattice=self.fill_lattice,
            fill_strength=self.fill_strength,
            fill_iterations=self.fill_iterations,
        )


class Roi(BaseModel):
    x: float
    y: float
    width: float
    height: float


class AutoTuneRequest(DetectionRequest):
    roi: Roi


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "algorithm_version": __version__,
        "raw_dir": str(RAW_DIR),
        "results_dir": str(RESULTS_DIR),
    }


@app.get("/api/images")
def images() -> dict:
    files = list_tiff_images(RAW_DIR)
    return {
        "images": [
            {"name": p.name, "size_bytes": p.stat().st_size, "path": str(p)}
            for p in files
        ]
    }


@app.post("/api/images/upload")
async def upload_image(file: UploadFile = File(...)) -> dict:
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in {".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="Only .tif/.tiff files are supported")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = unique_path(RAW_DIR / filename)
    with target.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    return {
        "image": {"name": target.name, "size_bytes": target.stat().st_size, "path": str(target)}
    }


@app.get("/api/images/{image_name}/preview")
def image_preview(image_name: str):
    image_path = resolve_image(image_name)
    preview_dir = RESULTS_DIR / "_previews"
    preview_path = preview_dir / f"{safe_stem(image_path)}_preview.png"
    if not preview_path.exists() or preview_path.stat().st_mtime < image_path.stat().st_mtime:
        raw_image, _ = read_tiff_grayscale(image_path)
        save_preprocessed(normalize_image(raw_image), preview_path)
    return FileResponse(preview_path)


@app.post("/api/runs")
def create_run(request: DetectionRequest) -> dict:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = RESULTS_DIR / run_id
    params = request.params()
    if request.image:
        image_paths = [resolve_image(request.image)]
    else:
        image_paths = list_tiff_images(RAW_DIR)
    results = [run_detection(path, output_dir, params) for path in image_paths]
    summary = {
        "run_id": run_id,
        "output_dir": str(output_dir),
        "image_count": len(results),
        "site_count": sum(len(result["sites"]) for result in results),
        "results": [
            {
                "image": result["image"]["name"],
                "image_key": safe_stem(Path(result["image"]["name"])),
                "site_count": len(result["sites"]),
                "json": f"/api/runs/{run_id}/results/{safe_stem(Path(result['image']['name']))}/json",
                "csv": f"/api/runs/{run_id}/results/{safe_stem(Path(result['image']['name']))}/csv",
                "overlay": f"/api/runs/{run_id}/results/{safe_stem(Path(result['image']['name']))}/overlay",
                "preprocessed": f"/api/runs/{run_id}/results/{safe_stem(Path(result['image']['name']))}/preprocessed",
                "mask": f"/api/runs/{run_id}/results/{safe_stem(Path(result['image']['name']))}/mask",
            }
            for result in results
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


@app.post("/api/autotune")
def autotune(request: AutoTuneRequest) -> dict:
    if not request.image:
        raise HTTPException(status_code=400, detail="Auto tune requires one image")
    image_path = resolve_image(request.image)
    tuning = autotune_params(image_path, request.roi.model_dump(), request.params())
    best = DetectionParams(**tuning["best_parameters"])
    run_id = datetime.now().strftime("autotune_%Y%m%d_%H%M%S")
    output_dir = RESULTS_DIR / run_id
    result = run_detection(image_path, output_dir, best, periodic_roi=tuning["roi"])
    if len(result["sites"]) < 20:
        best = replace(best, threshold_rel=min(best.threshold_rel, 0.08), mask_dark_threshold=0.0)
        tuning["best_parameters"] = best.to_dict()
        tuning["fallback_applied"] = "lower_threshold_disable_dark_mask"
        result = run_detection(image_path, output_dir, best, periodic_roi=tuning["roi"])
    image_key = safe_stem(Path(result["image"]["name"]))
    summary = {
        "run_id": run_id,
        "output_dir": str(output_dir),
        "image_count": 1,
        "site_count": len(result["sites"]),
        "autotune": tuning,
        "results": [
            {
                "image": result["image"]["name"],
                "image_key": image_key,
                "site_count": len(result["sites"]),
                "json": f"/api/runs/{run_id}/results/{image_key}/json",
                "csv": f"/api/runs/{run_id}/results/{image_key}/csv",
                "overlay": f"/api/runs/{run_id}/results/{image_key}/overlay",
                "preprocessed": f"/api/runs/{run_id}/results/{image_key}/preprocessed",
                "mask": f"/api/runs/{run_id}/results/{image_key}/mask",
            }
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


@app.get("/api/runs/{run_id}")
def run_summary(run_id: str) -> dict:
    path = RESULTS_DIR / run_id / "run_summary.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/runs/{run_id}/results/{image_key}/{artifact}")
def run_artifact(run_id: str, image_key: str, artifact: str):
    suffix = {
        "json": "_sites.json",
        "csv": "_sites.csv",
        "overlay": "_overlay.png",
        "preprocessed": "_preprocessed.png",
        "mask": "_mask.png",
    }.get(artifact)
    if suffix is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = RESULTS_DIR / run_id / f"{image_key}{suffix}"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)


def resolve_image(image_name: str) -> Path:
    image_path = (RAW_DIR / image_name).resolve()
    raw_root = RAW_DIR.resolve()
    if raw_root not in image_path.parents or image_path.suffix.lower() not in {".tif", ".tiff"}:
        raise HTTPException(status_code=404, detail="Image not found")
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return image_path


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise HTTPException(status_code=500, detail="Could not create unique upload filename")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    index = WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Web build not found")
