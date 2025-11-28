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
        self.sidereal = sidereal
        self.ayanamsa = ayanamsa
        self.node_mode = node_mode
        self.ketu_lat_mode = ketu_lat_mode

        # Build calculation list: exclude Ketu (synthesized), handle Rahu node mode
        # Ensure Rahu is calculated if Ketu is requested
        calc_bodies_set = set()
        for b in self.bodies:
            if b == "Ketu":
                # Ketu is synthesized from Rahu
                calc_bodies_set.add("Rahu")
            elif b != "Ketu":
                calc_bodies_set.add(b)

        # Map to swisseph IDs, preserving order
        self.body_ids = []
        self._calc_body_names = []
        for b in self.bodies:
            # Skip Ketu in calculation, it will be synthesized
            if b == "Ketu":
                continue
            # Handle Rahu node mode
            if b == "Rahu":
                body_id = swe.MEAN_NODE if self.node_mode == "mean" else swe.TRUE_NODE
            else:
                body_id = BODY_IDS.get(b)

            if body_id is not None:
                self.body_ids.append(body_id)
                self._calc_body_names.append(b)

        # If Ketu requested but Rahu not in bodies, add Rahu to calculation
        if "Ketu" in self.bodies and "Rahu" not in self.bodies:
            rahu_id = swe.MEAN_NODE if self.node_mode == "mean" else swe.TRUE_NODE
            self.body_ids.append(rahu_id)
            self._calc_body_names.append("Rahu")

        if ephe_path:
            swe.set_ephe_path(ephe_path)
        self.flags = BASE_FLAGS
        if self.sidereal:
            self.flags |= SIDEREAL_EXTRA
        # RISE_FLAGS removed from general position calculation
        # They should only be used in rise/set calculations (panchanga_engine)

    def calculate_batch(self, jds: np.ndarray) -> EphemerisBatch:
        # Collect results in Python lists to avoid per-element NumPy assignment overhead.
        collected_data = []

        calc_ut = swe.calc_ut
        flags = self.flags

        with ayanamsa_guard(self.sidereal, self.ayanamsa):
            for body_id in self.body_ids:
                body_results = [calc_ut(jd, body_id, flags)[0] for jd in jds]
                collected_data.append(body_results)

        # collected_data: (num_bodies_calc, num_jds, 6)
        # We need: (num_jds, num_bodies_calc, 6)
        raw_results_calc = np.array(collected_data, dtype=np.float64).transpose(1, 0, 2)

        # Now synthesize Ketu if requested
        if "Ketu" in self.bodies:
            # Find Rahu index in calculated bodies
            try:
                rahu_idx = self._calc_body_names.index("Rahu")
            except ValueError:
                raise RuntimeError("Ketu requested but Rahu not calculated")

            # Extract Rahu data: (num_jds, 6)
            rahu_data = raw_results_calc[:, rahu_idx, :]

            # Synthesize Ketu
            # Ketu longitude = (Rahu longitude + 180) % 360
            ketu_data = rahu_data.copy()
            ketu_data[:, 0] = (rahu_data[:, 0] + 180.0) % 360.0  # longitude
            # Latitude: PyJHora mode keeps same sign, standard mode inverts
            if self.ketu_lat_mode == "pyjhora":
                ketu_data[:, 1] = rahu_data[:, 1]
            else:
                ketu_data[:, 1] = -rahu_data[:, 1]
            # Distance and speed same as Rahu
            # ketu_data[:, 2:] already copied

            # Build final results with Ketu inserted at correct position
            final_bodies = []
            final_data_list = []
            calc_idx = 0

            for body_name in self.bodies:
                if body_name == "Ketu":
                    final_bodies.append("Ketu")
                    final_data_list.append(ketu_data)
                else:
                    final_bodies.append(body_name)
                    final_data_list.append(raw_results_calc[:, calc_idx, :])
                    calc_idx += 1

            # Stack into final array: (num_jds, num_bodies, 6)
            raw_results = np.stack(final_data_list, axis=1)
        else:
            raw_results = raw_results_calc
            final_bodies = self._calc_body_names

        return EphemerisBatch(jds=jds, raw_results=raw_results, bodies=final_bodies)

