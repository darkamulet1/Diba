"""
Test Rahu/Ketu calculation in VectorizedProvider.
This test was added to verify the critical bug fix for Rahu/Ketu handling.
"""
import pytest
import numpy as np
import pytz
from datetime import datetime
from raavi_ephemeris import TimeLocation, get_default_provider


def test_rahu_ketu_vectorized_basic():
    """Test that VectorizedProvider can handle Rahu/Ketu without crashing."""
    # Create a vectorized provider with Rahu and Ketu
    provider = get_default_provider(
        use_vector_engine=True,
        bodies=["Sun", "Moon", "Rahu", "Ketu"],
        sidereal=True,
        ayanamsa="LAHIRI"
    )

    # Create a simple time location
    tl = TimeLocation(
        dt_utc=datetime(2000, 1, 1, 12, 0, 0, tzinfo=pytz.utc),
        latitude=28.6139,
        longitude=77.2090
    )

    # This should not crash
    frame = provider.get_sky_frame(tl)

    # Verify all bodies are present
    assert "Sun" in frame.positions
    assert "Moon" in frame.positions
    assert "Rahu" in frame.positions
    assert "Ketu" in frame.positions


def test_rahu_ketu_opposition():
    """Test that Ketu is exactly 180 degrees opposite to Rahu."""
    provider = get_default_provider(
        use_vector_engine=True,
        bodies=["Rahu", "Ketu"],
        sidereal=False
    )

    tl = TimeLocation(
        dt_utc=datetime(2020, 6, 21, 12, 0, 0, tzinfo=pytz.utc)
    )

    frame = provider.get_sky_frame(tl)

    rahu_lon = frame.positions["Rahu"].lon
    ketu_lon = frame.positions["Ketu"].lon

    # Ketu should be exactly 180 degrees from Rahu
    expected_ketu = (rahu_lon + 180.0) % 360.0
    assert abs(ketu_lon - expected_ketu) < 1e-6, f"Ketu {ketu_lon} != Rahu+180 {expected_ketu}"


def test_ketu_only_synthesizes_rahu():
    """Test that requesting only Ketu still calculates Rahu internally."""
    provider = get_default_provider(
        use_vector_engine=True,
        bodies=["Ketu"],  # Only Ketu requested
        sidereal=True
    )

    tl = TimeLocation(
        dt_utc=datetime(2023, 7, 25, 6, 0, 0, tzinfo=pytz.utc)
    )

    # This should not crash - Rahu should be calculated internally
    frame = provider.get_sky_frame(tl)

    # Only Ketu should be in the result
    assert "Ketu" in frame.positions
    assert "Rahu" not in frame.positions  # Rahu was only calculated internally


def test_vector_scalar_parity_rahu_ketu():
    """Test that vectorized and scalar engines give same Rahu/Ketu positions."""
    tl = TimeLocation(
        dt_utc=datetime(2000, 1, 1, 12, 0, 0, tzinfo=pytz.utc),
        latitude=13.0827,
        longitude=80.2707
    )

    bodies_list = ["Sun", "Moon", "Rahu", "Ketu"]
    scalar = get_default_provider(use_vector_engine=False, sidereal=True, bodies=bodies_list)
    vector = get_default_provider(use_vector_engine=True, sidereal=True, bodies=bodies_list)

    frame_scalar = scalar.get_sky_frame(tl)
    frame_vector = vector.get_sky_frame(tl)

    for body in ["Rahu", "Ketu"]:
        lon_scalar = frame_scalar.positions[body].lon
        lon_vector = frame_vector.positions[body].lon
        diff = abs(lon_scalar - lon_vector)
        assert diff < 1e-6, f"{body} mismatch: scalar={lon_scalar}, vector={lon_vector}"


def test_revati_dasha_calculation():
    """Test Dasha calculation for Revati nakshatra (tests the modulo fix)."""
    from logic.dashas import calculate_vimshottari

    # Moon at 350 degrees (in Revati, which starts at ~346.67)
    # This previously caused negative traversed calculation
    birth_date = datetime(2000, 1, 1, tzinfo=pytz.utc)

    # Should not crash or give nonsensical results
    dashas = calculate_vimshottari(350.0, birth_date, total_years=20)

    first = dashas[0]
    # Revati (26) % 9 = 8 -> Mercury
    assert first.lord == "Mercury"
    # Should have some balance left (not negative or > full duration)
    assert 0 < first.duration_years < 17  # Mercury full duration is 17 years
