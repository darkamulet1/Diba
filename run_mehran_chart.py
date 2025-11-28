# -*- coding: utf-8 -*-
import pytz
from datetime import datetime
from chart_calculator import ChartCalculator
import os


def main():
    # --- Mehran birth data ---
    # 7 June 1997 – 20:28:36 Asia/Tehran (UTC+4:30)
    tz = pytz.timezone("Asia/Tehran")
    local_dt = tz.localize(datetime(1997, 6, 7, 20, 28, 36))
    utc_dt = local_dt.astimezone(pytz.utc)

    # Tehran coordinates
    lat, lon = 35.6892, 51.3890

    print(f"Calculating chart for Mehran at local {local_dt} (UTC {utc_dt})")

    calc = ChartCalculator()
    json_output = calc.calculate_json(utc_dt, lat, lon, name="Mehran")

    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)

    out_path = "output/mehran_chart.json"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json_output)

    print(f"\n? Chart JSON saved to {out_path}\n")
    print(json_output)


if __name__ == "__main__":
    main()

