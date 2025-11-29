# Raavi Ephemeris

## ✨ ویژگی‌های کلیدی (نسخه ۱.۰)

* **Panchanga Engine (Phase 4):**
    * تقویم کامل ودیک: Tithi, Nakshatra, Yoga, Karana, Vara, Masa, Paksha.
    * **Event-Driven:** تشخیص دقیق تغییرات فاز در طول روز (Kshaya/Adhika Tithis).
    * زمان‌های خاص: Rahu Kalam, Yamaganda, Gulika, Abhijit Muhurta.
* **Chart Calculator & Vargas:**
    * محاسبه دقیق موقعیت سیارات (Sidereal).
    * تولید تمام چارت‌های تقسیمی استاندارد (**D1 تا D60**) بر اساس پاراشارا.
* **Planetary Strength (Bala):**
    * **Shadbala:** محاسبه کامل ۶ قدرت (Sthana, Dig, Kaala, Chesta, Naisargika, Drik).
    * **Strength Analysis:** گزارش خودکار سیارات قوی/ضعیف، Ishta Phala و Kashta Phala.
    * **Vimsopaka Bala:** محاسبه امتیاز قدرت در ۱۰ ورگا (Shadvarga, Dasavarga و ...).
    * **Maitri:** روابط دقیق سیاره‌ای (طبیعی، موقتی، مرکب).

## Usage

```python
from raavi_ephemeris import get_default_provider

# 1. Classic (Single chart, Houses)
provider = get_default_provider(calculate_houses=True, sidereal=True, ayanamsa="LAHIRI")

# 2. Vectorized (Time series, ML)
vec_provider = get_default_provider(use_vector_engine=True, sidereal=True, ayanamsa="LAHIRI")
```

## Installation & Development

This project is packaged using standard PEP 621 metadata.

### Setup

```bash
# Install in editable mode with development dependencies
pip install -e .[dev]
```

### Running CI Locally

```bash
pytest tests/
```
