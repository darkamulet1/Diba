import sys
from pathlib import Path
from datetime import datetime

import pytest
import pytz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Raavi"))

from raavi_ephemeris import TimeLocation, get_default_provider
from panchanga_engine import compute_panchanga, PanchangaConfig


TEHRAN = pytz.timezone("Asia/Tehran")


def test_panchanga_end_times_in_range():
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
    config = PanchangaConfig(compute_end_times=True, samples_per_day=5)
    result = compute_panchanga(tl, provider, config=config)

    assert result.sunrise_jd_utc < result.sunset_jd_utc
    for end in (
        result.tithi.end_jd_utc,
        result.nakshatra.end_jd_utc,
        result.yoga.end_jd_utc,
    ):
        assert end is None or (result.sunrise_jd_utc <= end <= result.sunrise_jd_utc + 1.0)
