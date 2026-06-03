from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile


TIFF_EXTENSIONS = {".tif", ".tiff"}


def list_tiff_images(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() in TIFF_EXTENSIONS:
        return [path]
    if not path.exists():
        raise FileNotFoundError(path)
    return sorted(
        p for p in path.iterdir() if p.is_file() and p.suffix.lower() in TIFF_EXTENSIONS
    )


def read_tiff_grayscale(path: Path) -> tuple[np.ndarray, dict]:
    arr = tifffile.imread(path)
    arr = np.asarray(arr)
    if arr.ndim > 2:
        if arr.shape[-1] in (3, 4):
            arr = arr[..., :3].mean(axis=-1)
        else:
            arr = arr.reshape((-1,) + arr.shape[-2:])[0]
    image = arr.astype(np.float32, copy=False)
    meta = {
        "path": str(path),
        "name": path.name,
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "dtype": str(arr.dtype),
    }
    return image, meta
