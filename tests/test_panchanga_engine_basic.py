import sys
from pathlib import Path
from datetime import datetime

import pytest
import pytz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Raavi"))

from raavi_ephemeris import TimeLocation, get_default_provider
from panchanga_engine import compute_panchanga


TEHRAN = pytz.timezone("Asia/Tehran")


def test_compute_panchanga_returns_basics():
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
    result = compute_panchanga(tl, provider)
    assert result.sunrise_jd_utc < result.sunset_jd_utc
    assert 0 <= result.tithi.index < 30
    assert 0 <= result.nakshatra.index < 27
    assert 1 <= result.nakshatra.pada <= 4
    assert 0 <= result.yoga.index < 27
    assert 0 <= result.karana.index < 60
