from typing import Dict, List, Optional, Tuple
import numpy as np

from raavi_ephemeris import SkyFrame, SkyPosition  # type: ignore
from raavi_ephemeris_vector import EphemerisBatch  # type: ignore

# Aspect name -> exact angle in degrees
DEFAULT_ASPECTS: Dict[str, float] = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}


def _normalize_longitude(lon: float) -> float:
    """Normalize any longitude to [0, 360)."""
    return lon % 360.0


def _angle_difference(a: float, b: float) -> float:
    """
    Smallest signed angular difference a - b in [-180, 180].

    Positive means 'a is ahead of b' on the zodiac, negative means behind.
    """
    diff = (a - b + 180.0) % 360.0 - 180.0
    return diff


def compute_aspects_for_frame(
    frame: SkyFrame,
    bodies: Optional[List[str]] = None,
    aspects: Optional[Dict[str, float]] = None,
    orb: float = 3.0,
) -> Dict[str, Dict[Tuple[str, str], float]]:
    """
    Compute aspects for a single SkyFrame (scalar engine).

    Returns:
        dict[aspect_name][(body_a, body_b)] = delta_angle
        where delta_angle is the signed deviation from the exact aspect angle,
        e.g. +1.2 means 1.2 degrees past exact.
    """
    aspects_def = aspects or DEFAULT_ASPECTS
    body_list = bodies or list(frame.positions.keys())

    # Extract longitudes and normalize
    longitudes: Dict[str, float] = {}
    for name in body_list:
        pos: SkyPosition = frame.positions[name]
        longitudes[name] = _normalize_longitude(pos.lon)

    result: Dict[str, Dict[Tuple[str, str], float]] = {
        name: {} for name in aspects_def.keys()
    }

    for i, a in enumerate(body_list):
        for j, b in enumerate(body_list):
            if j <= i:
                continue  # avoid duplicates and self pairs
            angle = _angle_difference(longitudes[a], longitudes[b])
            abs_angle = abs(angle)

            for asp_name, asp_angle in aspects_def.items():
                delta = abs_angle - asp_angle
                if abs(delta) <= orb:
                    # Store signed deviation from exact aspect
                    result[asp_name][(a, b)] = angle - np.sign(angle) * asp_angle if asp_angle > 0 else angle

    return result


def compute_aspects_for_batch(
    batch: EphemerisBatch,
    bodies: Optional[List[str]] = None,
    aspects: Optional[Dict[str, float]] = None,
    orb: float = 3.0,
) -> Dict[str, np.ndarray]:
    """
    Compute aspects over time for a full EphemerisBatch (vector engine).

    Returns:
        dict[aspect_name] -> bool array of shape (N_time, N_body, N_body)
        where entry [t, i, j] is True if body i and j form that aspect at time t
        within the given orb.
    """
    aspects_def = aspects or DEFAULT_ASPECTS
    bnames = bodies or batch.bodies

    # Map requested bodies to indices in the batch
    body_indices = [batch.bodies.index(name) for name in bnames]
    N_time = batch.jds.shape[0]
    N_body = len(body_indices)

    # Extract longitudes: (T, B)
    # raw_results shape: (T, full_B, 6) -> we take index 0 = lon
    lon_full = batch.raw_results[:, :, 0]
    lon = lon_full[:, body_indices]  # (T, B)
    lon = np.mod(lon, 360.0)

    # Compute pairwise angle differences using broadcasting
    # lon[..., None] shape: (T, B, 1)
    # lon[:, None, :] shape: (T, 1, B)
    diff = (lon[..., None] - lon[:, None, :])  # (T, B, B)
    # Normalize to [-180, 180]
    diff = (diff + 180.0) % 360.0 - 180.0
    abs_diff = np.abs(diff)

    masks: Dict[str, np.ndarray] = {}
    for asp_name, asp_angle in aspects_def.items():
        target = asp_angle
        # For conjunction (0 deg), just check abs(angle) <= orb
        if target == 0.0:
            mask = abs_diff <= orb
        else:
            mask = np.abs(abs_diff - target) <= orb
        # Zero out diagonal (self-self)
        mask = mask & ~np.eye(N_body, dtype=bool)[None, :, :]
        masks[asp_name] = mask

    return masks

