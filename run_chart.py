import pytz
from datetime import datetime
from chart_calculator import ChartCalculator


def main():
    # Example birth data: Tehran, 1 Jan 2000, 12:00 local time
    year, month, day = 2000, 1, 1
    hour, minute = 12, 0
    lat, lon = 35.6892, 51.3890

    tz = pytz.timezone("Asia/Tehran")
    local_dt = tz.localize(datetime(year, month, day, hour, minute))
    utc_dt = local_dt.astimezone(pytz.utc)

    print(f"--- Calculating Chart for {local_dt} (Tehran, converted to {utc_dt} UTC) ---")

    calc = ChartCalculator()
    json_output = calc.calculate_json(utc_dt, lat, lon, name="Test User")

    print(json_output)

    if '"Moon"' in json_output and '"dashas"' in json_output:
        print("\n? JSON generated successfully containing planets and dashas.")
    else:
        print("\n? JSON generation might be incomplete.")


if __name__ == "__main__":
    main()

