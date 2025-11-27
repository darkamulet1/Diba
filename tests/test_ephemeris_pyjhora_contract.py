"""
Tests for PyJhora contract compliance in raavi-ephemeris.

These tests verify that our implementation matches PyJhora's behavior for:
- Time, calendar, and JD calculations
- Flags and ayanamsa handling
- Rahu/Ketu nodes
- Houses calculation
- Scalar and vector engine parity
"""

import pytest
import numpy as np
from datetime import datetime
import pytz
import swisseph as swe

from raavi_ephemeris import (
    TimeLocation,
    SwissEphemerisProvider,
    compute_jd_pair,
)
from raavi_ephemeris_vector import VectorizedProvider


class TestJDAndTimezone:
    """Test JD calculation and timezone handling."""

    def test_compute_jd_pair_with_utc(self):
        """Test compute_jd_pair with dt_utc."""
        dt_utc = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.utc)
        tz_offset = 3.5  # Tehran timezone

        tl = TimeLocation(
            dt_utc=dt_utc,
            timezone=tz_offset,
            latitude=35.6892,
            longitude=51.3890
        )

        jd_local, jd_utc = compute_jd_pair(tl)

        # Verify: jd_local = jd_utc + tz/24
        expected_jd_local = jd_utc + tz_offset / 24.0
        assert abs(jd_local - expected_jd_local) < 1e-9, \
            f"jd_local should equal jd_utc + tz/24: {jd_local} vs {expected_jd_local}"

    def test_compute_jd_pair_with_local(self):
        """Test compute_jd_pair with dt_local."""
        dt_local = datetime(2024, 1, 15, 15, 30, 0)  # 15:30 Tehran time
        tz_offset = 3.5

        tl = TimeLocation(
            dt_local=dt_local,
            timezone=tz_offset,
            latitude=35.6892,
            longitude=51.3890
        )

        jd_local, jd_utc = compute_jd_pair(tl)

        # Verify: jd_utc = jd_local - tz/24
        expected_jd_utc = jd_local - tz_offset / 24.0
        assert abs(jd_utc - expected_jd_utc) < 1e-9, \
            f"jd_utc should equal jd_local - tz/24: {jd_utc} vs {expected_jd_utc}"

    def test_timezone_independence(self):
        """Test that same UTC time gives same jd_utc regardless of timezone."""
        dt_utc = datetime(2024, 6, 21, 18, 0, 0, tzinfo=pytz.utc)

        tl1 = TimeLocation(dt_utc=dt_utc, timezone=0.0, latitude=0, longitude=0)
        tl2 = TimeLocation(dt_utc=dt_utc, timezone=5.5, latitude=0, longitude=0)

        _, jd_utc1 = compute_jd_pair(tl1)
        _, jd_utc2 = compute_jd_pair(tl2)

        assert abs(jd_utc1 - jd_utc2) < 1e-9, \
            "Same UTC time should give same jd_utc regardless of timezone offset"


class TestSiderealVsTropical:
    """Test sidereal vs tropical mode differences."""

    def test_ayanamsa_difference(self):
        """Test that sidereal and tropical modes differ by approximately ayanamsa."""
        dt_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(dt_utc=dt_utc, latitude=0, longitude=0)

        # Tropical
        provider_tropical = SwissEphemerisProvider(
            sidereal=False,
            bodies=["Sun", "Moon"]
        )
        frame_tropical = provider_tropical.get_sky_frame(tl)

        # Sidereal (Lahiri)
        provider_sidereal = SwissEphemerisProvider(
            sidereal=True,
            ayanamsa="LAHIRI",
            bodies=["Sun", "Moon"]
        )
        frame_sidereal = provider_sidereal.get_sky_frame(tl)

        # Get expected ayanamsa value from swisseph
        jd = frame_tropical.jd
        # Set Lahiri ayanamsa
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        ayanamsa = swe.get_ayanamsa_ut(jd)

        # Check Sun
        sun_trop = frame_tropical.positions["Sun"].lon
        sun_sid = frame_sidereal.positions["Sun"].lon
        diff = (sun_trop - sun_sid) % 360.0
        if diff > 180:
            diff = diff - 360.0

        assert abs(diff - ayanamsa) < 0.1, \
            f"Tropical-Sidereal difference should be ~ayanamsa: {diff} vs {ayanamsa}"

        # Check Moon
        moon_trop = frame_tropical.positions["Moon"].lon
        moon_sid = frame_sidereal.positions["Moon"].lon
        diff = (moon_trop - moon_sid) % 360.0
        if diff > 180:
            diff = diff - 360.0

        assert abs(diff - ayanamsa) < 0.1, \
            f"Tropical-Sidereal difference should be ~ayanamsa: {diff} vs {ayanamsa}"


class TestRahuKetu:
    """Test Rahu and Ketu node calculations."""

    def test_ketu_opposite_rahu(self):
        """Test that Ketu longitude = Rahu longitude + 180°."""
        dt_utc = datetime(2024, 3, 20, 12, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(dt_utc=dt_utc, latitude=28.6139, longitude=77.2090)

        provider = SwissEphemerisProvider(
            bodies=["Rahu", "Ketu"],
            node_mode="mean"
        )
        frame = provider.get_sky_frame(tl)

        rahu_lon = frame.positions["Rahu"].lon
        ketu_lon = frame.positions["Ketu"].lon

        expected_ketu_lon = (rahu_lon + 180.0) % 360.0

        assert abs(ketu_lon - expected_ketu_lon) < 1e-6, \
            f"Ketu lon should be Rahu lon + 180°: {ketu_lon} vs {expected_ketu_lon}"

    def test_ketu_lat_pyjhora_mode(self):
        """Test that in pyjhora mode, Ketu lat = Rahu lat."""
        dt_utc = datetime(2024, 3, 20, 12, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(dt_utc=dt_utc, latitude=28.6139, longitude=77.2090)

        provider = SwissEphemerisProvider(
            bodies=["Rahu", "Ketu"],
            node_mode="mean",
            ketu_lat_mode="pyjhora"
        )
        frame = provider.get_sky_frame(tl)

        rahu_lat = frame.positions["Rahu"].lat
        ketu_lat = frame.positions["Ketu"].lat

        assert abs(ketu_lat - rahu_lat) < 1e-9, \
            f"In pyjhora mode, Ketu lat should equal Rahu lat: {ketu_lat} vs {rahu_lat}"

    def test_ketu_lat_mirrored_mode(self):
        """Test that in mirrored mode, Ketu lat = -Rahu lat."""
        dt_utc = datetime(2024, 3, 20, 12, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(dt_utc=dt_utc, latitude=28.6139, longitude=77.2090)

        provider = SwissEphemerisProvider(
            bodies=["Rahu", "Ketu"],
            node_mode="mean",
            ketu_lat_mode="mirrored"
        )
        frame = provider.get_sky_frame(tl)

        rahu_lat = frame.positions["Rahu"].lat
        ketu_lat = frame.positions["Ketu"].lat

        assert abs(ketu_lat + rahu_lat) < 1e-9, \
            f"In mirrored mode, Ketu lat should equal -Rahu lat: {ketu_lat} vs {-rahu_lat}"

    def test_mean_vs_true_node(self):
        """Test that mean and true nodes give different results."""
        dt_utc = datetime(2024, 3, 20, 12, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(dt_utc=dt_utc, latitude=28.6139, longitude=77.2090)

        provider_mean = SwissEphemerisProvider(
            bodies=["Rahu"],
            node_mode="mean"
        )
        frame_mean = provider_mean.get_sky_frame(tl)

        provider_true = SwissEphemerisProvider(
            bodies=["Rahu"],
            node_mode="true"
        )
        frame_true = provider_true.get_sky_frame(tl)

        rahu_mean = frame_mean.positions["Rahu"].lon
        rahu_true = frame_true.positions["Rahu"].lon

        # They should be different (usually by a small amount)
        assert abs(rahu_mean - rahu_true) > 0.001, \
            "Mean and true nodes should give different positions"


class TestHouses:
    """Test houses calculation."""

    def test_houses_ex_structure(self):
        """Test that houses_ex returns correct structure."""
        dt_utc = datetime(2024, 1, 1, 12, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(
            dt_utc=dt_utc,
            latitude=35.6892,
            longitude=51.3890
        )

        provider = SwissEphemerisProvider(
            calculate_houses=True,
            house_system="P",
            bodies=["Sun"]
        )
        frame = provider.get_sky_frame(tl)

        assert frame.houses is not None, "Houses should be calculated"
        assert "cusps" in frame.houses, "Houses should contain cusps"
        assert "asc" in frame.houses, "Houses should contain asc"
        assert "mc" in frame.houses, "Houses should contain mc"
        assert len(frame.houses["cusps"]) == 12, "Should have 12 house cusps"

    def test_houses_different_systems(self):
        """Test that different house systems give different results."""
        dt_utc = datetime(2024, 1, 1, 12, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(
            dt_utc=dt_utc,
            latitude=35.6892,
            longitude=51.3890
        )

        provider_placidus = SwissEphemerisProvider(
            calculate_houses=True,
            house_system="P",
            bodies=["Sun"]
        )
        frame_placidus = provider_placidus.get_sky_frame(tl)

        provider_koch = SwissEphemerisProvider(
            calculate_houses=True,
            house_system="K",
            bodies=["Sun"]
        )
        frame_koch = provider_koch.get_sky_frame(tl)

        # ASC and MC should be the same regardless of house system
        assert abs(frame_placidus.houses["asc"] - frame_koch.houses["asc"]) < 0.01, \
            "Ascendant should be same across house systems"
        assert abs(frame_placidus.houses["mc"] - frame_koch.houses["mc"]) < 0.01, \
            "MC should be same across house systems"

        # But cusps should differ (except cusp 1 = ASC, cusp 10 = MC)
        # Check a middle cusp
        assert abs(frame_placidus.houses["cusps"][4] - frame_koch.houses["cusps"][4]) > 0.1, \
            "House cusps should differ between Placidus and Koch"


class TestPlanetaryPositions:
    """Test planetary position accuracy."""

    def test_sun_moon_jupiter_precision(self):
        """Test that major planets have reasonable precision."""
        # Reference date: 2024-01-01 00:00 UTC
        dt_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(dt_utc=dt_utc, latitude=0, longitude=0)

        provider = SwissEphemerisProvider(
            sidereal=False,
            bodies=["Sun", "Moon", "Jupiter"]
        )
        frame = provider.get_sky_frame(tl)

        # Verify we got all three bodies
        assert "Sun" in frame.positions
        assert "Moon" in frame.positions
        assert "Jupiter" in frame.positions

        # Verify positions are in valid range
        sun_lon = frame.positions["Sun"].lon
        moon_lon = frame.positions["Moon"].lon
        jupiter_lon = frame.positions["Jupiter"].lon

        assert 0 <= sun_lon < 360, f"Sun longitude out of range: {sun_lon}"
        assert 0 <= moon_lon < 360, f"Moon longitude out of range: {moon_lon}"
        assert 0 <= jupiter_lon < 360, f"Jupiter longitude out of range: {jupiter_lon}"

        # For 2024-01-01, Sun should be around 280° (Capricorn)
        # This is a rough sanity check
        assert 270 < sun_lon < 290, f"Sun position seems wrong for 2024-01-01: {sun_lon}"

    def test_position_vs_direct_swiss(self):
        """Test that our positions match direct swisseph calls."""
        dt_utc = datetime(2024, 6, 21, 12, 0, 0, tzinfo=pytz.utc)
        tl = TimeLocation(dt_utc=dt_utc, latitude=0, longitude=0)

        provider = SwissEphemerisProvider(
            sidereal=False,
            bodies=["Sun", "Mars"]
        )
        frame = provider.get_sky_frame(tl)

        # Direct swisseph call
        from raavi_ephemeris import BASE_FLAGS
        jd = frame.jd

        # Sun
        sun_direct, _ = swe.calc_ut(jd, swe.SUN, BASE_FLAGS)
        sun_our = frame.positions["Sun"]

        assert abs(sun_our.lon - sun_direct[0]) < 1e-3, \
            f"Sun longitude should match direct swiss: {sun_our.lon} vs {sun_direct[0]}"

        # Mars
        mars_direct, _ = swe.calc_ut(jd, swe.MARS, BASE_FLAGS)
        mars_our = frame.positions["Mars"]

        assert abs(mars_our.lon - mars_direct[0]) < 1e-3, \
            f"Mars longitude should match direct swiss: {mars_our.lon} vs {mars_direct[0]}"


class TestScalarVectorParity:
    """Test that scalar and vector engines give same results."""

    def test_single_time_parity(self):
        """Test that scalar and vector give same result for single time."""
        dt_utc = datetime(2024, 3, 15, 18, 30, 0, tzinfo=pytz.utc)
        tl = TimeLocation(dt_utc=dt_utc, latitude=28.6139, longitude=77.2090)

        bodies = ["Sun", "Moon", "Mars", "Jupiter", "Rahu", "Ketu"]

        # Scalar
        scalar_provider = SwissEphemerisProvider(
            sidereal=True,
            ayanamsa="LAHIRI",
            bodies=bodies,
            node_mode="mean",
            ketu_lat_mode="pyjhora"
        )
        scalar_frame = scalar_provider.get_sky_frame(tl)

        # Vector
        from raavi_ephemeris import VectorizedAdapter, datetime_to_julian
        vector_engine = VectorizedProvider(
            sidereal=True,
            ayanamsa="LAHIRI",
            bodies=bodies,
            node_mode="mean",
            ketu_lat_mode="pyjhora"
        )
        vector_provider = VectorizedAdapter(vector_engine)
        vector_frame = vector_provider.get_sky_frame(tl)

        # Compare positions
        for body in bodies:
            scalar_pos = scalar_frame.positions[body]
            vector_pos = vector_frame.positions[body]

            assert abs(scalar_pos.lon - vector_pos.lon) < 1e-6, \
                f"{body} longitude mismatch: scalar={scalar_pos.lon}, vector={vector_pos.lon}"
            assert abs(scalar_pos.lat - vector_pos.lat) < 1e-6, \
                f"{body} latitude mismatch: scalar={scalar_pos.lat}, vector={vector_pos.lat}"

    def test_batch_rahu_ketu(self):
        """Test that vector engine correctly calculates Rahu/Ketu in batch."""
        jds = np.array([
            2460000.0,  # Some arbitrary JDs
            2460001.0,
            2460002.0,
        ])

        vector_engine = VectorizedProvider(
            sidereal=False,
            bodies=["Rahu", "Ketu"],
            node_mode="mean",
            ketu_lat_mode="pyjhora"
        )

        batch = vector_engine.calculate_batch(jds)

        for i in range(len(jds)):
            frame = batch.get_frame(i)
            rahu = frame.get_position("Rahu")
            ketu = frame.get_position("Ketu")

            # Ketu lon = Rahu lon + 180
            expected_ketu_lon = (rahu.longitude + 180.0) % 360.0
            assert abs(ketu.longitude - expected_ketu_lon) < 1e-6, \
                f"Ketu lon should be Rahu lon + 180: {ketu.longitude} vs {expected_ketu_lon}"

            # Ketu lat = Rahu lat (pyjhora mode)
            assert abs(ketu.latitude - rahu.latitude) < 1e-9, \
                f"Ketu lat should equal Rahu lat in pyjhora mode"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
