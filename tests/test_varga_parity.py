from logic.varga_engine import calculate_all_vargas


def _extract_sign(vargas: dict, varga_name: str, planet: str) -> int:
    return int(vargas[varga_name][planet]["sign"])


def _build_single_longitude(lon: float) -> dict:
    return {"TestPlanet": lon}


def test_d10_harmonic_mid_sign():
    # 15° absolute longitude -> D10 harmonic: (15*10) % 360 = 150° -> sign 5 (Virgo)
    lons = _build_single_longitude(15.0)
    vargas = calculate_all_vargas(lons)
    sign_d10 = _extract_sign(vargas, "D10", "TestPlanet")
    assert sign_d10 == 5


def test_d2_hora_parashara():
    # Sun in Aries 10° (10.0) -> D2 Hora: Leo (4)
    lons = _build_single_longitude(10.0)  # 0*30 + 10
    vargas = calculate_all_vargas(lons)
    sign_d2 = _extract_sign(vargas, "D2", "TestPlanet")
    assert sign_d2 == 4


def test_d9_navamsa_parashara():
    # Sun in Aries 29° -> D9 Navamsa: Sagittarius (8)
    lons = _build_single_longitude(29.0)
    vargas = calculate_all_vargas(lons)
    sign_d9 = _extract_sign(vargas, "D9", "TestPlanet")
    assert sign_d9 == 8


def test_d30_trimsamsa_piecewise():
    # Jupiter in Taurus 15° -> Taurus index=1, 15° in [12,20) -> Pisces (11)
    lons = _build_single_longitude(30.0 + 15.0)
    vargas = calculate_all_vargas(lons)
    sign_d30 = _extract_sign(vargas, "D30", "TestPlanet")
    assert sign_d30 == 11


def test_chart_calculator_includes_vargas():
    # Integration smoke test: verify that ChartCalculator returns a 'vargas' block.
    import pytz
    from datetime import datetime

    from chart_calculator import ChartCalculator

    tz = pytz.timezone("Asia/Tehran")
    local_dt = tz.localize(datetime(2025, 1, 1, 12, 0))
    utc_dt = local_dt.astimezone(pytz.utc)

    calc = ChartCalculator(sidereal=True, ayanamsa="LAHIRI")
    data = calc.calculate_dict(utc_dt, lat=35.6892, lon=51.3890, name="Sample")

    assert "vargas" in data
    vargas = data["vargas"]
    # Check that some standard vargas exist and contain Sun
    for name in ["D1", "D2", "D9", "D30"]:
        assert name in vargas
        assert "Sun" in vargas[name]

