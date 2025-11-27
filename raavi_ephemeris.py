import numpy as np
import pytz
import swisseph as swe
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, TYPE_CHECKING
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
    houses: Optional[Dict[str, float]] = None
    utc_datetime: Optional[datetime] = None
    local_datetime: Optional[datetime] = None

# Central definition of Body IDs using swisseph constants
BODY_IDS: Dict[BodyID, int] = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
    "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
    "Mean_North_Lunar_Node": swe.MEAN_NODE, "True_North_Lunar_Node": swe.TRUE_NODE,
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

class SwissEphemerisProvider:
    def __init__(self, ephe_path: Optional[str] = None, sidereal_mode: Optional[str] = None, calculate_houses: bool = False, house_system: str = "P", bodies: Optional[List[BodyID]] = None):
        self.bodies = bodies or list(BODY_IDS.keys())
        self.calculate_houses = calculate_houses
        self.house_system = house_system
        
        # Configure Flags: Default to Moshier (Analytic) for dev portability
        self.flags = swe.FLG_MOSEPH | swe.FLG_SPEED
        
        if ephe_path:
            swe.set_ephe_path(ephe_path)
            self.flags = swe.FLG_SWIEPH | swe.FLG_SPEED

        if sidereal_mode:
            self.flags |= swe.FLG_SIDEREAL
            # Robust case-insensitive lookup
            mode_name = f"SIDM_{sidereal_mode.upper()}"
            mode = getattr(swe, mode_name, swe.SIDM_LAHIRI)
            swe.set_sid_mode(mode, 0, 0)

    def get_sky_frame(self, time_location: TimeLocation) -> SkyFrame:
        if time_location.dt_utc: dt = time_location.dt_utc
        else: dt = localize_datetime(time_location.dt_local, time_location.tz)
        
        jd = datetime_to_julian(dt)
        positions = {}
        
        for body_name in self.bodies:
            body_id = BODY_IDS.get(body_name)
            if body_id is None: continue
            
            # swe.calc_ut -> ((lon, lat, dist, speed_lon, ...), rflag)
            res = swe.calc_ut(jd, body_id, self.flags)
            data = res[0]
            
            positions[body_name] = SkyPosition(
                body_id=body_name, jd=jd, 
                lon=data[0], lat=data[1], 
                speed_lon=data[3], distance=data[2]
            )
            
        houses = None
        if self.calculate_houses:
            # swe.houses_ex expects a single-byte house system identifier
            house_system = str(self.house_system or "P")[0].encode("ascii", errors="ignore")
            h_res = swe.houses_ex(jd, time_location.latitude, time_location.longitude, house_system)
            houses = {"Ascendant": h_res[1][0], "MC": h_res[1][1]}

        return SkyFrame(
            jd=jd, positions=positions, houses=houses,
            utc_datetime=dt if dt.tzinfo is not None else None, 
            local_datetime=None
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

