import json
from datetime import datetime
from typing import Dict, Any, Optional
import pytz

from raavi_ephemeris import get_default_provider, TimeLocation
from logic.nakshatras import get_nakshatra_scalar
from logic.dashas import calculate_vimshottari
from logic.aspects import compute_aspects_for_frame
from logic.varga_engine import calculate_all_vargas
from logic import maitri, strengths, shadbala


class ChartCalculator:
    def __init__(self, *, sidereal: bool = False, ayanamsa: str = "LAHIRI"):
        # Scalar provider with houses (Placidus by default)
        self.provider = get_default_provider(
            calculate_houses=True,
            house_system="P",
            sidereal=sidereal,
            ayanamsa=ayanamsa,
        )

    def _json_default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def calculate_json(
        self,
        dt_utc: datetime,
        lat: float,
        lon: float,
        name: str = "Unknown",
    ) -> str:
        data = self.calculate_dict(dt_utc, lat, lon, name)
        return json.dumps(data, default=self._json_default, indent=2)

    def calculate_dict(
        self,
        dt_utc: datetime,
        lat: float,
        lon: float,
        name: str = "Unknown",
    ) -> Dict[str, Any]:
        # 1) Build TimeLocation and SkyFrame
        tl = TimeLocation(dt_utc=dt_utc, latitude=lat, longitude=lon)
        frame = self.provider.get_sky_frame(tl)

        # 2) Bodies: positions + zodiac + nakshatra
        bodies_data: Dict[str, Any] = {}
        moon_lon: Optional[float] = None
        planet_signs_d1: Dict[str, int] = {}
        d1_longitudes: Dict[str, float] = {}

        for body_name, pos in frame.positions.items():
            # Normalize longitude safely
            norm_lon = pos.lon % 360.0
            sign_idx = int(norm_lon // 30.0)
            degree_in_sign = norm_lon % 30.0

            # Nakshatra
            nak_idx, nak_name, nak_pada = get_nakshatra_scalar(norm_lon)

            # Speed / retrograde check safe for None
            speed = pos.speed_lon if pos.speed_lon is not None else 0.0
            retro = speed < 0.0

            bodies_data[body_name] = {
                "longitude": round(norm_lon, 4),
                "raw_longitude": round(pos.lon, 4),
                "speed": round(speed, 5),
                "retrograde": retro,
                "zodiac_sign": int(sign_idx),
                "degree_in_sign": round(degree_in_sign, 4),
                "nakshatra": {
                    "index": int(nak_idx),
                    "name": nak_name,
                    "pada": int(nak_pada),
                },
            }

            if body_name == "Moon":
                moon_lon = norm_lon
            if body_name in maitri.PLANETS:
                planet_signs_d1[body_name] = int(sign_idx)
            d1_longitudes[body_name] = norm_lon

        # 3) Vargas (divisional charts from D1)
        vargas = calculate_all_vargas(d1_longitudes)

        # 4) Dashas (Vimshottari)
        dashas_data = []
        if moon_lon is not None:
            dashas_list = calculate_vimshottari(moon_lon, dt_utc, total_years=120)
            for d in dashas_list:
                dashas_data.append(
                    {
                        "lord": d.lord,
                        "start": d.start_date,
                        "end": d.end_date,
                        "duration_years": round(d.duration_years, 2),
                    }
                )

        # 5) Aspects (simple set: conj/square/trine/opposition with orb)
        raw_aspects = compute_aspects_for_frame(frame, orb=5.0)
        aspects_data = []
        for aspect_type, pairs in raw_aspects.items():
            for (p1, p2), angle_err in pairs.items():
                aspects_data.append(
                    {
                        "type": aspect_type,
                        "body_a": p1,
                        "body_b": p2,
                        "orb_error": round(angle_err, 2),
                    }
                )

        # 6) Maitri & Vimsopaka (D1-based)
        compound_maitri = maitri.compute_compound_maitri(planet_signs_d1)
        vimsopaka_scores = strengths.calculate_vimsopaka_score(planet_signs_d1)

        # 7) Multi-varga weighted Vimsopaka using real vargas
        vimsopaka_weighted: Dict[str, Dict[str, float]] = {}
        for planet in maitri.PLANETS:
            varga_positions: Dict[int, int] = {}
            for varga_name, per_planet in vargas.items():
                info = per_planet.get(planet)
                if info is None:
                    continue
                try:
                    factor = int(varga_name[1:])
                except ValueError:
                    continue
                varga_positions[factor] = int(info["sign"])
            if not varga_positions:
                continue
            vimsopaka_weighted[planet] = strengths.calculate_weighted_vimsopaka_for_planet(
                planet,
                varga_positions=varga_positions,
                compound_maitri_d1=compound_maitri,
            )

        # 8) Shadbala (Phase 7+ implementation with full Sthana Bala)
        shadbala_components_raw = shadbala.calculate_shadbala_for_frame(
            frame,
            vargas=vargas,
            compound_maitri=compound_maitri,
        )

        # 9) Assemble final structure
        shadbala_components = {
            planet: {
                "sthana": comp.sthana,
                "dig": comp.dig,
                "kaala": comp.kaala,
                "chesta": comp.chesta,
                "naisargika": comp.naisargika,
                "drik": comp.drik,
                "total": comp.total,
            }
            for planet, comp in shadbala_components_raw.items()
        }

        shadbala_summary = shadbala.summarize_shadbala(shadbala_components_raw)
        shadbala_overview = shadbala.classify_shadbala(shadbala_summary)

        return {
            "meta": {
                "name": name,
                "datetime_utc": dt_utc,
                "latitude": lat,
                "longitude": lon,
                "ayanamsa": "Lahiri (dev: Moshier if no ephe_path)",
                "jd": frame.jd,
            },
            "houses": frame.houses,
            "bodies": bodies_data,
            "vargas": vargas,
            "maitri": {
                "compound": compound_maitri,
                "vimsopaka_d1": vimsopaka_scores,
                "vimsopaka_weighted": vimsopaka_weighted,
            },
            # Detailed per-component Shadbala (alias kept for compatibility)
            "shadbala": shadbala_components,
            "shadbala_components": shadbala_components,
            # High-level summary with ratios & Ishta/Kashta
            "shadbala_summary": shadbala_summary,
            "shadbala_overview": shadbala_overview,
            "dashas": dashas_data,
            "aspects": aspects_data,
        }

