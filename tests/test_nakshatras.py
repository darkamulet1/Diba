import pytest
import numpy as np
from logic.nakshatras import get_nakshatra_scalar, get_nakshatra_batch, NAKSHATRA_NAMES

def test_nakshatra_scalar_boundaries():
    # 0 degrees -> Start of Ashwini (Index 0), Pada 1
    idx, name, pada = get_nakshatra_scalar(0.0)
    assert idx == 0
    assert name == "Ashwini"
    assert pada == 1
    
    # 13.333... degrees -> Start of Bharani (Index 1)
    # 13 deg 20 min = 13 + 1/3 = 13.3333...
    boundary = 360.0 / 27.0
    
    # Test just before boundary (Ashwini Pada 4)
    idx, name, pada = get_nakshatra_scalar(boundary - 0.0001)
    assert idx == 0
    assert pada == 4
    
    # Test just after boundary (Bharani Pada 1)
    idx, name, pada = get_nakshatra_scalar(boundary + 0.0001)
    assert idx == 1
    assert name == "Bharani"
    assert pada == 1

def test_nakshatra_batch_parity():
    # Create an array of test longitudes
    lons = np.array([0.0, 10.0, 13.5, 120.0, 359.9])
    
    # Vector calculation
    vec_idxs, vec_padas = get_nakshatra_batch(lons)
    
    # Scalar verification loop
    for i, lon in enumerate(lons):
        scal_idx, _, scal_pada = get_nakshatra_scalar(lon)
        assert vec_idxs[i] == scal_idx
        assert vec_padas[i] == scal_pada

def test_specific_nakshatra_points():
    # Magha starts at 120 degrees (Leo 0)
    idx, name, _ = get_nakshatra_scalar(120.0)
    assert name == "Magha"
    
    # Revati ends at 360
    idx, name, _ = get_nakshatra_scalar(359.0)
    assert name == "Revati"

