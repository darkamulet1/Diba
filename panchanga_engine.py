"""
Panchanga engine – Phase 3 (Complete).

Phase 1: Sunrise-anchored indices (Tithi, Nakshatra, Yoga, Karana).
Phase 2: Event-driven end-times (Multi-Event processing for Kshaya/Adhika).
Phase 3: Calendar components (Vara, Paksha, Masa/Adhika logic).
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
    compute_jd_pair,
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
# 2. Info Classes (Phase 3)
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
    index: int          # 1..12 (1 = Chaitra, usually)
    is_adhika: bool     # True if Adhika Masa (Leap Month)
    name: Optional[str] = None  # Filled by translation/UI layer if needed


@dataclass
class PanchangaResult:
    sunrise_jd_utc: float
    sunset_jd_utc: float

    # Core Components
    tithi: TithiInfo
    nakshatra: NakshatraInfo
    yoga: YogaInfo
    karana: KaranaInfo

    # Phase 3 Calendar Components
    vara: str           # 'Sunday', 'Monday', ...
    vara_index: int     # 0=Sunday, ... 6=Saturday
    paksha: str         # 'Shukla' or 'Krishna'
    masa: MasaInfo

    samples: Optional[Sequence[tuple[float, float, float]]] = None


@dataclass
class PanchangaConfig:
    compute_end_times: bool = False
    samples_per_day: int = 5


# ---------------------------------------------------------------------------
# 3. Helpers – Sunrise, Frames, Phase unwrap
# ---------------------------------------------------------------------------


def _local_day_midnight(time_loc: TimeLocation) -> TimeLocation:
    """
    Return a TimeLocation pinned to local midnight of the same civil day.
    """
    if time_loc.dt_local:
        dt_local = time_loc.dt_local
    else:
        raise ValueError("TimeLocation must have dt_local for sunrise logic.")
    midnight = dt_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return TimeLocation(
        dt_local=midnight,
        tz=time_loc.tz,
        latitude=time_loc.latitude,
        longitude=time_loc.longitude,
    )


def _compute_sunrise_sunset(eph: SwissEphemerisProvider, time_loc: TimeLocation) -> tuple[float, float]:
    """
    Compute sunrise and sunset (UT JDs) for the civil day of time_loc.
    """
    midnight_loc = _local_day_midnight(time_loc)
    # Use central Raavi time conversion (handles tz/DST consistently).
    _, start_jd_utc = compute_jd_pair(midnight_loc)

    geopos = (time_loc.longitude, time_loc.latitude, 0.0)

    # Use positional arguments for compatibility with installed swisseph
    res_rise = swe.rise_trans(start_jd_utc, swe.SUN, geopos=geopos, rsmi=RISE_FLAGS | swe.CALC_RISE)
    rise_jd = res_rise[1][0]

    res_set = swe.rise_trans(start_jd_utc, swe.SUN, geopos=geopos, rsmi=RISE_FLAGS | swe.CALC_SET)
    set_jd = res_set[1][0]

    return rise_jd, set_jd


def _frame_at_jd(eph: SwissEphemerisProvider, jd_utc: float, lat: float, lon: float) -> Dict[str, float]:
    """
    Fetch Sun/Moon nirayana longitudes at a given UTC JD via SwissEphemerisProvider.
    """
    data = eph.calculate_positions(jd_utc, bodies=["Sun", "Moon"])
    return {"Sun": data["Sun"].lon, "Moon": data["Moon"].lon}


def _unwrap_phase(prev: float, curr: float) -> float:
    """
    Make `curr` continuous relative to `prev` by handling 0/360 wrap.
    Assumes motion between samples is monotonic and < 180°.
    """
    delta = curr - prev
    if delta < -180.0:
        return curr + 360.0
    if delta > 180.0:
        return curr - 360.0
    return curr


# ---------------------------------------------------------------------------
# 4. Phase 3 Helpers (Vara, Paksha, Masa)
# ---------------------------------------------------------------------------


def _get_vara(jd: float) -> tuple[int, str]:
    """
    Returns (index, name). 0=Sunday.
    Logic matches PyJHora: int(ceil(jd + 1)) % 7.
    """
    idx = int(math.ceil(jd + 1.0)) % 7
    names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    return idx, names[idx]


def _get_paksha(tithi_index: int) -> str:
    """
    0..14 = Shukla (waxing), 15..29 = Krishna (waning).
    """
    return "Shukla" if tithi_index < 15 else "Krishna"


def _find_new_moon_jd(
    eph: SwissEphemerisProvider,
    start_jd: float,
    direction: int,  # -1 for previous NM, +1 for next NM
    lat: float,
    lon: float,
) -> float:
    """
    Find the JD of the New Moon (phase = 0) relative to start_jd.
    Simple iterative solver; sufficient for Phase 3.
    """
    curr_jd = start_jd
    for _ in range(5):  # typically converges in 2–3 steps
        frame = _frame_at_jd(eph, curr_jd, lat, lon)
        s, m = frame["Sun"], frame["Moon"]

        phase = (m - s) % 360.0

        if direction == 1:
            dist_to_target = 360.0 - phase  # forward to next 0
        else:
            dist_to_target = -phase  # backward to 0

        # Moon moves ~12.19 deg/day faster than Sun
        days_step = dist_to_target / 12.19
        if abs(days_step) < 1e-6:
            return curr_jd
        curr_jd += days_step

    return curr_jd


def _compute_masa(
    eph: SwissEphemerisProvider,
    sunrise_jd: float,
    lat: float,
    lon: float,
) -> MasaInfo:
    """
    Determine lunar month and Adhika status (Amanta system, aligned with PyJHora).
    """
    # 1. Find New Moons bracketing the day
    nm_prev = _find_new_moon_jd(eph, sunrise_jd, -1, lat, lon)
    nm_next = _find_new_moon_jd(eph, sunrise_jd, 1, lat, lon)

    # 2. Solar rasi at New Moons
    sun_prev = _frame_at_jd(eph, nm_prev, lat, lon)["Sun"]
    sun_next = _frame_at_jd(eph, nm_next, lat, lon)["Sun"]

    rasi_prev = int(sun_prev / 30.0)
    rasi_next = int(sun_next / 30.0)

    # 3. Adhika detection: same rasi across consecutive New Moons
    is_adhika = (rasi_prev == rasi_next)

    # 4. Masa index (Amanta: month named after the solar rasi following conjunction)
    masa_index_raw = (rasi_prev + 1) % 12
    if masa_index_raw == 0:
        masa_index_raw = 12

    return MasaInfo(index=masa_index_raw, is_adhika=is_adhika)


# ---------------------------------------------------------------------------
# 5. Phase-Event Collection (Phase 2 core)
# ---------------------------------------------------------------------------


def _collect_phase_events(
    samples: Sequence[tuple[float, float, float]],
    initial_index: int,
    step_deg: float,
    max_index: int,
    phase_mode: str,
) -> list[tuple[int, float, float]]:
    """
    Generic engine to collect all phase boundary crossings from sampled data.

    Returns:
        list of (ended_index, end_jd_utc, boundary_phase_mod_360)
    """
    if not samples:
        return []

    events: list[tuple[int, float, float]] = []

    def get_phase(s: float, m: float) -> float:
        if phase_mode == "tithi":
            return (m - s) % 360.0
        if phase_mode == "yoga":
            return (m + s) % 360.0
        if phase_mode == "nakshatra":
            return m % 360.0
        raise ValueError(f"Unknown phase_mode {phase_mode!r}")

    jd0, sun0, moon0 = samples[0]
    prev_jd = jd0
    prev_phase = get_phase(sun0, moon0)
    tracking_index = initial_index

    for jd, sun_lon, moon_lon in samples[1:]:
        raw_phase = get_phase(sun_lon, moon_lon)
        curr_phase = _unwrap_phase(prev_phase, raw_phase)

        if curr_phase == prev_phase:
            prev_jd, prev_phase = jd, curr_phase
            continue

        while True:
            target_absolute = (tracking_index + 1) * step_deg
            diff = target_absolute - (prev_phase % 360.0)
            if diff <= 0:
                diff += 360.0
            candidate_boundary = prev_phase + diff

            if candidate_boundary <= curr_phase:
                ratio = (candidate_boundary - prev_phase) / (curr_phase - prev_phase)
                jd_cross = prev_jd + ratio * (jd - prev_jd)
                norm_boundary = candidate_boundary % 360.0
                events.append((tracking_index, jd_cross, norm_boundary))
                tracking_index = (tracking_index + 1) % max_index
                prev_phase = candidate_boundary
                prev_jd = jd_cross
                continue
            else:
                break

        prev_jd = jd
        prev_phase = curr_phase

    return events


def _sample_sun_moon_longitudes(
    eph: SwissEphemerisProvider,
    time_loc: TimeLocation,
    sunrise_jd_utc: float,
    next_sunrise_jd_utc: float,
    samples_per_day: int,
) -> List[Tuple[float, float, float]]:
    """
    Sample Sun/Moon longitudes between sunrise and next sunrise (inclusive).
    """
    span = next_sunrise_jd_utc - sunrise_jd_utc
    if samples_per_day < 2 or span <= 0:
        return []

    points: List[Tuple[float, float, float]] = []
    for i in range(samples_per_day):
        frac = i / (samples_per_day - 1)
        jd = sunrise_jd_utc + frac * span
        longs = _frame_at_jd(eph, jd, time_loc.latitude, time_loc.longitude)
        points.append(
            (
                jd,
                math.fmod(longs["Sun"] + 360.0, 360.0),
                math.fmod(longs["Moon"] + 360.0, 360.0),
            )
        )
    return points


# ---------------------------------------------------------------------------
# 6. Domain Wrappers
# ---------------------------------------------------------------------------


def collect_tithi_events(samples: Sequence[tuple[float, float, float]], tithi_index: int) -> List[TithiEvent]:
    raw = _collect_phase_events(samples, tithi_index, 12.0, 30, "tithi")
    return [TithiEvent(idx, t) for idx, t, _ in raw]


def collect_yoga_events(samples: Sequence[tuple[float, float, float]], yoga_index: int) -> List[YogaEvent]:
    raw = _collect_phase_events(samples, yoga_index, 360.0 / 27.0, 27, "yoga")
    return [YogaEvent(idx, t) for idx, t, _ in raw]


def collect_nakshatra_events(
    samples: Sequence[tuple[float, float, float]],
    nak_index: int,
) -> List[NakshatraEvent]:
    raw = _collect_phase_events(samples, nak_index, 360.0 / 27.0, 27, "nakshatra")
    events: List[NakshatraEvent] = []
    # For now, treat each boundary as the end of pada 4; can be refined later.
    for idx, t, _ in raw:
        events.append(NakshatraEvent(index=idx, pada=4, end_jd_utc=t))
    return events


def collect_karana_events_from_tithis(
    sunrise_jd: float,
    next_sunrise_jd: float,
    tithi_idx_at_sunrise: int,
    tithi_events: Sequence[TithiEvent],
) -> List[KaranaEvent]:
    """
    Derive karana events from tithi intervals.
    For each tithi interval [start, end]:
        K0 = 2*Ti   ends at mid
        K1 = 2*Ti+1 ends at end
    """
    events: List[KaranaEvent] = []

    def add(idx: int, start: float, end: float) -> None:
        if end <= start:
            return
        mid = (start + end) / 2.0
        events.append(KaranaEvent((idx * 2) % 60, mid))
        events.append(KaranaEvent((idx * 2 + 1) % 60, end))

    curr_start = sunrise_jd
    curr_idx = tithi_idx_at_sunrise

    for evt in tithi_events:
        add(curr_idx, curr_start, evt.end_jd_utc)
        curr_idx = (evt.index + 1) % 30
        curr_start = evt.end_jd_utc

    if curr_start < next_sunrise_jd:
        add(curr_idx, curr_start, next_sunrise_jd)

    return events


# ---------------------------------------------------------------------------
# 7. Main Function (Integrated Phase 3)
# ---------------------------------------------------------------------------


def compute_panchanga(
    time_loc: TimeLocation,
    eph: SwissEphemerisProvider,
    config: Optional[PanchangaConfig] = None,
) -> PanchangaResult:
    if config is None:
        config = PanchangaConfig()

    sunrise, sunset = _compute_sunrise_sunset(eph, time_loc)

    if time_loc.dt_local is None:
        raise ValueError("TimeLocation.dt_local is required for Panchanga computation.")

    next_day_loc = TimeLocation(
        dt_local=time_loc.dt_local + datetime.timedelta(days=1),
        tz=time_loc.tz,
        latitude=time_loc.latitude,
        longitude=time_loc.longitude,
    )
    next_day_rise, _ = _compute_sunrise_sunset(eph, next_day_loc)

    # 1. Sunrise snapshot
    frame = _frame_at_jd(eph, sunrise, time_loc.latitude, time_loc.longitude)
    sun = frame["Sun"]
    moon = frame["Moon"]

    # 2. Indices at sunrise
    tithi_index = int(((moon - sun) % 360.0) // 12.0) % 30
    nak_step = 360.0 / 27.0
    nak_index = int(moon // nak_step) % 27
    pada = int((moon % nak_step) // (nak_step / 4.0)) + 1
    yoga_index = int(((moon + sun) % 360.0) // nak_step) % 27
    karana_index = int(((moon - sun) % 360.0) // 6.0) % 60

    # 3. Events (Phase 2)
    t_events: List[TithiEvent] = []
    n_events: List[NakshatraEvent] = []
    y_events: List[YogaEvent] = []
    k_events: List[KaranaEvent] = []

    t_end: Optional[float] = None
    n_end: Optional[float] = None
    y_end: Optional[float] = None
    k_end: Optional[float] = None

    samples: Optional[Sequence[tuple[float, float, float]]] = None

    if config.compute_end_times:
        samples = _sample_sun_moon_longitudes(
            eph=eph,
            time_loc=time_loc,
            sunrise_jd_utc=sunrise,
            next_sunrise_jd_utc=next_day_rise,
            samples_per_day=config.samples_per_day,
        )
        t_events = collect_tithi_events(samples, tithi_index)
        n_events = collect_nakshatra_events(samples, nak_index)
        y_events = collect_yoga_events(samples, yoga_index)
        k_events = collect_karana_events_from_tithis(
            sunrise_jd=sunrise,
            next_sunrise_jd=next_day_rise,
            tithi_idx_at_sunrise=tithi_index,
            tithi_events=t_events,
        )

        if t_events:
            t_end = t_events[0].end_jd_utc
        if n_events:
            n_end = n_events[0].end_jd_utc
        if y_events:
            y_end = y_events[0].end_jd_utc
        if k_events:
            k_end = k_events[0].end_jd_utc

    # 4. Calendar components (Phase 3)
    vara_idx, vara_name = _get_vara(sunrise)
    paksha_name = _get_paksha(tithi_index)
    masa_info = _compute_masa(eph, sunrise, time_loc.latitude, time_loc.longitude)

    # 5. Assemble result
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
        samples=samples,
    )
