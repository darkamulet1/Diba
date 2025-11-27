import pytest
from datetime import datetime
import pytz

from logic.dashas import calculate_vimshottari, DashaPeriod


def test_vimshottari_balance_logic():
    # Example Logic Check:
    # Moon at exactly 0 degrees (Start of Ashwini).
    # Ashwini is ruled by Ketu (7 years).
    # Since Moon is at 0%, 100% of Ketu dasha remains.
    birth_date = datetime(2000, 1, 1, tzinfo=pytz.utc)
    dashas = calculate_vimshottari(0.00, birth_date, total_years=20)
    first = dashas[0]
    assert first.lord == "Ketu"
    # Allow small float error margin for year calculation
    assert abs(first.duration_years - 7.0) < 0.01
    second = dashas[1]
    assert second.lord == "Venus"  # Venus follows Ketu
    assert abs(second.duration_years - 20.0) < 0.01


def test_vimshottari_midpoint():
    # Moon exactly in the middle of Ashwini (13.3333 / 2 = 6.6666 degrees)
    # Should have exactly half of Ketu's period left (3.5 years).
    birth_date = datetime(2000, 1, 1, tzinfo=pytz.utc)
    moon_lon = 6.66666666
    dashas = calculate_vimshottari(moon_lon, birth_date, total_years=10)
    first = dashas[0]
    assert first.lord == "Ketu"
    assert abs(first.duration_years - 3.5) < 0.05

