import sys
from pathlib import Path
from datetime import datetime

import pytest
import pytz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Raavi"))

from raavi_ephemeris import TimeLocation, get_default_provider
from panchanga_engine import compute_panchanga, PanchangaConfig


TEHRAN = pytz.timezone("Asia/Tehran")


def _assert_event_list_well_formed(events, start: float, end_limit: float):
    assert events, "event list must not be empty when compute_end_times=True"
    prev = start
    for ev in events:
        assert start <= ev.end_jd_utc <= end_limit
        assert ev.end_jd_utc >= prev
        prev = ev.end_jd_utc


def test_panchanga_events_cover_day():
    tl = TimeLocation(
        dt_local=datetime(1997, 6, 7, 6, 0, 0),
        tz=TEHRAN,
        latitude=35.6892,
        longitude=51.3890,
    )
    provider = get_default_provider(
        use_vector_engine=False,
        sidereal=True,
        ayanamsa="LAHIRI",
        calculate_houses=False,
        bodies=["Sun", "Moon"],
    )
    config = PanchangaConfig(compute_end_times=True, samples_per_day=7)
    result = compute_panchanga(tl, provider, config=config)

    upper_limit = result.sunrise_jd_utc + 1.0
    _assert_event_list_well_formed(result.tithi.events, result.sunrise_jd_utc, upper_limit)
    _assert_event_list_well_formed(
        result.nakshatra.events, result.sunrise_jd_utc, upper_limit
    )
    _assert_event_list_well_formed(result.yoga.events, result.sunrise_jd_utc, upper_limit)
    _assert_event_list_well_formed(result.karana.events, result.sunrise_jd_utc, upper_limit)
