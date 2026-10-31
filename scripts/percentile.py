"""Shared percentile helper (no dependencies)."""
import math


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def summarize(latencies_ms):
    return {
        "count": len(latencies_ms),
        "p50_ms": round(percentile(latencies_ms, 50), 2),
        "p95_ms": round(percentile(latencies_ms, 95), 2),
        "max_ms": round(max(latencies_ms), 2) if latencies_ms else 0.0,
    }
