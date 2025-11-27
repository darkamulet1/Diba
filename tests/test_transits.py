import pytest
import numpy as np
from datetime import datetime, timedelta
import pytz

from raavi_ephemeris import get_default_provider, datetime_to_julian
from logic.transits import find_zodiac_ingresses


def test_moon_ingress_vectorized():
    # Setup: 10 days of data starting Jan 1, 2024.
    # The Moon moves ~13 degrees/day, so it changes sign every ~2.25 days.
    # In 10 days, we expect roughly 4 sign changes.
    start_date = datetime(2024, 1, 1, tzinfo=pytz.utc)
    days = 10
    # Hourly resolution (24 * 10 = 240 points) ensures we catch the transition
    jds = np.array([datetime_to_julian(start_date + timedelta(hours=i)) for i in range(days * 24)])
    
    # Use Vector Engine
    provider = get_default_provider(use_vector_engine=True)
    batch = provider._backend.calculate_batch(jds)
    
    # Find Ingresses for the Moon
    ingresses = find_zodiac_ingresses(batch, "Moon")
    
    print(f"\nFound {len(ingresses)} Moon ingresses in {days} days (Hourly resolution):")
    for jd, f, t in ingresses:
        # Simple logging for verification
        print(f"  JD {jd:.4f}: Sign {f} -> {t}")
        
    # Validation
    assert len(ingresses) >= 3, "Moon should change signs at least 3 times in 10 days"
    
    # Logic check: Verify the 'from' and 'to' signs are actually different
    for _, f, t in ingresses:
        assert f != t
        assert 0 <= f <= 11
        assert 0 <= t <= 11

