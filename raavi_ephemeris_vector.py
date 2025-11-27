import numpy as np
import swisseph as swe
from dataclasses import dataclass
from typing import Dict, List, Optional
# Import BODY_IDs and PyJhora-compatible tools from the scalar module.
# This works because raavi_ephemeris does NOT import this file at top-level anymore.
from raavi_ephemeris import BODY_IDS, BASE_FLAGS, SIDEREAL_EXTRA, RISE_FLAGS, ayanamsa_guard, AYANAMSA_DEFAULT

@dataclass
class LazySkyPosition:
    longitude: float
    latitude: float
    distance_au: float
    speed_lon: float

@dataclass
class LazySkyFrame:
    jd: float
    positions: Dict[str, LazySkyPosition]

    def get_position(self, body_name: str) -> LazySkyPosition:
        return self.positions[body_name]

@dataclass
class EphemerisBatch:
    jds: np.ndarray
    raw_results: np.ndarray 
    bodies: List[str]

    def get_frame(self, index: int) -> LazySkyFrame:
        jd = self.jds[index]
        lazy_positions: Dict[str, LazySkyPosition] = {}
        time_results = self.raw_results[index] 
        
        for i, body_name in enumerate(self.bodies):
            pos_data = time_results[i]
            lazy_positions[body_name] = LazySkyPosition(
                longitude=pos_data[0], latitude=pos_data[1],
                distance_au=pos_data[2], speed_lon=pos_data[3],
            )
        return LazySkyFrame(jd=jd, positions=lazy_positions)

class VectorizedProvider:
    def __init__(
        self,
        ephe_path: Optional[str] = None,
        bodies: Optional[List[str]] = None,
        sidereal: bool = False,
        ayanamsa: Optional[str] = None,
        node_mode: str = "mean",
        ketu_lat_mode: str = "pyjhora"
    ):
        self.bodies = bodies or list(BODY_IDS.keys())
        self.sidereal = sidereal
        self.ayanamsa = ayanamsa or AYANAMSA_DEFAULT
        self.node_mode = node_mode  # "mean" | "true"
        self.ketu_lat_mode = ketu_lat_mode  # "pyjhora" | "mirrored"

        # Set ephemeris path if provided
        if ephe_path:
            swe.set_ephe_path(ephe_path)

        # Configure flags PyJhora-style
        if self.sidereal:
            self.flags = BASE_FLAGS | SIDEREAL_EXTRA | RISE_FLAGS
        else:
            self.flags = BASE_FLAGS

        # Build body_ids list, handling Rahu specially and skipping Ketu
        self.body_ids = []
        self.body_names = []
        for body_name in self.bodies:
            if body_name == "Ketu":
                # Ketu will be calculated from Rahu, not fetched
                continue
            elif body_name == "Rahu":
                # Rahu ID will be determined by node_mode at calculation time
                self.body_names.append(body_name)
                self.body_ids.append(swe.MEAN_NODE if self.node_mode == "mean" else swe.TRUE_NODE)
            elif body_name in BODY_IDS:
                self.body_names.append(body_name)
                self.body_ids.append(BODY_IDS[body_name])

    def calculate_batch(self, jds: np.ndarray) -> EphemerisBatch:
        # Collect results in Python lists to avoid per-element NumPy assignment overhead.
        collected_data = []

        calc_ut = swe.calc_ut
        flags = self.flags

        # Use ayanamsa_guard for all calculations
        with ayanamsa_guard(self.sidereal, self.ayanamsa):
            for body_id in self.body_ids:
                body_results = [calc_ut(jd, body_id, flags)[0] for jd in jds]
                collected_data.append(body_results)

        # collected_data: (num_bodies, num_jds, 6)
        # We need: (num_jds, num_bodies, 6)
        raw_results = np.array(collected_data, dtype=np.float64).transpose(1, 0, 2)

        # Add Ketu if requested
        final_bodies = self.body_names.copy()
        if "Ketu" in self.bodies and "Rahu" in self.body_names:
            # Find Rahu index
            rahu_idx = self.body_names.index("Rahu")

            # Extract Rahu data: (num_jds, 6)
            rahu_data = raw_results[:, rahu_idx, :]

            # Calculate Ketu
            ketu_lon = (rahu_data[:, 0] + 180.0) % 360.0

            if self.ketu_lat_mode == "pyjhora":
                ketu_lat = rahu_data[:, 1]
            else:  # "mirrored"
                ketu_lat = -rahu_data[:, 1]

            # Build Ketu data array: (num_jds, 6)
            ketu_data = np.zeros_like(rahu_data)
            ketu_data[:, 0] = ketu_lon  # longitude
            ketu_data[:, 1] = ketu_lat  # latitude
            ketu_data[:, 2] = rahu_data[:, 2]  # distance
            ketu_data[:, 3] = rahu_data[:, 3]  # speed_lon

            # Append Ketu to results
            raw_results = np.concatenate([raw_results, ketu_data[:, np.newaxis, :]], axis=1)
            final_bodies.append("Ketu")

        return EphemerisBatch(jds=jds, raw_results=raw_results, bodies=final_bodies)

