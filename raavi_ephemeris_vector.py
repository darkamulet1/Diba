import numpy as np
import swisseph as swe
from dataclasses import dataclass
from typing import Dict, List, Optional
from raavi_ephemeris import (
    BODY_IDS,
    BASE_FLAGS,
    SIDEREAL_EXTRA,
    RISE_FLAGS,
    ayanamsa_guard,
    compute_jd_pair,
)

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
        ayanamsa: str = "LAHIRI",
        node_mode: str = "mean",
        ketu_lat_mode: str = "pyjhora",
    ):
        self.bodies = bodies or list(BODY_IDS.keys())
        self.body_ids = [BODY_IDS[b] for b in self.bodies]
        self.sidereal = sidereal
        self.ayanamsa = ayanamsa
        self.node_mode = node_mode
        self.ketu_lat_mode = ketu_lat_mode
        if ephe_path:
            swe.set_ephe_path(ephe_path)
        self.flags = BASE_FLAGS
        if self.sidereal:
            self.flags |= SIDEREAL_EXTRA | RISE_FLAGS

    def calculate_batch(self, jds: np.ndarray) -> EphemerisBatch:
        # Collect results in Python lists to avoid per-element NumPy assignment overhead.
        collected_data = []

        calc_ut = swe.calc_ut
        flags = self.flags

        with ayanamsa_guard(self.sidereal, self.ayanamsa):
            for body_id in self.body_ids:
                body_results = [calc_ut(jd, body_id, flags)[0] for jd in jds]
                collected_data.append(body_results)

        # collected_data: (num_bodies, num_jds, 6)
        # We need: (num_jds, num_bodies, 6)
        raw_results = np.array(collected_data, dtype=np.float64).transpose(1, 0, 2)

        return EphemerisBatch(jds=jds, raw_results=raw_results, bodies=self.bodies)

