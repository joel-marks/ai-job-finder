#!/usr/bin/env python3
"""diff_roles.py — the run ledger diff. The ONLY way to diff a run.

Pure set logic against the profile's seen-roles.json and applications.json.
It updates seen-roles.json in place and prints the run partition to stdout.
Status transitions to "closed" stay the agent's call after verification — this
script only FLAGS removed-candidates; it never closes anything.

Inputs:
  --roles         JSON array of this run's roles, each WITH a role_id
                  (i.e. the output of role_id.py, optionally carrying a
                  "provenance" list or a "source" string).
  --seen          path to the profile's seen-roles.json (created if absent)
  --applications  path to the profile's applications.json (created if absent)
  --run-date      YYYY-MM-DD (default: today)

Partition printed to stdout:
  {"new": [...], "persisting": [...], "removed_candidates": [...],
   "applied_suppressed": [...]}
each element is {role_id, org, title, url}.

Behaviour per run role:
  - id in applications.json   -> applied_suppressed (ledger bumped, status="applied")
  - else id already in seen   -> persisting (bump last_seen, runs_seen, merge provenance)
  - else                      -> new (fresh ledger entry, status="live")
removed_candidates = ledger ids with status "live" that are absent this run.

Usage:
  python3 skill/lib/diff_roles.py --roles run.json \
      --seen profiles/<p>/history/seen-roles.json \
      --applications profiles/<p>/history/applications.json --run-date 2026-06-27
"""
import sys
import json
import argparse
import datetime


def _load(path, default):
    if path and __import__("os").path.exists(path):
        text = open(path, encoding="utf-8").read().strip()
        return json.loads(text) if text else default
    return default


def _sources(role):
    prov = role.get("provenance")
    if isinstance(prov, list):
        return [p for p in prov if p]
    if isinstance(prov, str) and prov:
        return [prov]
    src = role.get("source")
    return [src] if src else []


def _merge_unique(existing, incoming):
    out = list(existing)
    for item in incoming:
        if item not in out:
            out.append(item)
    return out


def _slim(role_id, obj):
    return {
        "role_id": role_id,
        "org": obj.get("org"),
        "title": obj.get("title"),
        "url": obj.get("url"),
    }


def main():
    ap = argparse.ArgumentParser(description="Diff a run against the profile ledger.")
    ap.add_argument("--roles", required=True, help="this run's roles (with role_id)")
    ap.add_argument("--seen", required=True, help="seen-roles.json path")
    ap.add_argument("--applications", required=True, help="applications.json path")
    ap.add_argument("--run-date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    roles = json.loads(open(args.roles, encoding="utf-8").read())
    seen = _load(args.seen, {})
    applications = _load(args.applications, {})
    run_date = args.run_date

    partition = {"new": [], "persisting": [], "removed_candidates": [], "applied_suppressed": []}
    this_run_ids = set()

    for role in roles:
        rid = role.get("role_id")
        if not rid:
            sys.exit("diff_roles.py: every role needs a role_id (run role_id.py first)")
        this_run_ids.add(rid)
        incoming_sources = _sources(role)

        if rid in applications:
            entry = seen.get(rid, {
                "org": role.get("org"), "title": role.get("title"), "url": role.get("url"),
                "first_seen": run_date, "runs_seen": 0, "provenance": [],
            })
            entry["last_seen"] = run_date
            entry["runs_seen"] = entry.get("runs_seen", 0) + 1
            entry["provenance"] = _merge_unique(entry.get("provenance", []), incoming_sources)
            entry["status"] = "applied"
            seen[rid] = entry
            partition["applied_suppressed"].append(_slim(rid, entry))
        elif rid in seen:
            entry = seen[rid]
            entry["last_seen"] = run_date
            entry["runs_seen"] = entry.get("runs_seen", 0) + 1
            entry["provenance"] = _merge_unique(entry.get("provenance", []), incoming_sources)
            partition["persisting"].append(_slim(rid, entry))
        else:
            entry = {
                "org": role.get("org"),
                "title": role.get("title"),
                "url": role.get("url"),
                "first_seen": run_date,
                "last_seen": run_date,
                "runs_seen": 1,
                "status": "live",
                "provenance": incoming_sources,
            }
            seen[rid] = entry
            partition["new"].append(_slim(rid, entry))

    for rid, entry in seen.items():
        if entry.get("status") == "live" and rid not in this_run_ids:
            partition["removed_candidates"].append(_slim(rid, entry))

    with open(args.seen, "w", encoding="utf-8") as fh:
        json.dump(seen, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(json.dumps(partition, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
