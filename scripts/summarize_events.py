"""Summarize one normalized request record per physical attempt, offline.

Schema and semantics: references/verification.md. Never infers missing usage.
Not a parser for arbitrary provider logs. Reads only the specified JSONL file.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    return values[max(0, math.ceil(q*len(values))-1)]


def summarize(records):
    seen, completed = set(), set()
    statuses, unknown, sums = Counter(), Counter(), Counter()
    latency, starts, ends = [], [], []
    for r in records:
        identity = (r["run_id"], r["attempt_id"])
        if identity in seen:
            raise ValueError("duplicate physical attempt record")
        seen.add(identity)
        start, end = r["start_s"], r["end_s"]
        if any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, end)) or end < start:
            raise ValueError("invalid finite start/end timestamps")
        status = r["status"]
        if status not in {"validated", "format_error", "rate_limited", "transport_error", "unknown", "cache_hit", "global_error", "agent_failed"}:
            raise ValueError("unknown normalized status")
        starts.append(start); ends.append(end); statuses[status] += 1
        if status == "validated":
            completed.add(r["decision_key"])
        if status != "cache_hit":
            latency.append(end-start)
        for key in ("input_tokens", "output_tokens"):
            value = r.get(key)
            if value is None:
                if status != "cache_hit":
                    unknown[key] += 1
            elif type(value) is not int or value < 0:
                raise ValueError("usage must be a nonnegative integer or null")
            elif status != "cache_hit":
                sums[key] += value
    elapsed = max(ends)-min(starts) if starts else 0
    return {
        "records": len(seen), "statuses": dict(statuses),
        "new_validated_decisions": len(completed),
        "observed_wall_seconds": elapsed,
        "new_validated_decisions_per_minute": 60*len(completed)/elapsed if elapsed else None,
        "request_latency_p50_seconds": percentile(latency, .5),
        "request_latency_p95_seconds": percentile(latency, .95),
        "known_input_tokens": sums["input_tokens"],
        "known_output_tokens": sums["output_tokens"],
        "unknown_input_usage_attempts": unknown["input_tokens"],
        "unknown_output_usage_attempts": unknown["output_tokens"],
        "unknown_outcome_records": statuses["unknown"],
        "note": "Known usage sums only; null is not zero. Cache replay is not new API throughput. No billing inference."
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.events.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    print(json.dumps(summarize(records), ensure_ascii=False, indent=2))
