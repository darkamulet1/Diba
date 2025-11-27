"""
Manual test for PyJhora contract - runs without pytest.
"""

from datetime import datetime
import pytz
import numpy as np

from raavi_ephemeris import (
    TimeLocation,
    SwissEphemerisProvider,
    compute_jd_pair,
    VectorizedAdapter
)
from raavi_ephemeris_vector import VectorizedProvider


def test_jd_calculation():
    """Test JD calculation."""
    print("\n=== Testing JD Calculation ===")

    dt_utc = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.utc)
    tz_offset = 3.5

    tl = TimeLocation(
        dt_utc=dt_utc,
        timezone=tz_offset,
        latitude=35.6892,
        longitude=51.3890
    )

    jd_local, jd_utc = compute_jd_pair(tl)

    expected_jd_local = jd_utc + tz_offset / 24.0
    diff = abs(jd_local - expected_jd_local)

    print(f"  jd_utc: {jd_utc}")
    print(f"  jd_local: {jd_local}")
    print(f"  expected_jd_local: {expected_jd_local}")
    print(f"  difference: {diff}")
    print(f"  ✓ PASS" if diff < 1e-9 else "  ✗ FAIL")

    return diff < 1e-9


def test_rahu_ketu():
    """Test Rahu/Ketu calculation."""
    print("\n=== Testing Rahu/Ketu ===")

    dt_utc = datetime(2024, 3, 20, 12, 0, 0, tzinfo=pytz.utc)
    tl = TimeLocation(dt_utc=dt_utc, latitude=28.6139, longitude=77.2090)

    provider = SwissEphemerisProvider(
        bodies=["Rahu", "Ketu"],
        node_mode="mean",
        ketu_lat_mode="pyjhora"
    )
    frame = provider.get_sky_frame(tl)

    rahu_lon = frame.positions["Rahu"].lon
    ketu_lon = frame.positions["Ketu"].lon
    rahu_lat = frame.positions["Rahu"].lat
    ketu_lat = frame.positions["Ketu"].lat

    expected_ketu_lon = (rahu_lon + 180.0) % 360.0
    lon_diff = abs(ketu_lon - expected_ketu_lon)
    lat_diff = abs(ketu_lat - rahu_lat)

    print(f"  Rahu lon: {rahu_lon:.6f}°")
    print(f"  Ketu lon: {ketu_lon:.6f}°")
    print(f"  Expected Ketu lon: {expected_ketu_lon:.6f}°")
    print(f"  Longitude difference: {lon_diff}")
    print(f"  Latitude difference: {lat_diff}")
    print(f"  ✓ PASS" if (lon_diff < 1e-6 and lat_diff < 1e-9) else "  ✗ FAIL")

    return lon_diff < 1e-6 and lat_diff < 1e-9


def test_houses():
    """Test houses calculation."""
    print("\n=== Testing Houses ===")

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

    has_houses = frame.houses is not None
    has_cusps = "cusps" in frame.houses if has_houses else False
    has_asc = "asc" in frame.houses if has_houses else False
    has_mc = "mc" in frame.houses if has_houses else False
    correct_cusp_count = len(frame.houses["cusps"]) == 12 if has_cusps else False

    print(f"  Houses calculated: {has_houses}")
    if has_houses:
        print(f"  Has cusps: {has_cusps}")
        print(f"  Has ASC: {has_asc}")
        print(f"  Has MC: {has_mc}")
        print(f"  Cusp count: {len(frame.houses['cusps']) if has_cusps else 0}")
        print(f"  ASC: {frame.houses['asc']:.4f}°" if has_asc else "")
        print(f"  MC: {frame.houses['mc']:.4f}°" if has_mc else "")

    passed = has_houses and has_cusps and has_asc and has_mc and correct_cusp_count
    print(f"  ✓ PASS" if passed else "  ✗ FAIL")

    return passed


def test_sidereal_vs_tropical():
    """Test sidereal vs tropical difference."""
    print("\n=== Testing Sidereal vs Tropical ===")

    dt_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
    tl = TimeLocation(dt_utc=dt_utc, latitude=0, longitude=0)

    # Tropical
    provider_tropical = SwissEphemerisProvider(
        sidereal=False,
        bodies=["Sun"]
    )
    frame_tropical = provider_tropical.get_sky_frame(tl)

    # Sidereal
    provider_sidereal = SwissEphemerisProvider(
        sidereal=True,
        ayanamsa="LAHIRI",
        bodies=["Sun"]
    )
    frame_sidereal = provider_sidereal.get_sky_frame(tl)

    sun_trop = frame_tropical.positions["Sun"].lon
    sun_sid = frame_sidereal.positions["Sun"].lon
    diff = sun_trop - sun_sid

    # Expected ayanamsa ~24° for 2024
    print(f"  Tropical Sun: {sun_trop:.4f}°")
    print(f"  Sidereal Sun: {sun_sid:.4f}°")
    print(f"  Difference: {diff:.4f}°")
    print(f"  Expected ~24° (Lahiri ayanamsa for 2024)")

    passed = 23 < diff < 25
    print(f"  ✓ PASS" if passed else "  ✗ FAIL")

    return passed


def test_scalar_vector_parity():
    """Test scalar and vector engine parity."""
    print("\n=== Testing Scalar/Vector Parity ===")

    dt_utc = datetime(2024, 3, 15, 18, 30, 0, tzinfo=pytz.utc)
    tl = TimeLocation(dt_utc=dt_utc, latitude=28.6139, longitude=77.2090)

    bodies = ["Sun", "Moon", "Mars", "Rahu", "Ketu"]

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
    vector_engine = VectorizedProvider(
        sidereal=True,
        ayanamsa="LAHIRI",
        bodies=bodies,
        node_mode="mean",
        ketu_lat_mode="pyjhora"
    )
    vector_provider = VectorizedAdapter(vector_engine)
    vector_frame = vector_provider.get_sky_frame(tl)

    all_passed = True
    max_lon_diff = 0
    max_lat_diff = 0

    for body in bodies:
        scalar_pos = scalar_frame.positions[body]
        vector_pos = vector_frame.positions[body]

        lon_diff = abs(scalar_pos.lon - vector_pos.lon)
        lat_diff = abs(scalar_pos.lat - vector_pos.lat)

        max_lon_diff = max(max_lon_diff, lon_diff)
        max_lat_diff = max(max_lat_diff, lat_diff)

        passed = lon_diff < 1e-6 and lat_diff < 1e-6
        all_passed = all_passed and passed

        print(f"  {body:8s}: lon_diff={lon_diff:.9f}°, lat_diff={lat_diff:.9f}° {'✓' if passed else '✗'}")

    print(f"\n  Max longitude diff: {max_lon_diff:.9f}°")
    print(f"  Max latitude diff: {max_lat_diff:.9f}°")
    print(f"  ✓ PASS" if all_passed else "  ✗ FAIL")

    return all_passed


def main():
    """Run all tests."""
    print("=" * 60)
    print("PyJhora Contract Compliance Tests")
    print("=" * 60)

    tests = [
        ("JD Calculation", test_jd_calculation),
        ("Rahu/Ketu", test_rahu_ketu),
        ("Houses", test_houses),
        ("Sidereal vs Tropical", test_sidereal_vs_tropical),
        ("Scalar/Vector Parity", test_scalar_vector_parity),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  ✗ ERROR: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name:25s}: {status}")

    print(f"\n  Total: {passed_count}/{total_count} passed")
    print("=" * 60)

    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
