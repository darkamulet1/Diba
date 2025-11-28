# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime

import pytz

from chart_calculator import ChartCalculator


def main():
    # --- Mehran birth data ---
    tz = pytz.timezone("Asia/Tehran")
    local_dt = tz.localize(datetime(1997, 6, 7, 20, 28, 36))
    utc_dt = local_dt.astimezone(pytz.utc)

    lat, lon = 35.6892, 51.3890

    print(
        f"Calculating SIDEREAL (Lahiri) chart for Mehran at local {local_dt} (UTC {utc_dt})"
    )

    calc = ChartCalculator(sidereal=True, ayanamsa="LAHIRI")
    json_output = calc.calculate_json(utc_dt, lat, lon, name="Mehran (Sidereal)")

    os.makedirs("output", exist_ok=True)
    out_path = "output/mehran_chart_sidereal.json"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json_output)

    data = json.loads(json_output)
    moon_data = data.get("bodies", {}).get("Moon", {})
    moon_sign = moon_data.get("zodiac_sign")
    moon_nak = moon_data.get("nakshatra", {}).get("name")
    first_dasha = data.get("dashas", [{}])[0].get("lord")

    print(f"\n? Sidereal chart JSON saved to {out_path}\n")
    print(json_output)
    print(
        f"\n[Sanity] Moon sign index: {moon_sign}, Nakshatra: {moon_nak}, First dasha lord: {first_dasha}"
    )


if __name__ == "__main__":
    main()