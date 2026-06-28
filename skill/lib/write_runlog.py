#!/usr/bin/env python3
"""write_runlog.py — validate a run-log against the schema and archive it.

Writes profiles/<profile>/history/runs/<run_date>/run-log.json.

run-log schema (required keys):
  manifest_version : str
  run_date         : str  (YYYY-MM-DD)
  profile          : str
  queries_run      : [str, ...]
  queries_null     : [str, ...]
  fetch_failures   : [str, ...]
  sources_hit      : [{"name": str, "count": int}, ...]
  counts           : {"new": int, "persisting": int,
                      "removed": int, "applied_suppressed": int}
                     (optional extra count: "closed": int)

Optional self-audit keys (validated only if present, manifest_version 1.1.0+):
  unverified_sources  : [str, ...]   # n-flagged urls used this run
  broken_skips        : [str, ...]   # x-flagged urls skipped by merge_urls
  malformed_skips     : [str, ...]   # unparseable urls.md rows
  proposed_downgrades : [{"url": str, "from": "v", "to": "x", "reason": str}, ...]
  skipped_profiles    : [{"profile": str, "reason": str}, ...]  # failed preflight

Usage:
  python3 skill/lib/write_runlog.py --in runlog.json [--root .]
  cat runlog.json | python3 skill/lib/write_runlog.py
"""
import os
import sys
import json
import argparse

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REQUIRED_LIST_KEYS = ["queries_run", "queries_null", "fetch_failures"]
REQUIRED_STR_KEYS = ["manifest_version", "run_date", "profile"]
COUNT_KEYS = ["new", "persisting", "removed", "applied_suppressed"]
# Optional self-audit keys (manifest_version 1.1.0+); validated only if present.
OPTIONAL_LIST_KEYS = ["unverified_sources", "broken_skips", "malformed_skips",
                      "proposed_downgrades", "skipped_profiles"]


def validate(log):
    errors = []
    for k in REQUIRED_STR_KEYS:
        if not isinstance(log.get(k), str) or not log.get(k):
            errors.append(f"'{k}' must be a non-empty string")
    for k in REQUIRED_LIST_KEYS:
        if not isinstance(log.get(k), list):
            errors.append(f"'{k}' must be a list")
    sources = log.get("sources_hit")
    if not isinstance(sources, list):
        errors.append("'sources_hit' must be a list")
    else:
        for i, s in enumerate(sources):
            if not (isinstance(s, dict) and isinstance(s.get("name"), str)
                    and isinstance(s.get("count"), int)):
                errors.append(f"sources_hit[{i}] must be {{name:str, count:int}}")
    counts = log.get("counts")
    if not isinstance(counts, dict):
        errors.append("'counts' must be an object")
    else:
        for k in COUNT_KEYS:
            if not isinstance(counts.get(k), int):
                errors.append(f"counts.{k} must be an int")
        if "closed" in counts and not isinstance(counts.get("closed"), int):
            errors.append("counts.closed must be an int")
    for k in OPTIONAL_LIST_KEYS:
        if k in log and not isinstance(log.get(k), list):
            errors.append(f"'{k}' must be a list when present")
    return errors


def main():
    ap = argparse.ArgumentParser(description="Validate and archive a run-log.")
    ap.add_argument("--in", dest="infile", help="input JSON file (default: stdin)")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="repo root (default: inferred)")
    args = ap.parse_args()

    raw = open(args.infile, encoding="utf-8").read() if args.infile else sys.stdin.read()
    log = json.loads(raw)

    errors = validate(log)
    if errors:
        sys.exit("write_runlog.py: schema validation failed:\n  - " + "\n  - ".join(errors))

    out_dir = os.path.join(args.root, "profiles", log["profile"], "history", "runs", log["run_date"])
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "run-log.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"write_runlog.py: wrote {out_path}", file=sys.stderr)
    print(out_path)


if __name__ == "__main__":
    main()
