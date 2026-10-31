#!/usr/bin/env python3
"""Evaluate ReliabilityLab alert conditions against recorded evidence.

This is the no-Prometheus fallback for the promtool unit tests
(prometheus/alerts_test.yml). It works on either:
  --metrics-file  a captured /metrics exposition (checks dependency_up)
  --phases-file   the exercise JSON from scripts/exercise.py
                  (checks fault-phase error rate > 25% and dependency)

Exit code 0 if the expected alerts would fire on fault evidence and
would NOT fire on baseline evidence.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ERROR_RATE_THRESHOLD = 0.25  # mirrors HighErrorRate in prometheus/alerts.yml


def dependency_up(metrics_text: str):
    m = re.search(r"^dependency_up\s+([01](?:\.0)?)$", metrics_text, re.M)
    return float(m.group(1)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics-file")
    ap.add_argument("--phases-file")
    args = ap.parse_args()
    failures = []

    if args.metrics_file:
        text = Path(args.metrics_file).read_text()
        value = dependency_up(text)
        print(f"dependency_up in {args.metrics_file}: {value}")
        if value is None:
            failures.append("dependency_up series missing from metrics file")

    if args.phases_file:
        data = json.loads(Path(args.phases_file).read_text())
        base = data["phases"]["baseline"]
        fault = data["phases"]["fault"]
        base_err = base["errors"] / max(base["requests"], 1)
        fault_err = fault["errors"] / max(fault["requests"], 1)
        print(f"baseline error rate: {base_err:.2%} "
              f"({'would fire' if base_err > ERROR_RATE_THRESHOLD else 'ok, no fire'})")
        print(f"fault    error rate: {fault_err:.2%} "
              f"({'would fire HighErrorRate' if fault_err > ERROR_RATE_THRESHOLD else 'WOULD NOT FIRE'})")
        if fault_err <= ERROR_RATE_THRESHOLD:
            failures.append("HighErrorRate would not fire on fault evidence")
        if base_err > ERROR_RATE_THRESHOLD:
            failures.append("HighErrorRate would false-fire on baseline")
        dep = data["phases"]["fault"].get("dependency_up")
        print(f"fault dependency_up: {dep} "
              f"({'would fire DependencyDown' if dep == 0 else 'WOULD NOT FIRE'})")
        if dep != 0:
            failures.append("DependencyDown would not fire on fault evidence")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: alert conditions match the recorded evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
