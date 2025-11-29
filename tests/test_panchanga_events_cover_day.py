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

    upper_limit = result.sunrise_jd_utc + 1.2  # Allow slightly more than 1 day to be safe, next sunrise is approx +1.0
    
    # Verify primary end-times match first event
    if result.tithi.events:
        assert result.tithi.end_jd_utc == result.tithi.events[0].end_jd_utc
    if result.karana.events:
        assert result.karana.end_jd_utc == result.karana.events[0].end_jd_utc

    # Verify Karana coverage
    # Karana events should cover the whole day chronologically
    k_events = result.karana.events
    assert len(k_events) >= 2 # At least 2 karanas per day usually
    
    # Check strict ordering
    end_times = [ev.end_jd_utc for ev in k_events]
    assert end_times == sorted(end_times), "Karana events must be sorted"
    
    # Check boundaries
    assert end_times[0] >= result.sunrise_jd_utc
    # The last event should align with next sunrise (approx)
    # The logic adds interval up to next_sunrise, so the last event end_jd should be next_sunrise
    # We can check if it is > sunset to ensure it covers the day
    assert end_times[-1] > result.sunset_jd_utc

    # Verify general structure of other events
    for lst in [result.tithi.events, result.nakshatra.events, result.yoga.events]:
        # Events might be empty if no change occurs (rare for Nak/Yoga, possible for Tithi)
        # But if present, must be ordered
        if lst:
            t_list = [e.end_jd_utc for e in lst]
            assert t_list == sorted(t_list)
