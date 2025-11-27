import numpy as np
from typing import List, Tuple
from raavi_ephemeris_vector import EphemerisBatch

def find_zodiac_ingresses(batch: EphemerisBatch, body_name: str) -> List[Tuple[float, int, int]]:
    """
    Scans an EphemerisBatch to find when a planet changes Zodiac signs using vectorized logic.
    
    Args:
        batch: The pre-calculated vector batch.
        body_name: The name of the body to scan (e.g., "Moon").
        
    Returns:
        A list of tuples: (JulianDate, From_Sign_Index, To_Sign_Index)
        The JD returned is the timestamp of the *first* data point in the new sign.
    """
    try:
        # batch.bodies is a list of strings
        body_idx = batch.bodies.index(body_name)
    except ValueError:
        return []

    # Extract longitudes: Shape (N_time,)
    # raw_results is (N_time, N_body, 6), index 0 is Longitude
    longitudes = batch.raw_results[:, body_idx, 0]
    
    # Calculate Sign Indices (0..11)
    # mod 360 handles bounds, floor division by 30 gives sign index
    signs = np.floor(np.mod(longitudes, 360.0) / 30.0).astype(int)
    
    # Find where the sign changes
    # np.diff returns differences between adjacent elements. != 0 means a change.
    # prepend=signs[0] ensures the output shape matches the input shape, 
    # and the first element is never a 'change' relative to itself.
    changes = np.diff(signs, prepend=signs[0]) != 0
    
    # Get indices where changes occurred (True values)
    change_indices = np.where(changes)[0]
    
    events = []
    for idx in change_indices:
        jd = float(batch.jds[idx])
        to_sign = int(signs[idx])
        from_sign = int(signs[idx-1]) # safe because prepend handled index 0 logic
        
        events.append((jd, from_sign, to_sign))
        
    return events

