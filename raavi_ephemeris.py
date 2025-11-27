import numpy as np
import pytz
import swisseph as swe
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, TYPE_CHECKING
from dataclasses import dataclass
from contextlib import contextmanager

if TYPE_CHECKING:
    from raavi_ephemeris_vector import VectorizedProvider

BodyID = str

@dataclass
class TimeLocation:
    dt_utc: Optional[datetime] = None
    dt_local: Optional[datetime] = None
    tz: Optional[pytz.BaseTzInfo] = None
    timezone: Optional[float] = None  # Hours offset from UTC (e.g., +3.5 for Tehran)
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
    houses: Optional[Dict[str, Any]] = None  # Can contain cusps (list), asc, mc, etc.
    utc_datetime: Optional[datetime] = None
    local_datetime: Optional[datetime] = None

# PyJhora-compatible flags and constants
BASE_FLAGS = swe.FLG_SWIEPH
SIDEREAL_EXTRA = swe.FLG_SIDEREAL
RISE_FLAGS = swe.BIT_HINDU_RISING | swe.FLG_TRUEPOS | swe.FLG_SPEED
AYANAMSA_DEFAULT = "LAHIRI"

# Central definition of Body IDs using swisseph constants
BODY_IDS: Dict[BodyID, int] = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
    "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
    "Rahu": swe.MEAN_NODE,  # Default to mean node, actual node type determined by node_mode
    # Ketu is not fetched from Swiss - it's calculated from Rahu
}

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

def compute_jd_pair(t: TimeLocation) -> tuple[float, float]:
    """
    Returns (jd_local, jd_utc) in PyJhora style.

    Rules:
    - If dt_utc exists:
        * jd_utc is calculated from dt_utc.
        * If timezone exists → jd_local = jd_utc + tz_hours/24
          Otherwise jd_local = jd_utc.
    - If dt_utc doesn't exist but we have dt_local + timezone:
        * jd_local is calculated from dt_local (without applying timezone).
        * jd_utc = jd_local - tz_hours/24
    - DST is never applied automatically; tz_hours is t.timezone as-is.
    """
    if t.dt_utc is not None:
        # Calculate jd_utc from dt_utc
        dt_utc = t.dt_utc if t.dt_utc.tzinfo is not None else t.dt_utc.replace(tzinfo=pytz.utc)
        if dt_utc.tzinfo != pytz.utc:
            dt_utc = dt_utc.astimezone(pytz.utc)

        ut = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
        jd_utc = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, ut, swe.GREG_CAL)

        # If timezone is specified, calculate jd_local
        if t.timezone is not None:
            jd_local = jd_utc + t.timezone / 24.0
        else:
            jd_local = jd_utc
    elif t.dt_local is not None:
        # Calculate jd_local from dt_local
        dt_local = t.dt_local
        hour_float = dt_local.hour + dt_local.minute / 60.0 + dt_local.second / 3600.0
        jd_local = swe.julday(dt_local.year, dt_local.month, dt_local.day, hour_float, swe.GREG_CAL)

        # Calculate jd_utc by subtracting timezone offset
        tz_hours = t.timezone if t.timezone is not None else 0.0
        jd_utc = jd_local - tz_hours / 24.0
    else:
        raise ValueError("TimeLocation must have either dt_utc or dt_local")

    return jd_local, jd_utc

def _resolve_sidm(ayanamsa_name: str) -> int:
    """Resolve ayanamsa name to swisseph constant."""
    key = f"SIDM_{ayanamsa_name.upper()}"
    return getattr(swe, key, swe.SIDM_LAHIRI)

@contextmanager
def ayanamsa_guard(sidereal: bool, ayanamsa_name: Optional[str]):
    """
    PyJhora style: set_sid_mode before each calculation, reset after.

    Currently reset → AYANAMSA_DEFAULT (Lahiri).
    If needed later, can maintain "current engine default" element.
    """
    if sidereal:
        mode = _resolve_sidm(ayanamsa_name or AYANAMSA_DEFAULT)
        swe.set_sid_mode(mode, 0, 0)
    try:
        yield
    finally:
        if sidereal:
            mode = _resolve_sidm(AYANAMSA_DEFAULT)
            swe.set_sid_mode(mode, 0, 0)

class SwissEphemerisProvider:
    def __init__(
        self,
        ephe_path: Optional[str] = None,
        sidereal_mode: Optional[str] = None,
        calculate_houses: bool = False,
        house_system: str = "P",
        bodies: Optional[List[BodyID]] = None,
        sidereal: bool = False,
        ayanamsa: Optional[str] = None,
        node_mode: str = "mean",
        ketu_lat_mode: str = "pyjhora"
    ):
        self.bodies = bodies or list(BODY_IDS.keys())
        self.calculate_houses = calculate_houses
        self.house_system = house_system

        # PyJhora-compatible configuration
        self.sidereal = bool(sidereal) or bool(sidereal_mode)
        self.ayanamsa = ayanamsa or sidereal_mode or AYANAMSA_DEFAULT
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

    def get_sky_frame(self, time_location: TimeLocation) -> SkyFrame:
        # Compute JD pair in PyJhora style
        jd_local, jd_utc = compute_jd_pair(time_location)

        positions = {}

        # Use ayanamsa_guard for all calculations
        with ayanamsa_guard(self.sidereal, self.ayanamsa):
            for body_name in self.bodies:
                # Skip Ketu - we'll calculate it from Rahu later
                if body_name == "Ketu":
                    continue

                # Handle Rahu with node_mode
                if body_name == "Rahu":
                    body_id = swe.MEAN_NODE if self.node_mode == "mean" else swe.TRUE_NODE
                else:
                    body_id = BODY_IDS.get(body_name)
                    if body_id is None:
                        continue

                # Calculate position using jd_utc
                res, _ = swe.calc_ut(jd_utc, body_id, self.flags)

                positions[body_name] = SkyPosition(
                    body_id=body_name,
                    jd=jd_utc,
                    lon=res[0],
                    lat=res[1],
                    distance=res[2],
                    speed_lon=res[3],
                )

            # Calculate Ketu from Rahu
            if "Rahu" in positions and "Ketu" in self.bodies:
                rahu = positions["Rahu"]
                ketu_lon = (rahu.lon + 180.0) % 360.0

                if self.ketu_lat_mode == "pyjhora":
                    ketu_lat = rahu.lat
                else:  # "mirrored"
                    ketu_lat = -rahu.lat

                positions["Ketu"] = SkyPosition(
                    body_id="Ketu",
                    jd=rahu.jd,
                    lon=ketu_lon,
                    lat=ketu_lat,
                    distance=rahu.distance,
                    speed_lon=rahu.speed_lon,
                )

            # Calculate houses if requested
            houses = None
            if self.calculate_houses:
                house_code = str(self.house_system or "P")[0].encode("ascii")
                cusps, ascmc = swe.houses_ex(
                    jd_utc,
                    time_location.latitude,
                    time_location.longitude,
                    house_code
                )
                houses = {
                    "system": self.house_system or "P",
                    "cusps": list(cusps),
                    "asc": ascmc[0],
                    "mc": ascmc[1],
                }

        return SkyFrame(
            jd=jd_local,
            positions=positions,
            houses=houses,
            utc_datetime=time_location.dt_utc,
            local_datetime=time_location.dt_local
        )

class VectorizedAdapter:
    # Use 'Any' or string forward reference to avoid runtime import error
    def __init__(self, vector_provider: Any):
        self._backend = vector_provider
        self.bodies = vector_provider.bodies

    def get_sky_frame(self, time_location: TimeLocation) -> SkyFrame:
        if time_location.dt_utc: dt = time_location.dt_utc
        else: dt = localize_datetime(time_location.dt_local, time_location.tz)
        jd = datetime_to_julian(dt)
        
        batch = self._backend.calculate_batch(np.array([jd]))
        lazy_frame = batch.get_frame(0)
        
        positions = {}
        for body_name in self.bodies:
            try:
                lp = lazy_frame.get_position(body_name)
                positions[body_name] = SkyPosition(
                    body_id=body_name, jd=jd, 
                    lon=lp.longitude, lat=lp.latitude,
                    speed_lon=lp.speed_lon, distance=lp.distance_au
                )
            except KeyError: continue
            
        return SkyFrame(
            jd=jd, positions=positions, 
            utc_datetime=dt if dt.tzinfo is not None else None
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
    sidereal_mode: Optional[str] = None
) -> Union[SwissEphemerisProvider, VectorizedAdapter]:
    
    if use_vector_engine:
        # LAZY IMPORT to prevent circular dependency
        from raavi_ephemeris_vector import VectorizedProvider
        
        target_bodies = bodies or list(BODY_IDS.keys())
        engine = VectorizedProvider(ephe_path=ephe_path, bodies=target_bodies, sidereal=sidereal, ayanamsa=ayanamsa)
        return VectorizedAdapter(engine)
        
    return SwissEphemerisProvider(
        ephe_path=ephe_path, 
        sidereal_mode=ayanamsa if sidereal else sidereal_mode, 
        house_system=house_system, 
        bodies=bodies, 
        calculate_houses=calculate_houses
    )

