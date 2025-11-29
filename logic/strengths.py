"""
Logic for Planetary Strengths (Bala), specifically Vimsopaka Bala.
"""

from typing import Dict, Mapping

from .maitri import (
    PLANETS,
    compute_compound_maitri,
    COMPOUND_ADHIMITRA,
    COMPOUND_MITRA,
    COMPOUND_SAMA,
    COMPOUND_SATRU,
    COMPOUND_ADHISATRU,
)

# Sign Lords (0=Aries ... 11=Pisces)
SIGN_LORDS = [
    "Mars",
    "Venus",
    "Mercury",
    "Moon",
    "Sun",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Saturn",
    "Jupiter",
]

# Exaltation Signs (sign index)
EXALTATION_SIGNS = {
    "Sun": 0,  # Aries
    "Moon": 1,  # Taurus
    "Mars": 9,  # Capricorn
    "Mercury": 5,  # Virgo
    "Jupiter": 3,  # Cancer
    "Venus": 11,  # Pisces
    "Saturn": 6,  # Libra
    "Rahu": 1,  # Taurus (standard)
    "Ketu": 7,  # Scorpio (standard)
}

# Own Signs (Swakshetra)
OWN_SIGNS = {
    "Sun": [4],
    "Moon": [3],
    "Mars": [0, 7],
    "Mercury": [2, 5],
    "Jupiter": [8, 11],
    "Venus": [1, 6],
    "Saturn": [9, 10],
    "Rahu": [10],  # Aquarius (co-lord)
    "Ketu": [7],  # Scorpio (co-lord)
}

# Vimsopaka Scores (Standard Dasha Varga Scheme)
SCORE_OWN_EXALTED = 20
SCORE_ADHIMITRA = 18
SCORE_MITRA = 15
SCORE_SAMA = 10
SCORE_SATRU = 7
SCORE_ADHISATRU = 5


def calculate_vimsopaka_score(planet_signs: Dict[str, int]) -> Dict[str, int]:
    """
    Calculates the Vimsopaka score for each planet in the given chart (D1, D9, etc.).
    This is the score for a *single* varga chart.

    Args:
        planet_signs: dict[planet_name] = sign_index (0..11)

    Returns:
        dict[planet_name] = score in {5,7,10,15,18,20}
    """
    compound_rels = compute_compound_maitri(planet_signs)
    scores: Dict[str, int] = {}

    for planet, sign in planet_signs.items():
        if planet not in PLANETS:
            continue

        lord = SIGN_LORDS[sign]

        # 1. Check Own Sign (Swakshetra)
        if sign in OWN_SIGNS.get(planet, []):
            scores[planet] = SCORE_OWN_EXALTED
            continue

        # 2. Check Exaltation (Ucca)
        if sign == EXALTATION_SIGNS.get(planet, -1):
            scores[planet] = SCORE_OWN_EXALTED
            continue

        # 3. Check Relationship with Sign Lord
        rel = compound_rels[planet].get(lord, COMPOUND_SAMA)

        if rel == COMPOUND_ADHIMITRA:
            scores[planet] = SCORE_ADHIMITRA
        elif rel == COMPOUND_MITRA:
            scores[planet] = SCORE_MITRA
        elif rel == COMPOUND_SAMA:
            scores[planet] = SCORE_SAMA
        elif rel == COMPOUND_SATRU:
            scores[planet] = SCORE_SATRU
        elif rel == COMPOUND_ADHISATRU:
            scores[planet] = SCORE_ADHISATRU
        else:
            scores[planet] = SCORE_SAMA

    return scores


# ---------------------------------------------------------------------------
# Multi-Varga Vimsopaka (weighted across varga groups)
# ---------------------------------------------------------------------------

# Varga group weights – factors are D-N numbers.
SHADVARGA_WEIGHTS = {
    1: 6.0,
    2: 2.0,
    3: 4.0,
    9: 5.0,
    12: 2.0,
    30: 1.0,
}

SAPTAVARGA_WEIGHTS = {
    1: 5.0,
    2: 2.0,
    3: 3.0,
    7: 2.5,
    9: 4.5,
    12: 2.0,
    30: 1.0,
}

DASAVARGA_WEIGHTS = {
    1: 3.0,
    2: 1.5,
    3: 1.5,
    7: 1.5,
    9: 1.5,
    10: 1.5,
    12: 1.5,
    16: 1.5,
    30: 1.5,
    60: 4.0,
}

SHODASAVARGA_WEIGHTS = {
    1: 3.5,
    2: 1.0,
    3: 1.0,
    4: 0.5,
    7: 0.5,
    9: 3.0,
    10: 0.5,
    12: 0.5,
    16: 2.0,
    20: 0.5,
    24: 0.5,
    27: 0.5,
    30: 1.0,
    40: 0.5,
    45: 0.5,
    60: 4.0,
}

VARGA_GROUPS = {
    "Shadvarga": SHADVARGA_WEIGHTS,
    "Saptavarga": SAPTAVARGA_WEIGHTS,
    "Dasavarga": DASAVARGA_WEIGHTS,
    "Shodasavarga": SHODASAVARGA_WEIGHTS,
}


def _single_chart_score_from_sign(
    planet: str,
    sign: int,
    compound_maitri_d1: Mapping[str, Mapping[str, str]],
) -> int:
    """
    Single chart Vimsopaka score for a given planet in a given sign, using
    D1-based compound Maitri as the relational basis.
    """
    if planet not in PLANETS:
        return SCORE_SAMA

    # Own sign or exaltation dominate
    if sign in OWN_SIGNS.get(planet, []):
        return SCORE_OWN_EXALTED
    if sign == EXALTATION_SIGNS.get(planet, -1):
        return SCORE_OWN_EXALTED

    lord = SIGN_LORDS[sign]
    rel = compound_maitri_d1.get(planet, {}).get(lord, COMPOUND_SAMA)

    if rel == COMPOUND_ADHIMITRA:
        return SCORE_ADHIMITRA
    if rel == COMPOUND_MITRA:
        return SCORE_MITRA
    if rel == COMPOUND_SATRU:
        return SCORE_SATRU
    if rel == COMPOUND_ADHISATRU:
        return SCORE_ADHISATRU
    return SCORE_SAMA


def calculate_weighted_vimsopaka_for_planet(
    planet: str,
    varga_positions: Mapping[int, int],
    compound_maitri_d1: Mapping[str, Mapping[str, str]],
) -> Dict[str, float]:
    """
    Calculate weighted Vimsopaka Bala of a planet across standard varga groups.

    Args:
        planet: name of the planet (e.g., \"Sun\").
        varga_positions: mapping of divisional factor N -> sign index (0..11),
                         e.g. {1: sign_D1, 2: sign_D2, 9: sign_D9, ...}.
        compound_maitri_d1: D1-based compound relationships (from Maitri) in the
                            form compound_maitri[planet][other] = COMPOUND_*.

    Returns:
        dict with keys \"Shadvarga\", \"Saptavarga\", \"Dasavarga\", \"Shodasavarga\"
        and values in the range [5, 20] depending on available vargas.
    """
    results: Dict[str, float] = {}

    for group_name, weights in VARGA_GROUPS.items():
        total_weight = 0.0
        weighted_sum = 0.0

        for factor, weight in weights.items():
            sign = varga_positions.get(factor)
            if sign is None:
                continue
            score = _single_chart_score_from_sign(planet, sign, compound_maitri_d1)
            weighted_sum += weight * float(score)
            total_weight += weight

        if total_weight > 0:
            results[group_name] = weighted_sum / total_weight
        else:
            results[group_name] = 0.0

    return results
