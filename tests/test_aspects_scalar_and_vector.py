import pytz
import numpy as np
from datetime import datetime

from raavi_ephemeris import TimeLocation, get_default_provider
from logic.aspects import compute_aspects_for_frame, compute_aspects_for_batch, DEFAULT_ASPECTS


def test_scalar_aspects_basic():
    # Pick an arbitrary time
    tl = TimeLocation(dt_utc=datetime(2000, 1, 1, 12, 0, 0, tzinfo=pytz.utc))
    provider = get_default_provider(use_vector_engine=False)
    frame = provider.get_sky_frame(tl)

    aspects = compute_aspects_for_frame(frame, bodies=["Sun", "Moon"], aspects={"conjunction": 0.0}, orb=30.0)
    # With generous orb, there should be at least one relation
    assert isinstance(aspects, dict)
    assert "conjunction" in aspects
    # Just ensure code runs and returns dict-of-dicts
    assert isinstance(aspects["conjunction"], dict)


def test_vector_aspects_shape_and_symmetry():
    # Same time points as ephemeris benchmark used conceptually
    tz = pytz.utc
    times = [
        datetime(2000, 1, 1, 12, 0, 0, tzinfo=tz),
        datetime(2000, 1, 2, 12, 0, 0, tzinfo=tz),
        datetime(2000, 1, 3, 12, 0, 0, tzinfo=tz),
    ]

    # Build a batch from the vector provider
    provider_vec = get_default_provider(use_vector_engine=True)
    from raavi_ephemeris import datetime_to_julian  # re-use helper
    jds = np.array([datetime_to_julian(t) for t in times])
    batch = provider_vec._backend.calculate_batch(jds)

    masks = compute_aspects_for_batch(batch, bodies=["Sun", "Moon"], aspects={"conjunction": 0.0}, orb=30.0)
    assert "conjunction" in masks
    m = masks["conjunction"]
    # Shape: (T, B, B) = (3, 2, 2)
    assert m.shape == (3, 2, 2)
    # Symmetry: aspect(i, j) == aspect(j, i)
    assert np.all(m == np.transpose(m, (0, 2, 1)))
    # Diagonal must be False by construction
    for t in range(m.shape[0]):
        assert np.all(np.diag(m[t]) == 0)

