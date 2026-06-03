from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DetectionParams:
    mode: str = "bright"
    sigma_min: float = 1.0
    sigma_max: float = 6.0
    num_sigma: int = 10
    threshold_rel: float = 0.08
    min_distance: int = 4
    background_sigma: float = 30.0
    refine_method: str = "centroid"
    refine_window: int = 7
    neighbors_k: int = 6
    mask_bottom_fraction: float = 0.10
    mask_dark_threshold: float = 0.03
    fill_lattice: bool = True
    fill_strength: float = 0.35
    fill_iterations: int = 1

    def to_dict(self) -> dict:
        return asdict(self)
