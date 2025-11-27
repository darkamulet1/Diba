import pytest
import pytz
from datetime import datetime
from raavi_ephemeris import TimeLocation, get_default_provider

TIME_LOCATIONS = [
    TimeLocation(dt_utc=datetime(2000, 1, 1, 12, 0, 0, tzinfo=pytz.utc)),
    TimeLocation(dt_local=datetime(2020, 6, 21, 15, 30, 0), tz=pytz.timezone('Asia/Tehran')),
]
BODIES = ['Sun', 'Moon']

def test_parity():
    for tl in TIME_LOCATIONS:
        classic = get_default_provider(use_vector_engine=False).get_sky_frame(tl)
        vector = get_default_provider(use_vector_engine=True).get_sky_frame(tl)
        for b in BODIES:
            diff = abs(classic.positions[b].lon - vector.positions[b].lon)
            assert diff == pytest.approx(0.0, abs=1e-6), f"Mismatch for {b}"

