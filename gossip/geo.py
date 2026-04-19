"""Pairwise geographic distance helpers for gossip simulation."""
from __future__ import annotations

import numpy as np


def haversine_matrix_km(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Pairwise great-circle distance (km) for arrays of lat/lon (degrees)."""
    rlat = np.radians(lat)
    rlon = np.radians(lon)
    dphi = rlat[:, None] - rlat[None, :]
    dlmb = rlon[:, None] - rlon[None, :]
    a = (
        np.sin(dphi / 2) ** 2
        + np.cos(rlat)[:, None] * np.cos(rlat)[None, :] * np.sin(dlmb / 2) ** 2
    )
    return 2 * 6371.0 * np.arcsin(np.clip(np.sqrt(a), 0.0, 1.0))
