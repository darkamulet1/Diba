from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple

from logic.nakshatras import get_nakshatra_scalar, NAKSHATRA_EXTENT

# Vimshottari Constants
# Sequence of lords starting from Ashwini (Ketu)
DASHA_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"
]

# Duration of each Mahadasha in years
DASHA_YEARS = {
    "Ketu": 7,
    "Venus": 20,
    "Sun": 6,
    "Moon": 10,
    "Mars": 7,
    "Rahu": 18,
    "Jupiter": 16,
    "Saturn": 19,
    "Mercury": 17,
}


@dataclass
class DashaPeriod:
    lord: str
    start_date: datetime
    end_date: datetime
    duration_years: float


def calculate_vimshottari(moon_longitude: float, birth_date: datetime, total_years: int = 120) -> List[DashaPeriod]:
    """
    Calculates the Vimshottari Dasha sequence starting from the birth date.

    Args:
        moon_longitude: The exact longitude of the Moon at birth.
        birth_date: The localized datetime of birth.
        total_years: How many years of dashas to calculate (default 120).

    Returns:
        List of DashaPeriod objects covering the requested timeframe.
    """
    # 1. Get Nakshatra info
    # We need the exact position to calculate how much of the nakshatra is traversed.
    nak_idx, _, _ = get_nakshatra_scalar(moon_longitude)

    # 2. Determine the Ruling Planet (Lord)
    # The cycle of 9 lords repeats. Ashwini(0) -> Ketu(0), Bharani(1) -> Venus(1)...
    lord_idx = nak_idx % 9
    current_lord = DASHA_LORDS[lord_idx]

    # 3. Calculate Balance of Dasha (Sesh Dasha)
    # How far into the nakshatra is the Moon?
    # Start of current nakshatra:
    nak_start_lon = nak_idx * NAKSHATRA_EXTENT
    # Degrees traversed inside the nakshatra:
    traversed = moon_longitude - nak_start_lon
    # Fraction remaining (to be lived):
    fraction_remaining = 1.0 - (traversed / NAKSHATRA_EXTENT)

    # Total years for this lord:
    full_duration = DASHA_YEARS[current_lord]
    balance_years = full_duration * fraction_remaining

    # 4. Generate the Sequence
    dashas: List[DashaPeriod] = []
    current_date = birth_date

    # First Dasha (Balance)
    # Approximate leap years by using 365.25 days per year
    days_remaining = balance_years * 365.25
    end_date = current_date + timedelta(days=days_remaining)
    dashas.append(DashaPeriod(
        lord=current_lord,
        start_date=current_date,
        end_date=end_date,
        duration_years=balance_years
    ))
    current_date = end_date

    # Subsequent Dashas
    years_generated = balance_years
    curr_lord_seq_idx = lord_idx

    while years_generated < total_years:
        # Move to next lord in sequence
        curr_lord_seq_idx = (curr_lord_seq_idx + 1) % 9
        next_lord = DASHA_LORDS[curr_lord_seq_idx]
        duration = DASHA_YEARS[next_lord]
        end_date = current_date + timedelta(days=duration * 365.25)

        dashas.append(DashaPeriod(
            lord=next_lord,
            start_date=current_date,
            end_date=end_date,
            duration_years=float(duration)
        ))

        current_date = end_date
        years_generated += duration

    return dashas

