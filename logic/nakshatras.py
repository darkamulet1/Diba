import numpy as np
from typing import Tuple, List, Union, Dict

# Constants
NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

# Each Nakshatra is 13 degrees 20 minutes = 13.3333... degrees
NAKSHATRA_EXTENT = 360.0 / 27.0  # ~13.333333

def get_nakshatra_scalar(longitude: float) -> Tuple[int, str, int]:
    """
    Convert a single longitude to Nakshatra info.
    
    Args:
        longitude: 0..360 degrees.
        
    Returns:
        (index_0_26, name, pada_1_4)
    """
    # Normalize
    lon = longitude % 360.0
    
    # Calculate continuous index
    raw_idx = lon / NAKSHATRA_EXTENT
    idx = int(raw_idx)
    
    # Calculate Pada (Quarter): Each Nakshatra has 4 Padas
    # Fraction of the nakshatra * 4 -> 0..3.99 -> floor -> +1 -> 1..4
    fraction = raw_idx - idx
    pada = int(fraction * 4) + 1
    
    return idx, NAKSHATRA_NAMES[idx], pada

def get_nakshatra_batch(longitudes: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Vectorized mapping of longitudes to Nakshatra indices and Padas.
    
    Args:
        longitudes: NumPy array of longitudes.
        
    Returns:
        (indices, padas) as integer arrays.
    """
    lons = np.mod(longitudes, 360.0)
    raw_idxs = lons / NAKSHATRA_EXTENT
    
    indices = np.floor(raw_idxs).astype(int)
    
    # Pad calculation
    fractions = raw_idxs - indices
    padas = (np.floor(fractions * 4) + 1).astype(int)
    
    return indices, padas

