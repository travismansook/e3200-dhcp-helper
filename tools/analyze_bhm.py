#!/usr/bin/env python3
"""Summarize retained E3200 BHM evidence. Never sends traffic or executes log text."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys
from typing import Iterable

STAMP = re.compile(r"^(\d{4}) ([A-Z][a-z]{2})\s+(\d{1,2}) (\d{2}):(\d{2}):(\d{2})\b")
MONTHS = {name: i for i, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
LOSS = re.compile(r"\bbh packet loss rate\s*=\s*(\d+(?:\.\d+)?)\b")
DISCONNECT = re.compile(r"\bbh_ping_disconnect:\s*(\d+)\b")


def timestamp(line: str) -> datetime | None:
    match = STAMP.match(line)
    if not match or match[2] not in MONTHS:
        return None
    try:
        return datetime(int(match[1]), MONTHS[match[2]], int(match[3]),
                        int(match[4]), int(match[5]), int(match[6]))
    except ValueError:
        return None


def analyze_lines(lines: Iterable[str], day: date | None = None) -> dict:
    """Count explicit records; warning labels and function names are not outages."""
    first = last = previous = previous_probe = None
    records = malformed = probes = nonzero_probes = disconnect_results = 0
    nonzero_disconnects = led_disconnects = wired_establishments = 0
    max_probe_gap = None
    backwards = []
    distribution: Counter[str] = Counter()
    events = []
    for line_number, line in enumerate(lines, 1):
        stamp = timestamp(line)
        if stamp is None:
            malformed += 1
            continue
        if previous is not None and stamp < previous:
            backwards.append({"line": line_number, "from": previous.isoformat(" "),
                              "to": stamp.isoformat(" "),
                              "seconds": (previous - stamp).total_seconds()})
        previous = stamp
        if day is not None and stamp.date() != day:
            continue
        records += 1
        if first is None:
            first = stamp
        last = stamp
        loss = LOSS.search(line)
        if loss:
            value = float(loss[1])
            if not 0 <= value <= 100:
                malformed += 1
                continue
            probes += 1
            nonzero_probes += value > 0
            distribution[f"{value:g}"] += 1
            if previous_probe is not None:
                gap = (stamp - previous_probe).total_seconds()
                if gap >= 0:
                    max_probe_gap = gap if max_probe_gap is None else max(max_probe_gap, gap)
            previous_probe = stamp
        indicator = DISCONNECT.search(line)
        if indicator:
            disconnect_results += 1
            nonzero_disconnects += int(indicator[1]) != 0
        if re.search(r"\bBHM_LED_DISCONNECTED\b", line):
            led_disconnects += 1
            events.append({"line": line_number, "time": stamp.isoformat(" "),
                           "event": "backhaul_disconnected_led"})
        if re.search(r"\bBHM_LED_ESTABLISH_WIRE_BACKHAUL\b", line):
            wired_establishments += 1
            events.append({"line": line_number, "time": stamp.isoformat(" "),
                           "event": "wired_backhaul_established_led"})
    return {
        "requested_date": day.isoformat() if day else None,
        "clock": "Device log time; timezone is not inferred.",
        "matching_records": records,
        "first_record": first.isoformat(" ") if first else None,
        "last_record": last.isoformat(" ") if last else None,
        "gateway_loss_samples": probes,
        "nonzero_loss_samples": nonzero_probes,
        "sample_distribution_percent": dict(distribution),
        "maximum_nonnegative_gap_between_samples_seconds": max_probe_gap,
        "disconnect_indicator_samples": disconnect_results,
        "nonzero_disconnect_indicators": nonzero_disconnects,
        "explicit_backhaul_disconnect_led_events": led_disconnects,
        "explicit_wired_establishment_led_events": wired_establishments,
        "events": events,
        "backward_clock_steps_in_whole_file": backwards,
        "unparsed_or_invalid_records_in_whole_file": malformed,
        "limits": [
            "Counts reflect retained records only, not continuous monitoring.",
            "Gateway probes do not measure individual Wi-Fi clients or the WAN.",
            "Zero samples provide no evidence of zero packet loss.",
            "Clock resets may combine separate sessions under the same date; inspect clock steps.",
            "Generic bh_disconnected function text is not counted as an outage.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--date", type=date.fromisoformat, help="Filter by device date YYYY-MM-DD")
    args = parser.parse_args()
    try:
        with args.log.open(encoding="utf-8", errors="replace") as stream:
            result = analyze_lines(stream, args.date)
    except OSError as error:
        print(f"Cannot read log: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
