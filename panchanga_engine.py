"""
Panchanga engine – Phase 4 (Feature Complete).

Phase 1: Sunrise-anchored indices (Tithi, Nakshatra, Yoga, Karana).
Phase 2: Event-driven end-times (Multi-Event processing for Kshaya/Adhika).
Phase 3: Calendar components (Vara, Paksha, Masa).
Phase 4: Special Times (Rahu Kalam, Yamaganda, Gulika, Abhijit).
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, List, Tuple
import math
import datetime
import pytz
import swisseph as swe

from raavi_ephemeris import (
    RISE_FLAGS,
    SwissEphemerisProvider,
    TimeLocation,
)

# ---------------------------------------------------------------------------
# 1. Event Data Classes
# ---------------------------------------------------------------------------

@dataclass
class TithiEvent:
    index: int          # 0..29
    end_jd_utc: float

@dataclass
class NakshatraEvent:
    index: int          # 0..26
    pada: int           # 1..4
    end_jd_utc: float

@dataclass
class YogaEvent:
    index: int          # 0..26
    end_jd_utc: float

@dataclass
class KaranaEvent:
    index: int          # 0..59
    end_jd_utc: float

# ---------------------------------------------------------------------------
# 2. Info Classes
# ---------------------------------------------------------------------------

@dataclass
class TithiInfo:
    index: int
    name: Optional[str]
    start_jd_utc: float
    end_jd_utc: Optional[float]
    events: List[TithiEvent] = field(default_factory=list)

@dataclass
class NakshatraInfo:
    index: int
    pada: int
    start_jd_utc: float
    end_jd_utc: Optional[float]
    events: List[NakshatraEvent] = field(default_factory=list)

@dataclass
class YogaInfo:
    index: int
    start_jd_utc: float
    end_jd_utc: Optional[float]
    events: List[YogaEvent] = field(default_factory=list)

@dataclass
class KaranaInfo:
    index: int
    start_jd_utc: float
    end_jd_utc: Optional[float]
    events: List[KaranaEvent] = field(default_factory=list)

@dataclass
class MasaInfo:
    index: int          # 1..12 (1 = Chaitra)
    is_adhika: bool     # True if Adhika Masa
    name: Optional[str] = None

@dataclass
class SpecialTimeRange:
    start_jd_utc: float
    end_jd_utc: float

@dataclass
class SpecialTimesInfo:
    rahu_kalam: SpecialTimeRange
    yamaganda: SpecialTimeRange
    gulika: SpecialTimeRange
    abhijit: SpecialTimeRange

@dataclass
class PanchangaResult:
    sunrise_jd_utc: float
    sunset_jd_utc: float

    # Core Components
    tithi: TithiInfo
    nakshatra: NakshatraInfo
    yoga: YogaInfo
    karana: KaranaInfo

    # Calendar Components
    vara: str
    vara_index: int
    paksha: str
    masa: MasaInfo

    # Phase 4: Special Times
    special_times: SpecialTimesInfo

    samples: Optional[Sequence[tuple[float, float, float]]] = None

@dataclass
class PanchangaConfig:
    compute_end_times: bool = False
    samples_per_day: int = 5

# ---------------------------------------------------------------------------
# 3. Helpers
# ---------------------------------------------------------------------------

def _local_day_midnight(time_loc: TimeLocation) -> TimeLocation:
    if time_loc.dt_local:
        dt_local = time_loc.dt_local
    else:
        raise ValueError("TimeLocation must have dt_local for sunrise logic.")
    midnight = dt_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return TimeLocation(dt_local=midnight, tz=time_loc.tz, latitude=time_loc.latitude, longitude=time_loc.longitude)

def _compute_sunrise_sunset(eph: SwissEphemerisProvider, time_loc: TimeLocation) -> tuple[float, float]:
    midnight_loc = _local_day_midnight(time_loc)
    utc_dt = midnight_loc.dt_local.astimezone(datetime.timezone.utc)
    start_jd_utc = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                              utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)

    geopos = (time_loc.longitude, time_loc.latitude, 0.0)
    res_rise = swe.rise_trans(start_jd_utc, swe.SUN, geopos=geopos, rsmi=RISE_FLAGS | swe.CALC_RISE)
    rise_jd = res_rise[1][0]
    res_set = swe.rise_trans(start_jd_utc, swe.SUN, geopos=geopos, rsmi=RISE_FLAGS | swe.CALC_SET)
    set_jd = res_set[1][0]
    return rise_jd, set_jd

def _frame_at_jd(eph: SwissEphemerisProvider, jd_utc: float, lat: float, lon: float) -> Dict[str, float]:
    data = eph.calculate_positions(jd_utc, bodies=["Sun", "Moon"])
    return {"Sun": data["Sun"].lon, "Moon": data["Moon"].lon}

def _unwrap_phase(prev: float, curr: float) -> float:
    delta = curr - prev
    if delta < -180.0: return curr + 360.0
    if delta > 180.0: return curr - 360.0
    return curr

# ---------------------------------------------------------------------------
# 4. Phase 3 & 4 Helpers (Calendar & Special Times)
# ---------------------------------------------------------------------------

def _get_vara(jd: float) -> tuple[int, str]:
    idx = int(math.ceil(jd + 1)) % 7
    names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    return idx, names[idx]

def _get_paksha(tithi_index: int) -> str:
    return "Shukla" if tithi_index < 15 else "Krishna"

def _find_new_moon_jd(eph, start_jd, direction, lat, lon) -> float:
    curr_jd = start_jd
    for i in range(10):
        frame = _frame_at_jd(eph, curr_jd, lat, lon)
        s, m = frame["Sun"], frame["Moon"]
        phase = (m - s) % 360.0

        if i == 0:
            # Iteration 0: Force movement in the requested direction.
            if direction == 1:
                dist_to_target = 360.0 - phase
            else:
                dist_to_target = -phase
        else:
            # Iteration >0: Use shortest path to 0 phase to converge.
            dist_to_target = -phase
            if dist_to_target < -180.0: dist_to_target += 360.0
            if dist_to_target > 180.0:  dist_to_target -= 360.0

        days_step = dist_to_target / 12.19
        if abs(days_step) < 1e-6:
            return curr_jd
        curr_jd += days_step
    return curr_jd

def _compute_masa(eph, sunrise_jd, lat, lon) -> MasaInfo:
    nm_prev = _find_new_moon_jd(eph, sunrise_jd, -1, lat, lon)
    nm_next = _find_new_moon_jd(eph, sunrise_jd, 1, lat, lon)

    sun_prev = _frame_at_jd(eph, nm_prev, lat, lon)["Sun"]
    sun_next = _frame_at_jd(eph, nm_next, lat, lon)["Sun"]

    rasi_prev = int(sun_prev / 30.0)
    rasi_next = int(sun_next / 30.0)

    is_adhika = (rasi_prev == rasi_next)
    masa_index_raw = (rasi_prev + 1) % 12
    if masa_index_raw == 0: masa_index_raw = 12

    return MasaInfo(index=masa_index_raw, is_adhika=is_adhika)

def _compute_special_times(sunrise_jd: float, sunset_jd: float, weekday_idx: int) -> SpecialTimesInfo:
    """
    Computes Rahu Kalam, Yamaganda, Gulika, and Abhijit Muhurta.
    """
    day_duration = sunset_jd - sunrise_jd

    # 1. Kalams (Day divided by 8)
    # Start fractions for [Sun, Mon, Tue, Wed, Thu, Fri, Sat]
    # Based on PyJHora / Vedic standard
    rahu_offsets = [0.875, 0.125, 0.75, 0.5, 0.625, 0.375, 0.25]
    yama_offsets = [0.5, 0.375, 0.25, 0.125, 0.0, 0.75, 0.625]
    gulika_offsets = [0.75, 0.625, 0.5, 0.375, 0.25, 0.125, 0.0]

    kalam_duration = day_duration / 8.0

    def get_kalam(offsets) -> SpecialTimeRange:
        start_frac = offsets[weekday_idx]
        start = sunrise_jd + (start_frac * day_duration)
        end = start + kalam_duration
        return SpecialTimeRange(start, end)

    # 2. Abhijit Muhurta (8th muhurta of 15)
    # Start = Sunrise + (7/15 * duration)
    # End   = Sunrise + (8/15 * duration)
    abhijit_start = sunrise_jd + (7.0/15.0 * day_duration)
    abhijit_end = sunrise_jd + (8.0/15.0 * day_duration)

    return SpecialTimesInfo(
        rahu_kalam=get_kalam(rahu_offsets),
        yamaganda=get_kalam(yama_offsets),
        gulika=get_kalam(gulika_offsets),
        abhijit=SpecialTimeRange(abhijit_start, abhijit_end)
    )

# ---------------------------------------------------------------------------
# 5. Core Logic & Wrappers (Phase 2)
# ---------------------------------------------------------------------------

def _collect_phase_events(samples, initial_index, step_deg, max_index, phase_mode):
    if not samples: return []
    events = []
    def get_phase(s, m):
        if phase_mode == "tithi": return (m - s) % 360.0
        elif phase_mode == "yoga": return (m + s) % 360.0
        elif phase_mode == "nakshatra": return m % 360.0
        raise ValueError(f"Unknown mode {phase_mode}")

    jd0, sun0, moon0 = samples[0]
    prev_jd = jd0
    prev_phase = get_phase(sun0, moon0)
    tracking_index = initial_index

    for jd, sun_lon, moon_lon in samples[1:]:
        raw_phase = get_phase(sun_lon, moon_lon)
        curr_phase = _unwrap_phase(prev_phase, raw_phase)

        while True:
            target_absolute = ((tracking_index + 1) * step_deg)
            diff = target_absolute - (prev_phase % 360.0)
            if diff <= 0: diff += 360.0
            candidate_boundary = prev_phase + diff

            if candidate_boundary <= curr_phase:
                ratio = (candidate_boundary - prev_phase) / (curr_phase - prev_phase)
                jd_cross = prev_jd + ratio * (jd - prev_jd)
                norm_boundary = candidate_boundary % 360.0
                events.append((tracking_index, jd_cross, norm_boundary))
                tracking_index = (tracking_index + 1) % max_index
                continue
            else:
                break

        prev_jd = jd
        prev_phase = curr_phase
    return events

def _sample_sun_moon_longitudes(eph, time_loc, start, end, samples_per_day):
    span = end - start
    if samples_per_day < 2 or span <= 0: return []
    points = []
    for i in range(samples_per_day):
        frac = i / (samples_per_day - 1)
        jd = start + frac * span
        longs = _frame_at_jd(eph, jd, time_loc.latitude, time_loc.longitude)
        points.append((jd, math.fmod(longs["Sun"]+360, 360), math.fmod(longs["Moon"]+360, 360)))
    return points

def collect_tithi_events(samples, idx):
    raw = _collect_phase_events(samples, idx, 12.0, 30, "tithi")
    return [TithiEvent(i, t) for i, t, _ in raw]

def collect_yoga_events(samples, idx):
    raw = _collect_phase_events(samples, idx, 360.0/27.0, 27, "yoga")
    return [YogaEvent(i, t) for i, t, _ in raw]

def collect_nakshatra_events(samples, idx):
    raw = _collect_phase_events(samples, idx, 360.0/27.0, 27, "nakshatra")
    return [NakshatraEvent(i, 4, t) for i, t, _ in raw]

def collect_karana_events_from_tithis(start_jd, end_jd, tithi_idx, t_events):
    events = []
    def add(idx, s, e):
        if e <= s: return
        mid = (s + e) / 2.0
        events.append(KaranaEvent((idx*2)%60, mid))
        events.append(KaranaEvent((idx*2+1)%60, e))

    curr_start = start_jd
    curr_idx = tithi_idx
    for evt in t_events:
        add(curr_idx, curr_start, evt.end_jd_utc)
        curr_idx = (evt.index + 1) % 30
        curr_start = evt.end_jd_utc
    if curr_start < end_jd:
        add(curr_idx, curr_start, end_jd)
    return events

# ---------------------------------------------------------------------------
# 7. Main Function (Phase 4 Integration)
# ---------------------------------------------------------------------------

def compute_panchanga(
    time_loc: TimeLocation,
    eph: SwissEphemerisProvider,
    config: Optional[PanchangaConfig] = None,
) -> PanchangaResult:
    if config is None: config = PanchangaConfig()

    sunrise, sunset = _compute_sunrise_sunset(eph, time_loc)

    next_day_loc = TimeLocation(
        dt_local=time_loc.dt_local + datetime.timedelta(days=1),
        tz=time_loc.tz, latitude=time_loc.latitude, longitude=time_loc.longitude
    )
    next_day_rise, _ = _compute_sunrise_sunset(eph, next_day_loc)

    # 1. Sunrise Snapshot
    frame = _frame_at_jd(eph, sunrise, time_loc.latitude, time_loc.longitude)
    sun, moon = frame["Sun"], frame["Moon"]

    # 2. Indices
    tithi_index = int(((moon - sun) % 360) // 12.0) % 30
    nak_step = 360.0 / 27.0
    nak_index = int(moon // nak_step) % 27
    pada = int((moon % nak_step) // (nak_step / 4.0)) + 1
    yoga_index = int(((moon + sun) % 360) // nak_step) % 27
    karana_index = int(((moon - sun) % 360) // 6.0) % 60

    # 3. Events
    t_events, n_events, y_events, k_events = [], [], [], []
    t_end, n_end, y_end, k_end = None, None, None, None
    samples = None

    if config.compute_end_times:
        samples = _sample_sun_moon_longitudes(eph, time_loc, sunrise, next_day_rise, config.samples_per_day)
        t_events = collect_tithi_events(samples, tithi_index)
        n_events = collect_nakshatra_events(samples, nak_index)
        y_events = collect_yoga_events(samples, yoga_index)
        k_events = collect_karana_events_from_tithis(sunrise, next_day_rise, tithi_index, t_events)

        if t_events: t_end = t_events[0].end_jd_utc
        if n_events: n_end = n_events[0].end_jd_utc
        if y_events: y_end = y_events[0].end_jd_utc
        if k_events: k_end = k_events[0].end_jd_utc

    # 4. Calendar & Special Times (Phase 3 & 4)
    vara_idx, vara_name = _get_vara(sunrise)
    paksha_name = _get_paksha(tithi_index)
    masa_info = _compute_masa(eph, sunrise, time_loc.latitude, time_loc.longitude)
    special_times = _compute_special_times(sunrise, sunset, vara_idx)

    # 5. Result
    return PanchangaResult(
        sunrise_jd_utc=sunrise,
        sunset_jd_utc=sunset,
        tithi=TithiInfo(tithi_index, None, sunrise, t_end, t_events),
        nakshatra=NakshatraInfo(nak_index, pada, sunrise, n_end, n_events),
        yoga=YogaInfo(yoga_index, sunrise, y_end, y_events),
        karana=KaranaInfo(karana_index, sunrise, k_end, k_events),
        vara=vara_name,
        vara_index=vara_idx,
        paksha=paksha_name,
        masa=masa_info,
        special_times=special_times,
        samples=samples
    )
