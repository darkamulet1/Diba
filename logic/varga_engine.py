"""
Pure logic Varga (Divisional Chart) engine for Raavi.

This module operates only on longitudes and does not depend on Swiss Ephemeris.
It implements standard Parashara-style divisional charts (D1..D60) with a mix
of rule-based and harmonic methods, closely aligned with PyJHora.

Input:
    d1_longitudes: Dict[str, float]  # absolute longitudes 0..360 (sidereal)

Output:
    Dict[str, Dict[str, Dict[str, float]]]
        {
            "D9": {
                "Sun": {"sign": 8, "degree_in_sign": 12.34},
                ...
            },
            ...
        }
"""

from typing import Dict, Mapping, Tuple


def _normalize_lon(lon: float) -> float:
    """Normalize any longitude to [0, 360)."""
    return lon % 360.0


def _split_sign(lon: float) -> Tuple[int, float]:
    """Return (sign_index, degree_in_sign) from absolute longitude."""
    lon_n = _normalize_lon(lon)
    sign = int(lon_n // 30.0)
    deg_in_sign = lon_n - 30.0 * sign
    return sign, deg_in_sign


def _harmonic_varga(lon: float, division: int) -> Tuple[int, float]:
    """
    Harmonic varga logic:
        varga_lon = (lon * division) % 360
    """
    lon_n = _normalize_lon(lon)
    vlon = (lon_n * float(division)) % 360.0
    sign = int(vlon // 30.0)
    deg_in_sign = vlon - 30.0 * sign
    return sign, deg_in_sign


def _d1_rasi(lon: float) -> Tuple[int, float]:
    return _split_sign(lon)


def _d2_hora(lon: float) -> Tuple[int, float]:
    """
    D2 – Hora, Traditional Parashara:
        Odd signs:
            0-15° -> Leo (4)
            15-30° -> Cancer (3)
        Even signs:
            0-15° -> Cancer (3)
            15-30° -> Leo (4)
    """
    sign, deg = _split_sign(lon)
    is_odd = sign % 2 == 0  # 0,2,4,.. treated as odd signs in index
    if deg < 15.0:
        varga_sign = 4 if is_odd else 3
    else:
        varga_sign = 3 if is_odd else 4
    varga_deg = (deg * 2.0) % 30.0
    return varga_sign, varga_deg


def _d3_drekkana(lon: float) -> Tuple[int, float]:
    """
    D3 – Drekkana, Parashara:
        0-10°  -> same sign
        10-20° -> 5th from sign
        20-30° -> 9th from sign
    """
    sign, deg = _split_sign(lon)
    width = 10.0
    idx = int(deg // width)  # 0,1,2
    varga_sign = (sign + 4 * idx) % 12
    varga_deg = (deg * 3.0) % 30.0
    return varga_sign, varga_deg


def _d4_chaturthamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 4)


def _d7_saptamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 7)


def _d9_navamsa(lon: float) -> Tuple[int, float]:
    """
    D9 – Navamsa, Traditional Parashara.

    Fire signs (Ar, Le, Sg) start from Aries(0).
    Earth signs (Ta, Vi, Cp) start from Capricorn(9).
    Air signs (Ge, Li, Aq) start from Libra(6).
    Water signs (Cn, Sc, Pi) start from Cancer(3).
    """
    sign, deg = _split_sign(lon)
    width = 30.0 / 9.0
    idx = int(deg // width)

    fire = {0, 4, 8}
    earth = {1, 5, 9}
    air = {2, 6, 10}
    water = {3, 7, 11}

    if sign in fire:
        seed = 0
    elif sign in water:
        seed = 3
    elif sign in air:
        seed = 6
    else:
        seed = 9

    varga_sign = (seed + idx) % 12
    varga_deg = (deg * 9.0) % 30.0
    return varga_sign, varga_deg


def _d10_dasamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 10)


def _d12_dwadasamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 12)


def _d16_shodasamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 16)


def _d20_vimsamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 20)


def _d24_chaturvimsamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 24)


def _d27_nakshatramsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 27)


def _d30_trimsamsa(lon: float) -> Tuple[int, float]:
    """
    D30 – Trimsamsa, Parashara piecewise mapping.

    Odd signs:
        0-5   -> Aries (0)
        5-10  -> Aquarius (10)
        10-18 -> Scorpio (8)
        18-25 -> Gemini (2)
        25-30 -> Virgo (6)
    Even signs:
        0-5   -> Taurus (1)
        5-12  -> Virgo (5)
        12-20 -> Pisces (11)
        20-25 -> Capricorn (9)
        25-30 -> Scorpio (7)
    """
    sign, deg = _split_sign(lon)
    vdeg = (deg * 30.0) % 30.0  # keep internal degree scaled similarly

    odd_signs = {0, 2, 4, 6, 8, 10}

    if sign in odd_signs:
        if 0.0 <= deg < 5.0:
            varga_sign = 0
        elif 5.0 <= deg < 10.0:
            varga_sign = 10
        elif 10.0 <= deg < 18.0:
            varga_sign = 8
        elif 18.0 <= deg < 25.0:
            varga_sign = 2
        else:
            varga_sign = 6
    else:
        if 0.0 <= deg < 5.0:
            varga_sign = 1
        elif 5.0 <= deg < 12.0:
            varga_sign = 5
        elif 12.0 <= deg < 20.0:
            varga_sign = 11
        elif 20.0 <= deg < 25.0:
            varga_sign = 9
        else:
            varga_sign = 7
    return varga_sign, vdeg


def _d40_khavedamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 40)


def _d45_akshavedamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 45)


def _d60_shashtyamsa(lon: float) -> Tuple[int, float]:
    return _harmonic_varga(lon, 60)


# Mapping from varga name to its computation function.
_VARGA_FUNCTIONS = {
    "D1": _d1_rasi,
    "D2": _d2_hora,
    "D3": _d3_drekkana,
    "D4": _d4_chaturthamsa,
    "D7": _d7_saptamsa,
    "D9": _d9_navamsa,
    "D10": _d10_dasamsa,
    "D12": _d12_dwadasamsa,
    "D16": _d16_shodasamsa,
    "D20": _d20_vimsamsa,
    "D24": _d24_chaturvimsamsa,
    "D27": _d27_nakshatramsa,
    "D30": _d30_trimsamsa,
    "D40": _d40_khavedamsa,
    "D45": _d45_akshavedamsa,
    "D60": _d60_shashtyamsa,
}


def calculate_all_vargas(
    d1_longitudes: Mapping[str, float],
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Compute all configured Vargas from D1 longitudes.

    Args:
        d1_longitudes: dict[planet_name] = absolute longitude (0..360).

    Returns:
        dict[varga_name][planet] = {"sign": int, "degree_in_sign": float}
    """
    result: Dict[str, Dict[str, Dict[str, float]]] = {}

    for varga_name, fn in _VARGA_FUNCTIONS.items():
        per_planet: Dict[str, Dict[str, float]] = {}
        for body, lon in d1_longitudes.items():
            sign, deg = fn(lon)
            per_planet[body] = {
                "sign": float(sign),
                "degree_in_sign": float(deg),
            }
        result[varga_name] = per_planet

    return result

