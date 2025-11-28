import sys
import os
from pathlib import Path
from datetime import datetime
import pytest
import pytz
import swisseph as swe

# Ensure the module is found
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from raavi_ephemeris import TimeLocation, get_default_provider
from panchanga_engine import compute_panchanga

# Setup Ephemeris Path
# Using the standard relative path as provided in context files
EPHE_PATH = os.path.join(Path(__file__).resolve().parents[2], 'kerykeion', 'kerykeion', 'sweph')
if not os.path.exists(EPHE_PATH):
    # Fallback or trust default if specific path not found in this environment
    # But ideally we point to where we know they are if in the bundle.
    pass
else:
    swe.set_ephe_path(EPHE_PATH)


CHENNAI_TZ = pytz.timezone("Asia/Kolkata")
CHENNAI_LAT = 13.0827
CHENNAI_LON = 80.2707


@pytest.fixture
def provider():
    return get_default_provider(
        use_vector_engine=False,
        sidereal=True,
        ayanamsa="LAHIRI",
        calculate_houses=False,
        bodies=["Sun", "Moon"],
    )


def test_adhika_masa_2023(provider):
    """
    Test Adhika Masa (Leap Month) detection.
    Date: July 25, 2023
    Location: Chennai
    Expected: Adhika Shravana (is_adhika=True)
    """
    tl = TimeLocation(
        dt_local=datetime(2023, 7, 25, 6, 0, 0),
        tz=CHENNAI_TZ,
        latitude=CHENNAI_LAT,
        longitude=CHENNAI_LON,
    )
    result = compute_panchanga(tl, provider)

    # Verify Adhika flag
    assert result.masa.is_adhika is True, "July 25, 2023 should be Adhika Masa"

    # Control Case: August 25, 2023 (Nija Shravana/Bhadrapada) -> is_adhika must be False.
    tl_control = TimeLocation(
        dt_local=datetime(2023, 8, 25, 6, 0, 0),
        tz=CHENNAI_TZ,
        latitude=CHENNAI_LAT,
        longitude=CHENNAI_LON,
    )
    result_control = compute_panchanga(tl_control, provider)
    assert result_control.masa.is_adhika is False, "August 25, 2023 should NOT be Adhika Masa"


def test_vara_diwali_2023(provider):
    """
    Test Vara (Weekday).
    Date: November 12, 2023 (Diwali)
    Expected: Sunday (index 0)
    """
    tl = TimeLocation(
        dt_local=datetime(2023, 11, 12, 6, 0, 0),
        tz=CHENNAI_TZ,
        latitude=CHENNAI_LAT,
        longitude=CHENNAI_LON,
    )
    result = compute_panchanga(tl, provider)

    assert result.vara == "Sunday"
    assert result.vara_index == 0


def test_paksha_transitions_2023(provider):
    """
    Test Paksha.
    1. Nov 12, 2023 (Amavasya) -> Krishna Paksha (waning end)
    2. Nov 27, 2023 (Purnima) -> Shukla Paksha (waxing end)
    """
    # Amavasya case
    tl_amavasya = TimeLocation(
        dt_local=datetime(2023, 11, 12, 6, 0, 0),
        tz=CHENNAI_TZ,
        latitude=CHENNAI_LAT,
        longitude=CHENNAI_LON,
    )
    result_amavasya = compute_panchanga(tl_amavasya, provider)
    assert result_amavasya.paksha == "Krishna", "Nov 12, 2023 should be Krishna Paksha"

    # Purnima case
    tl_purnima = TimeLocation(
        dt_local=datetime(2023, 11, 27, 6, 0, 0),
        tz=CHENNAI_TZ,
        latitude=CHENNAI_LAT,
        longitude=CHENNAI_LON,
    )
    result_purnima = compute_panchanga(tl_purnima, provider)
    assert result_purnima.paksha == "Shukla", "Nov 27, 2023 should be Shukla Paksha"


def test_special_times_rahu_kalam(provider):
    """
    Test Rahu Kalam.
    Date: Nov 14, 2023 (Tuesday).
    Expected: Rahu Kalam is the 6th part (index 5) of the 8-part day.
    """
    tl = TimeLocation(
        dt_local=datetime(2023, 11, 14, 6, 0, 0),
        tz=CHENNAI_TZ,
        latitude=CHENNAI_LAT,
        longitude=CHENNAI_LON,
    )
    result = compute_panchanga(tl, provider)

    # Confirm it is Tuesday
    assert result.vara == "Tuesday"

    sunrise = result.sunrise_jd_utc
    sunset = result.sunset_jd_utc
    day_duration = sunset - sunrise

    # Rahu Kalam on Tuesday is usually 3:00 PM - 4:30 PM (approx), 8th part 6 (index 5)
    # Logic in code: rahu_offsets[2 (Tue)] = 0.75 (which is 6/8)
    # So start = sunrise + 0.75 * duration, end = start + 0.125 * duration

    rahu = result.special_times.rahu_kalam

    # Check strict containment in day
    assert rahu.start_jd_utc >= sunrise
    assert rahu.end_jd_utc <= sunset
    assert rahu.start_jd_utc < rahu.end_jd_utc

    # Check duration (approx 1/8th of day)
    expected_duration = day_duration / 8.0
    actual_duration = rahu.end_jd_utc - rahu.start_jd_utc
    assert abs(actual_duration - expected_duration) < 1e-6

    # Check specific timing logic for Tuesday (0.75 offset)
    expected_start = sunrise + (0.75 * day_duration)
    assert abs(rahu.start_jd_utc - expected_start) < 1e-6
