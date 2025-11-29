import pytz
from datetime import datetime

from raavi_ephemeris import TimeLocation, get_default_provider, SkyFrame, SkyPosition
from logic.shadbala import (
    calculate_uchcha_bala,
    calculate_dig_bala,
    calculate_naisargika_bala,
    calculate_shadbala_for_frame,
    calculate_sthana_bala,
    summarize_shadbala,
    classify_shadbala,
    calculate_chesta_bala,
    calculate_kaala_bala,
    calculate_drik_bala,
)


TEHRAN = pytz.timezone("Asia/Tehran")


def test_uchcha_bala_sun_in_aries():
    # Sun exactly at 10° Aries (its exaltation point) should be near max Uchcha Bala (~60)
    lon = 10.0
    bala = calculate_uchcha_bala("Sun", lon)
    assert 59.0 <= bala <= 60.0


def test_dig_bala_sun_in_10th_house():
    # Sun zero-strength house = 4th; max strength at 10th.
    # Distance = 6 houses => arc = 180 -> bala = 60
    bala = calculate_dig_bala("Sun", house_from_asc=10)
    assert bala == 60.0


def test_naisargika_bala_static_values():
    # Simple static checks
    assert calculate_naisargika_bala("Sun") == 60.0
    assert calculate_naisargika_bala("Saturn") == 8.57
    assert calculate_naisargika_bala("Rahu") == 0.0


def test_shadbala_integration_with_chart_calculator():
    from chart_calculator import ChartCalculator

    tz = TEHRAN
    local_dt = tz.localize(datetime(2000, 1, 1, 12, 0))
    utc_dt = local_dt.astimezone(pytz.utc)

    provider = get_default_provider(
        calculate_houses=True,
        house_system="P",
        sidereal=True,
        ayanamsa="LAHIRI",
    )

    tl = TimeLocation(dt_utc=utc_dt, latitude=35.6892, longitude=51.3890)
    frame = provider.get_sky_frame(tl)

    shadbala_map = calculate_shadbala_for_frame(frame)
    # Must contain 7 classical planets
    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        assert planet in shadbala_map
        comp = shadbala_map[planet]
        assert comp.total >= comp.naisargika  # at least Naisargika component present


def test_sthana_bala_components_sun_exalted_kendra():
    # Synthetic frame: Ascendant in Cancer (sign 3), Sun in Aries 5° (sign 0)
    # -> Sun is in 10th house from asc (Kendra), near exaltation point, in odd sign.
    asc_lon = 3 * 30.0  # Cancer
    sun_lon = 5.0       # 5° Aries

    sun = SkyPosition(body_id="Sun", jd=0.0, lon=sun_lon, lat=0.0, speed_lon=0.98)
    positions = {"Sun": sun}
    houses = {"system": "P", "cusps": [0.0] * 12, "asc": asc_lon, "mc": 0.0}
    frame = SkyFrame(jd=2451544.5, positions=positions, houses=houses)

    lon_norm = sun_lon % 360.0
    house_from_asc = 10  # by construction: Aries is 10th from Cancer

    # No vargas/maitri -> Saptavargaja & Ojayugma = 0.
    sthana = calculate_sthana_bala(
        "Sun",
        lon_norm,
        frame,
        vargas=None,
        compound_maitri=None,
        house_from_asc=house_from_asc,
    )

    uchcha = calculate_uchcha_bala("Sun", lon_norm)
    # Drekkana: Sun (male) in first decanate (0-10) -> +15
    # Kendra: 10th house -> +60
    expected_min = uchcha + 60.0 + 15.0

    assert sthana >= expected_min


def _make_simple_frame_for_time(hour: int) -> SkyFrame:
    """
    Construct a minimal SkyFrame with Sun and Moon positions and a given UTC hour.
    Longitudes are arbitrary but consistent for Paksha computation.
    """
    dt = datetime(2000, 1, 1, hour, 0, tzinfo=pytz.utc)
    sun = SkyPosition(body_id="Sun", jd=0.0, lon=0.0, lat=0.0, speed_lon=0.98)
    # Full Moon opposite the Sun for maximum Paksha contrast
    moon = SkyPosition(body_id="Moon", jd=0.0, lon=180.0, lat=0.0, speed_lon=13.0)
    positions = {"Sun": sun, "Moon": moon}
    return SkyFrame(jd=2451544.5, positions=positions, utc_datetime=dt)


def test_chesta_bala_retrograde_mars():
    # Retrograde Mars should receive maximum Chesta Bala (60)
    mars = SkyPosition(body_id="Mars", jd=0.0, lon=0.0, lat=0.0, speed_lon=-0.5)
    frame = SkyFrame(jd=0.0, positions={"Mars": mars})
    bala = calculate_chesta_bala("Mars", frame)
    assert bala == 60.0


def test_kaala_bala_sun_noon_vs_midnight():
    # Sun should have higher Kaala Bala at (UTC) noon than at midnight
    frame_midnight = _make_simple_frame_for_time(0)
    frame_noon = _make_simple_frame_for_time(12)

    bala_midnight = calculate_kaala_bala("Sun", frame_midnight)
    bala_noon = calculate_kaala_bala("Sun", frame_noon)

    assert bala_noon > bala_midnight


def test_drik_bala_benefic_aspect_increases_strength():
    # Jupiter trine Moon should give Moon a positive Drik Bala
    moon = SkyPosition(body_id="Moon", jd=0.0, lon=0.0, lat=0.0, speed_lon=13.0)
    jupiter = SkyPosition(body_id="Jupiter", jd=0.0, lon=120.0, lat=0.0, speed_lon=0.08)
    positions = {"Moon": moon, "Jupiter": jupiter}
    frame = SkyFrame(jd=2451544.5, positions=positions)

    bala = calculate_drik_bala("Moon", frame)
    assert bala > 0.0


def test_shadbala_summary_ishta_kashta():
    # Build a simple synthetic Shadbala map for Sun and Saturn
    from logic.shadbala import ShadbalaComponents

    sun_comp = ShadbalaComponents(
        sthana=180.0,  # 3 rupas
        dig=60.0,
        kaala=60.0,
        chesta=60.0,
        naisargika=60.0,
        drik=60.0,
    )  # total = 480 -> 8 rupas, min = 5, ishta = 3, kashta = 0
    saturn_comp = ShadbalaComponents(
        sthana=60.0,
        dig=30.0,
        kaala=30.0,
        chesta=30.0,
        naisargika=8.57,
        drik=30.0,
    )  # total ~= 188.57 -> ~3.14 rupas, min = 5, ishta = 0, kashta > 0

    shadbala_map = {"Sun": sun_comp, "Saturn": saturn_comp}
    summary = summarize_shadbala(shadbala_map)

    assert "Sun" in summary and "Saturn" in summary

    sun = summary["Sun"]
    assert sun["rupas"] > sun["minimum_req"]
    assert sun["ishta_score"] > 0.0
    assert sun["kashta_score"] == 0.0

    sat = summary["Saturn"]
    assert sat["rupas"] < sat["minimum_req"]
    assert sat["ishta_score"] == 0.0
    assert sat["kashta_score"] > 0.0

    overview = classify_shadbala(summary)
    assert "Sun" in overview["strong_planets"]
    assert "Saturn" in overview["weak_planets"]
