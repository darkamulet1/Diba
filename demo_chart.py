import sys
import os
from datetime import datetime

import pytz

# Ensure Raavi package is importable when running from repo root
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "Raavi"))

from chart_calculator import ChartCalculator  # type: ignore


def print_chart_report() -> None:
    # 1. Setup (Tehran example)
    tz = pytz.timezone("Asia/Tehran")
    now_local = datetime.now(tz)
    now_utc = now_local.astimezone(pytz.utc)

    print("\n✨ RAAVI CHART REPORT ✨")
    print(f"📅 Date: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("📍 Location: Tehran (35.6892 N, 51.3890 E)")
    print("-" * 60)

    # 2. Calculate
    calc = ChartCalculator(sidereal=True, ayanamsa="LAHIRI")
    print("⏳ Calculating Chart, Vargas, Maitri & Shadbala...", end="", flush=True)
    data = calc.calculate_dict(now_utc, 35.6892, 51.3890, name="Demo")
    print(" Done!\n")

    # 3. Basic Bodies (D1)
    print("🪐 PLANETARY POSITIONS (D1 Rasi)")
    print(f"{'Body':<10} {'Longitude':<10} {'Rasi':<15} {'Nakshatra'}")
    print("-" * 60)

    SIGNS = [
        "Aries",
        "Taurus",
        "Gemini",
        "Cancer",
        "Leo",
        "Virgo",
        "Libra",
        "Scorpio",
        "Sagittarius",
        "Capricorn",
        "Aquarius",
        "Pisces",
    ]

    for body, info in data["bodies"].items():
        sign_name = SIGNS[info["zodiac_sign"]]
        deg = info["degree_in_sign"]
        nak = info["nakshatra"]["name"]
        print(f"{body:<10} {deg:05.2f}°     {sign_name:<15} {nak}")
    print("-" * 60)

    # 4. Shadbala Summary
    print("\n💪 SHADBALA STRENGTH (6-Fold Strength)")
    print(f"{'Planet':<10} {'Rupas':<8} {'Min':<6} {'Ratio':<8} {'Status':<10} {'Ishta/Kashta'}")
    print("-" * 60)

    summary = data.get("shadbala_summary", {})

    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        if planet not in summary:
            continue
        s = summary[planet]
        status_icon = "✅" if s["status"] == "Strong" else "⚠️"
        i_k = f"I:{s['ishta_score']:.1f} / K:{s['kashta_score']:.1f}"

        print(
            f"{planet:<10} {s['rupas']:<8.2f} "
            f"{s['minimum_req']:<6.1f} {s['ratio']:<8.2f} "
            f"{status_icon} {s['status']:<7} {i_k}"
        )

    print("-" * 60)

    # 5. Vimsopaka
    print("\n🌟 VIMSOPAKA BALA (Weighted Strength across Vargas)")
    print(f"{'Planet':<10} {'D1 Score':<10} {'Weighted Score (Shadvarga)'}")
    print("-" * 60)

    maitri = data.get("maitri", {})
    vim_d1 = maitri.get("vimsopaka_d1", {})
    vim_w = maitri.get("vimsopaka_weighted", {})

    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        d1 = vim_d1.get(planet, 0)
        w_score = vim_w.get(planet, {}).get("Shadvarga", 0.0)
        print(f"{planet:<10} {d1:<10} {w_score:.2f} / 20.00")

    print("\n✅ Report Generated Successfully.")


if __name__ == "__main__":
    print_chart_report()

