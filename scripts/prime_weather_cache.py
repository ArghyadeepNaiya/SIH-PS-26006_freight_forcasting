#!/usr/bin/env python3
"""Fetch and cache the weather forecast for every port.

Standing rule 4 of this project forbids a live external API call during a
demonstration. Run this with a network connection before you present, then set
FREIGHT_WEATHER_OFFLINE=1 and the dashboard will serve everything from the cache
with no network access at all.

    python3 scripts/prime_weather_cache.py
    FREIGHT_WEATHER_OFFLINE=1 ./run.sh
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml-service"))

from app.core import weather                      # noqa: E402


def main():
    if weather.offline():
        print("FREIGHT_WEATHER_OFFLINE is set, so nothing would be fetched.")
        print("Unset it, run this again, then set it back before the demonstration.")
        return 1

    print("Fetching the seven day forecast for every port and its approach anchorage.")
    print("")
    ok = 0
    for w in weather.for_all_ports(force=True):
        if "error" in w:
            print(f"   {w['port_code']}. FAILED. {w['error']}")
            continue
        adv, fresh = w["advisory"], w["freshness"]["quay"]
        print(f"   {w['port_name']} ({w['port_code']}). {adv['risk_band'].upper()}. "
              f"{adv['expected_weather_delay_days']} expected weather delay days. "
              f"Source {fresh['source']}.")
        if fresh["source"] == "live":
            ok += 1
    print("")
    print(f"{ok} ports fetched live and cached to data/cache/weather.")
    print("The cache is gitignored. Re-run this whenever the forecast goes stale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
