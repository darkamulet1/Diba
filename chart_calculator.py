import json
from datetime import datetime
from typing import Dict, Any, Optional
import pytz

from raavi_ephemeris import get_default_provider, TimeLocation
from logic.nakshatras import get_nakshatra_scalar
from logic.dashas import calculate_vimshottari
from logic.aspects import compute_aspects_for_frame


class ChartCalculator:
    def __init__(self, *, sidereal: bool = False, ayanamsa: str = "LAHIRI"):
        # Scalar provider with houses (Placidus by default)
        self.sidereal = sidereal
        self.ayanamsa = ayanamsa
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

        # 3) Dashas (Vimshottari)
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

        # 4) Aspects (simple set: conj/square/trine/opposition with orb)
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

        # 5) Assemble final structure
        zodiac_mode = "Sidereal" if self.sidereal else "Tropical"
        ayanamsa_info = f"{zodiac_mode} ({self.ayanamsa})" if self.sidereal else "Tropical (N/A)"

        return {
            "meta": {
                "name": name,
                "datetime_utc": dt_utc,
                "latitude": lat,
                "longitude": lon,
                "zodiac_system": zodiac_mode,
                "ayanamsa": ayanamsa_info,
                "jd": frame.jd,
            },
            "houses": frame.houses,
            "bodies": bodies_data,
            "dashas": dashas_data,
            "aspects": aspects_data,
        }

