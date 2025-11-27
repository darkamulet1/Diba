# Raavi Ephemeris
## Usage
```python
from raavi_ephemeris import get_default_provider
# 1. Classic (Single chart, Houses)
prov = get_default_provider(calculate_houses=True)
# 2. Vectorized (Time series, ML)
vec_prov = get_default_provider(use_vector_engine=True)
```

## Installation & Development

This project is packaged using standard PEP 621 metadata.
### Setup
```bash
# Install in editable mode with development dependencies
pip install -e .[dev]
```
Running CI Locally
```Bash
pytest tests/
```
