import time
import numpy as np
from datetime import datetime, timedelta
import pytz
from raavi_ephemeris import get_default_provider, datetime_to_julian

def run_benchmark():
    N = 1000
    jds = np.array([datetime_to_julian(datetime(2000,1,1) + timedelta(days=i)) for i in range(N)])
    
    # Scalar
    p_c = get_default_provider(use_vector_engine=False)
    t0 = time.perf_counter()
    for jd in jds:
        # Dummy mock call
        _ = p_c.get_sky_frame(type('TL', (object,), {'dt_utc': datetime.fromtimestamp((jd-2451544.5)*86400)})())
    t_scalar = time.perf_counter() - t0
    
    # Vector
    p_v = get_default_provider(use_vector_engine=True)
    t0 = time.perf_counter()
    _ = p_v._backend.calculate_batch(jds)
    t_vector = time.perf_counter() - t0
    
    print(f"Scalar: {t_scalar:.4f}s | Vector: {t_vector:.4f}s | Speedup: {t_scalar/t_vector:.1f}x")

if __name__ == "__main__":
    run_benchmark()

