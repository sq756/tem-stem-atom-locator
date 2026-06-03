from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import tifffile


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


def make_synthetic_tiff(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    height = 192
    width = 256
    yy, xx = np.mgrid[0:height, 0:width]
    image = np.full((height, width), 0.12, dtype=np.float32)
    for y in range(30, height - 25, 18):
        row_shift = 5 if (y // 18) % 2 else 0
        for x in range(28 + row_shift, width - 25, 18):
            image += 0.9 * np.exp(-(((xx - x) ** 2 + (yy - y) ** 2) / (2 * 2.2**2)))
    image += 0.04 * np.random.default_rng(42).normal(size=image.shape)
    image = np.clip(image, 0, 1)
    tifffile.imwrite(path, (image * 65535).astype(np.uint16))


def run_cli_contract() -> None:
    image = ROOT / "experimental_data" / "raw_tif" / "cyy.tif"
    if not image.exists():
        image = ROOT / "experimental_data" / "raw_tif" / "synthetic_smoke.tif"
        make_synthetic_tiff(image)
    output_root = ROOT / "experimental_data" / "results"
    command = [
        str(PYTHON),
        "-m",
        "atom_locator.cli",
        str(image),
        "--output-root",
        str(output_root),
        "--run-id",
        "smoke_test",
        "--threshold-rel",
        "0.12",
        "--min-distance",
        "6",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    summary = json.loads(completed.stdout.strip().splitlines()[-1])
    assert summary["image_count"] == 1
    assert summary["site_count"] > 0
    result = summary["results"][0]
    for key in ("json", "csv", "overlay", "preprocessed"):
        assert Path(result[key]).exists(), key
    payload = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
    for key in ("schema_version", "algorithm_version", "image", "parameters", "sites", "lattice", "outputs"):
        assert key in payload, key
    width = payload["image"]["width"]
    height = payload["image"]["height"]
    for site in payload["sites"]:
        assert 0 <= site["x_px"] < width
        assert 0 <= site["y_px"] < height


def main() -> None:
    run_cli_contract()
    print("smoke test passed")


if __name__ == "__main__":
    main()
