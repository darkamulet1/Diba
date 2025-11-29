"""
Shadbala Engine (Phase 7+) for Raavi.

Implements core components of Parashari Shadbala with PyJHora-style structure:
    - Sthana Bala (Positional):
        * Uchcha Bala (exaltation)
        * Saptavargaja Bala (7-varga strength)
        * Ojayugma Bala (odd/even sign & navamsa)
        * Kendra Bala (angular house strength)
        * Drekkana Bala (decanate strength)
    - Dig Bala   (Directional, house-based)
    - Kaala Bala (Time-based, simplified but structured)
    - Chesta Bala (Motion-based, simplified but structured)
    - Naisargika Bala (Natural)
    - Drik Bala (Aspect-based, simplified)

Units: Virupas (1 Rupa = 60 Virupas).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional
import math

from raavi_ephemeris import SkyFrame  # type: ignore
from .maitri import (
    PLANETS,
    COMPOUND_ADHIMITRA,
    COMPOUND_MITRA,
    COMPOUND_SAMA,
    COMPOUND_SATRU,
    COMPOUND_ADHISATRU,
)
from .aspects import compute_aspects_for_frame
from . import strengths


# ---------------------------------------------------------------------------
# Naisargika Bala (Natural strength, static)
# ---------------------------------------------------------------------------

NAISARGIKA_BALA: Dict[str, float] = {
    "Sun": 60.0,
    "Moon": 51.43,
    "Mars": 17.14,
    "Mercury": 25.71,
    "Jupiter": 34.28,
    "Venus": 42.85,
    "Saturn": 8.57,
}

# Minimum required Shadbala (in Rupas) per planet, based on classical
# Parashari / PyJHora thresholds (Sun..Saturn).
MIN_SHADBALA_RUPAS: Dict[str, float] = {
    "Sun": 5.0,
    "Moon": 6.0,
    "Mars": 5.0,
    "Mercury": 7.0,
    "Jupiter": 6.5,
    "Venus": 5.5,
    "Saturn": 5.0,
}


# ---------------------------------------------------------------------------
# Exaltation points (absolute longitudes in degrees)
# ---------------------------------------------------------------------------

EXALTATION_POINTS: Dict[str, float] = {
    "Sun": 10.0,          # 10° Aries
    "Moon": 30.0 + 3.0,   # 3° Taurus
    "Mars": 270.0 + 28.0, # 28° Capricorn
    "Mercury": 150.0 + 15.0,  # 15° Virgo
    "Jupiter": 90.0 + 5.0,    # 5° Cancer
    "Venus": 330.0 + 27.0,    # 27° Pisces
    "Saturn": 180.0 + 20.0,   # 20° Libra
}


def _normalize_lon(lon: float) -> float:
    return lon % 360.0


def calculate_uchcha_bala(planet: str, lon: float) -> float:
    """
    Uchcha Bala (Exaltation strength).

    Formula (simplified Parashari style):
        diff = |lon - exalt_point|  (wrapped to 0..360)
        arc = |180 - diff|
        uchcha_bala = (1/3) * arc    (max 60 when lon == exalt_point)
    """
    if planet not in EXALTATION_POINTS:
        return 0.0

    lon_n = _normalize_lon(lon)
    exalt = EXALTATION_POINTS[planet]
    diff = abs(lon_n - exalt)
    diff = diff % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    arc = abs(180.0 - diff)
    uchcha_bala = arc / 3.0
    if uchcha_bala < 0.0:
        return 0.0
    if uchcha_bala > 60.0:
        return 60.0
    return uchcha_bala


# ---------------------------------------------------------------------------
# Sthana Bala subcomponents �?" Saptavargaja, Ojayugma, Kendra, Drekkana
# ---------------------------------------------------------------------------

SAPTAVARGA_CHARTS = ("D1", "D2", "D3", "D7", "D9", "D12", "D30")

DEBILITATION_SIGNS: Dict[str, int] = {
    "Sun": 6,      # Libra
    "Moon": 7,     # Scorpio
    "Mars": 3,     # Cancer
    "Mercury": 11, # Pisces
    "Jupiter": 9,  # Capricorn
    "Venus": 5,    # Virgo
    "Saturn": 0,   # Aries
}


def _calculate_saptavargaja_bala(
    planet: str,
    vargas: Mapping[str, Mapping[str, Mapping[str, float]]],
    compound_maitri_d1: Mapping[str, Mapping[str, str]],
) -> float:
    """
    Saptavargaja Bala component for a planet.

    Uses 7 divisional charts: D1, D2, D3, D7, D9, D12, D30.
    Scoring (per varga, Parashari-style, in Virupas):
        - Own / Exalted sign: 45
        - Adhimitra: 40
        - Mitra: 30
        - Sama: 20
        - Satru: 15
        - Adhisatru: 10
        - Debilitated: 2
    Total Saptavargaja Bala is the sum over the 7 vargas.
    """
    if planet not in NAISARGIKA_BALA:
        return 0.0

    total = 0.0
    for vname in SAPTAVARGA_CHARTS:
        per_planet = vargas.get(vname)
        if per_planet is None:
            continue
        info = per_planet.get(planet)
        if info is None:
            continue

        sign = int(info.get("sign", 0))

        # Debilitation
        if DEBILITATION_SIGNS.get(planet) == sign:
            total += 2.0
            continue

        # Own or exalted
        if sign in strengths.OWN_SIGNS.get(planet, []):
            total += 45.0
            continue
        if sign == strengths.EXALTATION_SIGNS.get(planet, -1):
            total += 45.0
            continue

        # Relationship to sign lord via D1 compound Maitri
        lord = strengths.SIGN_LORDS[sign]
        rel = compound_maitri_d1.get(planet, {}).get(lord, COMPOUND_SAMA)

        if rel == COMPOUND_ADHIMITRA:
            total += 40.0
        elif rel == COMPOUND_MITRA:
            total += 30.0
        elif rel == COMPOUND_SAMA:
            total += 20.0
        elif rel == COMPOUND_SATRU:
            total += 15.0
        elif rel == COMPOUND_ADHISATRU:
            total += 10.0
        else:
            total += 20.0  # default neutral

    return total


OJAYUGMA_MALE_PLANETS = {"Sun", "Mars", "Jupiter", "Mercury", "Saturn"}
OJAYUGMA_FEMALE_PLANETS = {"Moon", "Venus"}


def _is_odd_sign(sign_index: int) -> bool:
    """
    Aries (0), Gemini (2), ..., Aquarius (10) treated as odd signs.
    """
    return sign_index % 2 == 0


def calculate_ojayugma_bala(
    planet: str,
    vargas: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> float:
    """
    Ojayugma Bala (odd/even sign strength).

    Logic:
        - Consider D1 (Rasi) and D9 (Navamsa).
        - Male planets (Sun, Mars, Jupiter, Mercury, Saturn) gain 15 Virupas
          when in an odd sign.
        - Female planets (Moon, Venus) gain 15 Virupas when in an even sign.
    """
    if planet not in NAISARGIKA_BALA:
        return 0.0

    bala = 0.0
    d1 = vargas.get("D1", {})
    d9 = vargas.get("D9", {})

    def sign_of(v: Mapping[str, Mapping[str, float]], p: str) -> Optional[int]:
        info = v.get(p)
        if info is None:
            return None
        try:
            return int(info.get("sign", 0))
        except Exception:
            return None

    sign_d1 = sign_of(d1, planet)
    sign_d9 = sign_of(d9, planet)

    def _contributes(sign: Optional[int]) -> bool:
        if sign is None:
            return False
        if planet in OJAYUGMA_MALE_PLANETS:
            return _is_odd_sign(sign)
        if planet in OJAYUGMA_FEMALE_PLANETS:
            return not _is_odd_sign(sign)
        return False

    if _contributes(sign_d1):
        bala += 15.0
    if _contributes(sign_d9):
        bala += 15.0

    return bala


# ---------------------------------------------------------------------------
# House utilities and Dig Bala
# ---------------------------------------------------------------------------


def _sign_from_lon(lon: float) -> int:
    lon_n = _normalize_lon(lon)
    return int(lon_n // 30.0)


def _house_from_asc(planet_lon: float, asc_lon: float) -> int:
    """
    Compute house number (1..12) from ascendant and planet longitudes.
    Uses simple sign-based houses.
    """
    p_sign = _sign_from_lon(planet_lon)
    asc_sign = _sign_from_lon(asc_lon)
    return (p_sign - asc_sign) % 12 + 1


ZERO_STRENGTH_HOUSE: Dict[str, int] = {
    "Sun": 4,
    "Mars": 4,
    "Moon": 10,
    "Venus": 10,
    "Jupiter": 7,
    "Mercury": 7,
    "Saturn": 1,
}


def calculate_dig_bala(planet: str, house_from_asc: int) -> float:
    """
    Dig Bala (Directional strength) in Virupas.

    Simplified formula:
        - Zero-strength house H0 depends on planet.
        - Distance in houses dh = |house_from_asc - H0| around the wheel, minimized.
        - Convert to degrees: arc = dh * 30, ensure arc <= 180.
        - Dig Bala = arc / 3 (max 60 at opposite house).
    """
    if planet not in ZERO_STRENGTH_HOUSE:
        return 0.0

    h0 = ZERO_STRENGTH_HOUSE[planet]
    dh = (house_from_asc - h0) % 12
    if dh > 6:
        dh = 12 - dh
    arc = dh * 30.0
    if arc > 180.0:
        arc = 180.0
    bala = arc / 3.0
    if bala < 0.0:
        return 0.0
    if bala > 60.0:
        return 60.0
    return bala


def _calculate_kendra_bala_from_house(house_from_asc: Optional[int]) -> float:
    """
    Kendra Bala component based on the planet's house from ascendant in D1.

    Houses:
        - Kendra (1, 4, 7, 10):   60 Virupas
        - Panapara (2, 5, 8, 11): 30 Virupas
        - Apoklima (3, 6, 9, 12): 15 Virupas
    """
    if house_from_asc is None:
        return 0.0
    if house_from_asc in (1, 4, 7, 10):
        return 60.0
    if house_from_asc in (2, 5, 8, 11):
        return 30.0
    if house_from_asc in (3, 6, 9, 12):
        return 15.0
    return 0.0


# ---------------------------------------------------------------------------
# Kaala, Chesta, Drik – simplified placeholders
# ---------------------------------------------------------------------------


def calculate_naisargika_bala(planet: str) -> float:
    """
    Static natural strength.

    For nodes (Rahu, Ketu) returns 0.0 by convention in this engine.
    """
    return NAISARGIKA_BALA.get(planet, 0.0)


def _hours_from_datetime(dt: Optional["datetime"]) -> Optional[float]:  # type: ignore[name-defined]
    if dt is None:
        return None
    return dt.hour + dt.minute / 60.0 + dt.second / 3600.0


def _get_vara_index(jd: float) -> int:
    """
    Vara index 0..6 using the same rule as Panchanga:
    int(ceil(jd + 1)) % 7, where 0 = Sunday.
    """
    return int(math.ceil(jd + 1.0)) % 7


VARA_LORDS: Dict[int, str] = {
    0: "Sun",
    1: "Moon",
    2: "Mars",
    3: "Mercury",
    4: "Jupiter",
    5: "Venus",
    6: "Saturn",
}

DAY_STRONG_PLANETS = {"Sun", "Jupiter", "Venus"}
NIGHT_STRONG_PLANETS = {"Moon", "Mars", "Saturn"}


def calculate_kaala_bala(planet: str, frame: SkyFrame) -> float:
    """
    Kaala Bala (time-based strength) � simplified but structured.

    Components (all mapped into a 0..60 Virupa band overall):
        - Natonnata (day/night) based on time-of-day (UTC or local if available).
        - Paksha Bala based on Moon phase.
        - Vara Bala based on weekday lord.

    The individual components are combined with heuristic weights and
    clipped to [0, 60] for stability. This gives a realistic, extensible
    structure while staying implementation-light for Phase 7.5.
    """
    if planet not in NAISARGIKA_BALA:
        return 0.0

    # --- Natonnata Bala (time of day) ---
    dt = frame.local_datetime or frame.utc_datetime
    natonnata = 0.0
    if dt is not None:
        hour = _hours_from_datetime(dt)
        if hour is not None:
            if planet == "Mercury":
                natonnata = 60.0
            elif planet in DAY_STRONG_PLANETS:
                # Max at 12:00, min at 00:00 / 24:00
                diff = abs(hour - 12.0)
                if diff > 12.0:
                    diff = 24.0 - diff
                natonnata = max(0.0, 60.0 * (1.0 - diff / 12.0))
            elif planet in NIGHT_STRONG_PLANETS:
                # Max at 00:00, min at 12:00
                diff = min(hour, 24.0 - hour)
                natonnata = max(0.0, 60.0 * (1.0 - diff / 12.0))

    # --- Paksha Bala (Moon phase) ---
    paksha_bala = 0.0
    sun_pos = frame.positions.get("Sun")
    moon_pos = frame.positions.get("Moon")
    if sun_pos is not None and moon_pos is not None:
        sun_lon = _normalize_lon(sun_pos.lon)
        moon_lon = _normalize_lon(moon_pos.lon)
        phase = (moon_lon - sun_lon) % 360.0

        # Distance from New Moon (0 or 360) mapped to 0..180
        if phase > 180.0:
            delta = 360.0 - phase
        else:
            delta = phase

        # 0 at New Moon, 60 at Full Moon
        benefic_score = 60.0 * (delta / 180.0)

        # Tithi index 0..29, Paksha split at 15
        tithi_index = int(phase // 12.0) % 30
        paksha = "Shukla" if tithi_index < 15 else "Krishna"

        is_benefic = planet in {"Jupiter", "Venus"} or (
            planet == "Moon" and paksha == "Shukla"
        )
        is_malefic = planet in {"Sun", "Mars", "Saturn"} or (
            planet == "Moon" and paksha == "Krishna"
        )

        if is_benefic:
            paksha_bala = benefic_score
        elif is_malefic:
            paksha_bala = 60.0 - benefic_score
        else:
            # Mercury / others: take mid-range
            paksha_bala = 30.0

    # --- Vara Bala (weekday lord) ---
    vara_bala = 0.0
    if frame.jd:
        vara_idx = _get_vara_index(frame.jd)
        vara_lord = VARA_LORDS.get(vara_idx)
        if vara_lord == planet:
            vara_bala = 45.0

    # Combine components into a 0..60 band
    combined = 0.4 * natonnata + 0.4 * paksha_bala + 0.2 * vara_bala
    if combined < 0.0:
        return 0.0
    if combined > 60.0:
        return 60.0
    return combined


AVG_SPEED: Dict[str, float] = {
    "Sun": 0.9856,
    "Moon": 13.1764,
    "Mars": 0.524,
    "Mercury": 1.607,
    "Jupiter": 0.0831,
    "Venus": 1.174,
    "Saturn": 0.0335,
}

STATIONARY_THRESHOLD = 0.05


def calculate_chesta_bala(planet: str, frame: SkyFrame) -> float:
    """
    Chesta Bala (motion-based strength), simplified.

    Logic (per-planet average orbital speed):
        - Retrograde (speed_lon < 0) -> 60 Virupas (max).
        - Stationary (|speed_lon| < 0.05) -> 15 Virupas.
        - Fast (speed_lon > avg_speed) -> 45 Virupas.
        - Slow (0 <= speed_lon <= avg_speed) -> 30 Virupas.

    Sun and Moon are treated as non-retrograde even if numerical noise
    yields negative speeds.
    """
    if planet not in AVG_SPEED:
        return 0.0

    pos = frame.positions.get(planet)
    if pos is None or pos.speed_lon is None:
        return 0.0

    speed = pos.speed_lon

    # Sun / Moon do not have true retrograde
    if planet in {"Sun", "Moon"} and speed < 0.0:
        speed = abs(speed)

    # Retrograde planets get maximum Chesta Bala
    if speed < 0.0:
        return 60.0

    abs_speed = abs(speed)
    if abs_speed < STATIONARY_THRESHOLD:
        return 15.0

    avg = AVG_SPEED[planet]
    if abs_speed > avg:
        return 45.0
    return 30.0


BENEFIC_PLANETS = {"Jupiter", "Venus", "Mercury", "Moon"}
MALEFIC_PLANETS = {"Sun", "Mars", "Saturn"}
ASPECT_ORB = 6.0


def calculate_drik_bala(planet: str, frame: SkyFrame) -> float:
    """
    Drik Bala (aspect-based strength), simplified.

    Uses the scalar aspect engine with a moderate orb and treats
    aspects from benefics as positive contributions and aspects from
    malefics as negative. The total is compressed into [0, 60].

    Formula (heuristic):
        - For each relevant aspect, base_strength = 60 * (1 - |delta| / orb).
        - Sum benefic contributions, subtract malefic ones.
        - Drik Bala = max(0, min(60, total / 4)).
    """
    if planet not in NAISARGIKA_BALA:
        return 0.0

    aspects = compute_aspects_for_frame(frame, orb=ASPECT_ORB)
    total = 0.0

    for _, pairs in aspects.items():
        for (p1, p2), delta in pairs.items():
            if planet not in (p1, p2):
                continue
            other = p2 if p1 == planet else p1

            if other not in BENEFIC_PLANETS and other not in MALEFIC_PLANETS:
                continue

            strength = max(0.0, 60.0 * (1.0 - abs(delta) / ASPECT_ORB))
            if other in BENEFIC_PLANETS:
                total += strength
            else:
                total -= strength

    bala = total / 4.0
    if bala < 0.0:
        return 0.0
    if bala > 60.0:
        return 60.0
    return bala


# ---------------------------------------------------------------------------
# Aggregate Sthana Bala
# ---------------------------------------------------------------------------


def calculate_sthana_bala(
    planet: str,
    lon: float,
    frame: SkyFrame,
    vargas: Optional[Mapping[str, Mapping[str, Mapping[str, float]]]] = None,
    compound_maitri: Optional[Mapping[str, Mapping[str, str]]] = None,
    house_from_asc: Optional[int] = None,
) -> float:
    """
    Full Sthana Bala for a planet, combining:
        - Uchcha Bala
        - Saptavargaja Bala (if vargas & compound_maitri provided)
        - Ojayugma Bala (if vargas provided)
        - Kendra Bala (from house_from_asc if available)
        - Drekkana Bala (from D1 decanate 0-10/10-20/20-30)
    """
    uchcha = calculate_uchcha_bala(planet, lon)

    saptavargaja = 0.0
    if vargas is not None and compound_maitri is not None:
        saptavargaja = _calculate_saptavargaja_bala(planet, vargas, compound_maitri)

    ojayugma = 0.0
    if vargas is not None:
        ojayugma = calculate_ojayugma_bala(planet, vargas)

    kendra = _calculate_kendra_bala_from_house(house_from_asc)

    # Drekkana Bala from D1 degree segments (0-10,10-20,20-30)
    deg_in_sign = lon % 30.0
    dec_idx = int(deg_in_sign // 10.0)  # 0,1,2
    drekkana = 0.0
    if planet in {"Sun", "Mars", "Jupiter"} and dec_idx == 0:
        drekkana = 15.0
    elif planet in {"Mercury", "Saturn"} and dec_idx == 1:
        drekkana = 15.0
    elif planet in {"Moon", "Venus"} and dec_idx == 2:
        drekkana = 15.0

    return uchcha + saptavargaja + ojayugma + kendra + drekkana


# ---------------------------------------------------------------------------
# Aggregate Shadbala computation
# ---------------------------------------------------------------------------


@dataclass
class ShadbalaComponents:
    sthana: float
    dig: float
    kaala: float
    chesta: float
    naisargika: float
    drik: float

    @property
    def total(self) -> float:
        return self.sthana + self.dig + self.kaala + self.chesta + self.naisargika + self.drik


def calculate_shadbala_for_frame(
    frame: SkyFrame,
    *,
    vargas: Optional[Mapping[str, Mapping[str, Mapping[str, float]]]] = None,
    compound_maitri: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> Dict[str, ShadbalaComponents]:
    """
    Compute Shadbala components for the classical 7 planets in a given SkyFrame.

    Notes:
        - Uses D1 data from the frame (longitudes + ascendant).
        - Sthana Bala combines Uchcha, Saptavargaja, Ojayugma, Kendra, Drekkana.
        - Dig Bala is computed from house_from_asc using sign-based houses.
        - Kaala, Chesta, Drik are simplified but structured.
        - Rahu/Ketu are ignored (not included in output).
    """
    results: Dict[str, ShadbalaComponents] = {}

    houses = frame.houses or {}
    asc_lon: Optional[float] = None
    if isinstance(houses, dict):
        asc_lon = houses.get("asc")

    for planet, pos in frame.positions.items():
        if planet not in NAISARGIKA_BALA:
            # Skip nodes in this Shadbala implementation
            continue

        lon = _normalize_lon(pos.lon)

        house_from_asc: Optional[int] = None
        dig = 0.0
        if asc_lon is not None:
            house_from_asc = _house_from_asc(lon, asc_lon)
            dig = calculate_dig_bala(planet, house_from_asc)

        # Sthana Bala (full)
        sthana = calculate_sthana_bala(
            planet,
            lon,
            frame,
            vargas=vargas,
            compound_maitri=compound_maitri,
            house_from_asc=house_from_asc,
        )

        # Other components
        kaala = calculate_kaala_bala(planet, frame)
        chesta = calculate_chesta_bala(planet, frame)
        nais = calculate_naisargika_bala(planet)
        drik = calculate_drik_bala(planet, frame)

        results[planet] = ShadbalaComponents(
            sthana=sthana,
            dig=dig,
            kaala=kaala,
            chesta=chesta,
            naisargika=nais,
            drik=drik,
        )

    return results


def summarize_shadbala(
    shadbala_map: Mapping[str, ShadbalaComponents],
) -> Dict[str, Dict[str, float]]:
    """
    Produce a Shadbala summary per planet, including:
        - total_virupas: sum of all six balas.
        - rupas: total virupas / 60.
        - minimum_rupas: classical minimum requirement.
        - strength_ratio: rupas / minimum_rupas (PyJHora-style).
        - ishta_rupas: max(0, rupas - minimum_rupas).
        - kashta_rupas: max(0, minimum_rupas - rupas).

    This mirrors the final aggregation logic in PyJHora's shad_bala,
    but returns a user-friendly summary with ratios and simple
    Ishta/Kashta scores.
    """
    summary: Dict[str, Dict[str, float]] = {}

    for planet, comp in shadbala_map.items():
        total = float(comp.total)
        rupas = total / 60.0
        min_req = MIN_SHADBALA_RUPAS.get(planet, 0.0)
        ratio = (rupas / min_req) if min_req > 0.0 else 0.0
        ishta = max(0.0, rupas - min_req)
        kashta = max(0.0, min_req - rupas)
        status = "Strong" if ratio >= 1.0 and min_req > 0.0 else "Weak"

        summary[planet] = {
            "total_virupas": round(total, 2),
            "rupas": round(rupas, 2),
            "minimum_req": float(min_req),
            "ratio": round(ratio, 2),
            "status": status,
            "ishta_score": round(ishta, 2),
            "kashta_score": round(kashta, 2),
        }

    return summary


def classify_shadbala(
    summary: Mapping[str, Mapping[str, float]],
) -> Dict[str, list[str]]:
    """
    Classify planets into strong/weak buckets based on Shadbala summary.

    Criteria (per planet):
        - Only planets with a positive minimum requirement are considered
          (Sun..Saturn).
        - \"Strong\" if status == \"Strong\" (ratio >= 1.0).
        - \"Weak\" if status == \"Weak\" (ratio < 1.0).

    Returns:
        {
            "strong_planets": [...],
            "weak_planets": [...],
        }
    """
    strong: list[str] = []
    weak: list[str] = []

    for planet, data in summary.items():
        min_req = float(data.get("minimum_req", 0.0))
        if min_req <= 0.0:
            # Skip nodes or anything without a meaningful minimum
            continue
        status = str(data.get("status", ""))
        if status == "Strong":
            strong.append(planet)
        elif status == "Weak":
            weak.append(planet)

    return {
        "strong_planets": strong,
        "weak_planets": weak,
    }
