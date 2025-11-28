import numpy as np
import pytz
import swisseph as swe
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Any, TYPE_CHECKING, Tuple
from dataclasses import dataclass

if TYPE_CHECKING:
    from raavi_ephemeris_vector import VectorizedProvider

BodyID = str

@dataclass
class TimeLocation:
    dt_utc: Optional[datetime] = None
    dt_local: Optional[datetime] = None
    tz: Optional[pytz.BaseTzInfo] = None
    latitude: float = 0.0
    longitude: float = 0.0

@dataclass
class SkyPosition:
    body_id: BodyID
    jd: float
    lon: float
    lat: float
    speed_lon: Optional[float] = None
    distance: Optional[float] = None
    declination: Optional[float] = None
    right_ascension: Optional[float] = None

@dataclass
class SkyFrame:
    jd: float
    positions: Dict[BodyID, SkyPosition]
    houses: Optional[Dict[str, Union[str, List[float]]]] = None
    utc_datetime: Optional[datetime] = None
    local_datetime: Optional[datetime] = None

# Central definition of Body IDs using swisseph constants
BODY_IDS: Dict[BodyID, int] = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "Rahu": swe.MEAN_NODE,
    # Ketu is synthesized from Rahu
}

BASE_FLAGS = swe.FLG_SWIEPH
SIDEREAL_EXTRA = swe.FLG_SIDEREAL
RISE_FLAGS = swe.BIT_HINDU_RISING | swe.FLG_TRUEPOS | swe.FLG_SPEED

AYANAMSA_DEFAULT = "LAHIRI"

def _resolve_sidm(ayanamsa_name: Optional[str]) -> int:
    if not ayanamsa_name:
        return getattr(swe, f"SIDM_{AYANAMSA_DEFAULT}", swe.SIDM_LAHIRI)
    key = f"SIDM_{ayanamsa_name.upper()}"
    return getattr(swe, key, swe.SIDM_LAHIRI)

def localize_datetime(dt_local: datetime, tz: pytz.BaseTzInfo) -> datetime:
    return tz.localize(dt_local)

def datetime_to_julian(dt: datetime) -> float:
    # Ensure UTC
    if dt.tzinfo is None:
        dt_utc = dt.replace(tzinfo=pytz.utc)
    else:
        dt_utc = dt.astimezone(pytz.utc)
    # Decimal hour (UT)
    ut = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, ut)

def _tz_offset_hours(tz: Optional[pytz.BaseTzInfo], reference: Optional[datetime]) -> float:
    if tz is None or reference is None:
        return 0.0
    if reference.tzinfo is None:
        localized = tz.localize(reference)
    else:
        localized = reference.astimezone(tz)
    offset = localized.utcoffset()
    return offset.total_seconds() / 3600.0 if offset else 0.0

def compute_jd_pair(time_location: TimeLocation) -> Tuple[float, float]:
    tz_hours = _tz_offset_hours(time_location.tz, time_location.dt_local or time_location.dt_utc)
    if time_location.dt_utc:
        dt_utc = time_location.dt_utc
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        jd_utc = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                            dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0)
        jd_local = jd_utc + tz_hours / 24.0 if time_location.tz else jd_utc
        return jd_local, jd_utc

    if not time_location.dt_local:
        raise ValueError("Either dt_local or dt_utc must be provided.")

    dt_local = time_location.dt_local
    if dt_local.tzinfo is None and time_location.tz:
        dt_local = time_location.tz.localize(dt_local)
    jd_local = swe.julday(dt_local.year, dt_local.month, dt_local.day,
                          dt_local.hour + dt_local.minute / 60.0 + dt_local.second / 3600.0)
    jd_utc = jd_local - tz_hours / 24.0
    return jd_local, jd_utc

@contextmanager
def ayanamsa_guard(sidereal: bool, ayanamsa_name: Optional[str]) -> Any:
    if sidereal:
        mode = _resolve_sidm(ayanamsa_name)
        swe.set_sid_mode(mode, 0, 0)
    try:
        yield
    finally:
        if sidereal:
            reset_mode = _resolve_sidm(AYANAMSA_DEFAULT)
            swe.set_sid_mode(reset_mode, 0, 0)

class SwissEphemerisProvider:
    def __init__(
        self,
        ephe_path: Optional[str] = None,
        sidereal_mode: Optional[str] = None,
        calculate_houses: bool = False,
        house_system: str = "P",
        bodies: Optional[List[BodyID]] = None,
        *,
        sidereal: bool = False,
        ayanamsa: str = "LAHIRI",
        node_mode: str = "mean",
        ketu_lat_mode: str = "pyjhora"
    ):
        self.bodies = bodies or list(BODY_IDS.keys())
        self.calculate_houses = calculate_houses
        self.house_system = house_system
        self.sidereal = bool(sidereal or sidereal_mode)
        self.ayanamsa = (sidereal_mode or ayanamsa) or AYANAMSA_DEFAULT
        self.node_mode = node_mode
        self.ketu_lat_mode = ketu_lat_mode

        if ephe_path:
            swe.set_ephe_path(ephe_path)
        self.flags = BASE_FLAGS
        if self.sidereal:
            self.flags |= SIDEREAL_EXTRA
        # RISE_FLAGS removed from general position calculation
        # They should only be used in rise/set calculations (panchanga_engine)

    def calculate_positions(
        self,
        jd_utc: float,
        bodies: Optional[List[BodyID]] = None,
    ) -> Dict[BodyID, SkyPosition]:
        """
        Calculate planetary positions for a given UTC Julian day.

        This is a lightweight variant of `get_sky_frame` used by the Panchanga
        engine for sampling between sunrise and next sunrise, without needing a
        full TimeLocation round-trip.
        """
        target_bodies = bodies or self.bodies
        positions: Dict[BodyID, SkyPosition] = {}
        with ayanamsa_guard(self.sidereal, self.ayanamsa):
            for body_name in target_bodies:
                if body_name == "Ketu":
                    continue
                if body_name == "Rahu":
                    body_id = swe.MEAN_NODE if self.node_mode == "mean" else swe.TRUE_NODE
                else:
                    body_id = BODY_IDS.get(body_name)
                if body_id is None:
                    continue
                res = swe.calc_ut(jd_utc, body_id, self.flags)
                data = res[0]
                positions[body_name] = SkyPosition(
                    body_id=body_name,
                    jd=jd_utc,
                    lon=data[0],
                    lat=data[1],
                    speed_lon=data[3],
                    distance=data[2],
                )

            if "Rahu" in positions and "Ketu" in target_bodies:
                rahu = positions["Rahu"]
                ketu_lon = (rahu.lon + 180.0) % 360.0
                ketu_lat = rahu.lat if self.ketu_lat_mode == "pyjhora" else -rahu.lat
                positions["Ketu"] = SkyPosition(
                    body_id="Ketu",
                    jd=rahu.jd,
                    lon=ketu_lon,
                    lat=ketu_lat,
                    speed_lon=rahu.speed_lon,
                    distance=rahu.distance,
                )
        return positions

    def get_sky_frame(self, time_location: TimeLocation) -> SkyFrame:
        jd_local, jd_utc = compute_jd_pair(time_location)
        positions: Dict[BodyID, SkyPosition] = {}
        with ayanamsa_guard(self.sidereal, self.ayanamsa):
            for body_name in self.bodies:
                if body_name == "Ketu":
                    continue
                if body_name == "Rahu":
                    body_id = swe.MEAN_NODE if self.node_mode == "mean" else swe.TRUE_NODE
                else:
                    body_id = BODY_IDS.get(body_name)
                if body_id is None:
                    continue
                res = swe.calc_ut(jd_utc, body_id, self.flags)
                data = res[0]
                positions[body_name] = SkyPosition(
                    body_id=body_name,
                    jd=jd_utc,
                    lon=data[0],
                    lat=data[1],
                    speed_lon=data[3],
                    distance=data[2],
                )

            if "Rahu" in positions and "Ketu" in self.bodies:
                rahu = positions["Rahu"]
                ketu_lon = (rahu.lon + 180.0) % 360.0
                ketu_lat = rahu.lat if self.ketu_lat_mode == "pyjhora" else -rahu.lat
                positions["Ketu"] = SkyPosition(
                    body_id="Ketu",
                    jd=rahu.jd,
                    lon=ketu_lon,
                    lat=ketu_lat,
                    speed_lon=rahu.speed_lon,
                    distance=rahu.distance,
                )

        houses = None
        if self.calculate_houses:
            house_code = str(self.house_system or "P")[0].encode("ascii", errors="ignore")
            cusps, ascmc = swe.houses_ex(
                jd_utc,
                time_location.latitude,
                time_location.longitude,
                house_code,
                flags=self.flags,
            )
            houses = {"system": self.house_system or "P", "cusps": list(cusps), "asc": ascmc[0], "mc": ascmc[1]}

        utc_dt = time_location.dt_utc
        local_dt = time_location.dt_local
        if not local_dt and utc_dt and time_location.tz:
            local_dt = time_location.dt_utc.astimezone(time_location.tz)

        return SkyFrame(
            jd=jd_utc,
            positions=positions,
            houses=houses,
            utc_datetime=utc_dt,
            local_datetime=local_dt,
        )

class VectorizedAdapter:
    # Use 'Any' or string forward reference to avoid runtime import error
    def __init__(self, vector_provider: Any):
        self._backend = vector_provider
        self.bodies = vector_provider.bodies

    def get_sky_frame(self, time_location: TimeLocation) -> SkyFrame:
        _, jd_utc = compute_jd_pair(time_location)
        batch = self._backend.calculate_batch(np.array([jd_utc]))
        lazy_frame = batch.get_frame(0)

        positions = {}
        for body_name in self.bodies:
            try:
                lp = lazy_frame.get_position(body_name)
                positions[body_name] = SkyPosition(
                    body_id=body_name, jd=jd_utc,
                    lon=lp.longitude, lat=lp.latitude,
                    speed_lon=lp.speed_lon, distance=lp.distance_au
                )
            except KeyError: continue
            
        utc_dt = time_location.dt_utc
        local_dt = time_location.dt_local
        if not local_dt and utc_dt and time_location.tz:
            local_dt = utc_dt.astimezone(time_location.tz)
        return SkyFrame(
            jd=jd_utc,
            positions=positions,
            utc_datetime=utc_dt,
            local_datetime=local_dt,
        )

def get_default_provider(
    calculate_houses: bool = False,
    house_system: str = "P",
    *,
    use_vector_engine: bool = False,
    ephe_path: Optional[str] = None,
    sidereal: bool = False,
    ayanamsa: str = "LAHIRI",
    bodies: Optional[List[BodyID]] = None,
    sidereal_mode: Optional[str] = None,
    node_mode: str = "mean",
    ketu_lat_mode: str = "pyjhora",
) -> Union[SwissEphemerisProvider, VectorizedAdapter]:
    
    if use_vector_engine:
        # LAZY IMPORT to prevent circular dependency
        from raavi_ephemeris_vector import VectorizedProvider
        
        target_bodies = bodies or list(BODY_IDS.keys())
        engine = VectorizedProvider(
            ephe_path=ephe_path,
            bodies=target_bodies,
            sidereal=sidereal,
            ayanamsa=ayanamsa,
            node_mode=node_mode,
            ketu_lat_mode=ketu_lat_mode,
        )
        return VectorizedAdapter(engine)

    return SwissEphemerisProvider(
        ephe_path=ephe_path, 
        sidereal_mode=ayanamsa if sidereal else sidereal_mode, 
        house_system=house_system, 
        bodies=bodies, 
        calculate_houses=calculate_houses,
        sidereal=sidereal,
        ayanamsa=ayanamsa,
        node_mode=node_mode,
        ketu_lat_mode=ketu_lat_mode,
    )

