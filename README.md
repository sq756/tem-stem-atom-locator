# TEM/STEM Atom Locator

TEM/STEM Atom Locator is a first-pass atom-column site detection workbench for high-resolution TEM/STEM images. It combines a Python image-processing core, a FastAPI backend, a React web UI, Docker deployment, and a SwiftUI macOS shell prototype.

The first version is deliberately principle-driven rather than neural-network-first: it detects local atomic-column candidates, supports ROI-based auto tuning, estimates periodic lattice vectors, fills likely missing sites, lets users manually correct the final points, and exports atom coordinates as CSV.

## Features

- Upload `.tif` / `.tiff` TEM/STEM images from the browser.
- Detect bright or dark atom-column candidates.
- Draw an ROI over a clear lattice region and run semi-automatic parameter tuning.
- Use periodic lattice estimation to recover missed atom sites.
- Mask bottom scale-bar/text regions and edge-connected black borders.
- Manually edit final points: add, drag, and delete sites.
- Export edited atom coordinates to CSV.
- Run locally with Python + Node, or deploy as a Docker web app.
- Use from Windows, macOS, Linux, tablets, or phones through a browser.

## Project Layout

```text
atom_locator/                  Python detection core
backend/                       FastAPI API and web server
web/                           React + Vite frontend
macos/AtomLocatorMac/          SwiftUI macOS shell prototype
scripts/                       Setup, run, and smoke-test scripts
experimental_data/raw_tif/     Local TIFF input folder, ignored by git
experimental_data/results/     Detection outputs, ignored by git
```

## Quick Start

Install dependencies:

```bash
./scripts/setup.sh
```

Start the backend:

```bash
./scripts/start_backend.sh
```

Start the web UI:

```bash
./scripts/start_web.sh
```

Open:

```text
http://127.0.0.1:5173/
```

## Typical Workflow

1. Upload a `.tif` or `.tiff` image.
2. Select bright-peak or dark-peak mode.
3. Draw an ROI around a clear lattice region.
4. Click `自动调参并检测`.
5. Inspect the overlay and mask.
6. Click `手动编辑`.
7. Add, drag, or delete final atom sites.
8. Click `导出编辑 CSV`.

Manual editing controls:

```text
Click empty image area: add a point
Drag a point: move it
Double-click a point: delete it
Export edited CSV: download final atom-site coordinates
```

CSV fields:

```text
site_id,x_px,y_px,intensity,confidence,filled,periodic_filled
```

`x_px` and `y_px` are pixel coordinates in the original image. Physical units can be added later if the pixel scale is known.

## Python CLI

Run one image:

```bash
.venv/bin/python -m atom_locator.cli experimental_data/raw_tif/example.tif \
  --output-root experimental_data/results
```

Run all TIFF images in the local input folder:

```bash
.venv/bin/python -m atom_locator.cli experimental_data/raw_tif \
  --output-root experimental_data/results
```

Each run writes:

```text
*_sites.json
*_sites.csv
*_overlay.png
*_preprocessed.png
*_mask.png
run_summary.json
```

## Docker Deployment

Docker runs the React frontend and FastAPI backend in one container on port `8000`.

Build and run:

```bash
docker compose up --build
```

Open locally:

```text
http://127.0.0.1:8000
```

On a lab LAN, other devices can open:

```text
http://SERVER_LAN_IP:8000
```

This is the easiest way to let Windows, macOS, Linux, tablets, and phones use the same tool through a browser.

## Sharing With Others

Option A: share source code.

```text
1. Push this repository to GitHub.
2. The other person installs Docker Desktop.
3. They run: docker compose up --build
4. They open: http://127.0.0.1:8000
```

Option B: share a Docker image.

```bash
docker build -t atom-locator:0.1 .
docker save atom-locator:0.1 -o atom-locator.tar
```

The recipient loads and runs it:

```bash
docker load -i atom-locator.tar
docker compose up
```

## GitHub Upload

Recommended: keep real TIFF data out of GitHub. The repository ignores:

```text
experimental_data/raw_tif/*
experimental_data/excluded_sem_tif/*
experimental_data/results/*
*.pdf
```

Create an empty repository on GitHub, then run:

```bash
git add .
git commit -m "Initial atom locator workbench"
git remote add origin https://github.com/YOUR_USER/tem-stem-atom-locator.git
git push -u origin main
```

If the default branch on GitHub is `master`, use:

```bash
git branch -M main
git push -u origin main
```

## Validation

Run:

```bash
./scripts/run_smoke.sh
```

The smoke test checks:

```text
Python module compilation
Single-image detection contract
Web production build
```

## macOS App Prototype

The SwiftUI source lives in:

```text
macos/AtomLocatorMac
```

It is a native shell that calls the same Python CLI. Full macOS app packaging requires a working full Xcode installation, code signing, and notarization. The current web/Docker version is the recommended way to share the tool broadly.

## Data Privacy

Uploaded images and generated results are stored locally under `experimental_data/`. They are not uploaded anywhere unless you deploy the server publicly or manually share the files.

## Current Limitations

- No neural-network segmentation yet.
- Physical coordinate export requires pixel scale metadata or user-provided calibration.
- Periodic filling is heuristic and should be checked with manual editing before final export.
- The macOS app is a prototype; the web/Docker workflow is currently more complete.
