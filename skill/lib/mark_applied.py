#!/usr/bin/env python3
"""mark_applied.py — record an application and suppress the role from new leads.

Adds/updates the role's entry in the profile's applications.json and flips that
id's status to "applied" in its seen-roles.json. org/title/url are pulled from
seen-roles.json when present (so the call only needs the role_id), or supplied
on the command line.

applications.json schema (keyed by role_id):
  {"org", "title", "url", "date_applied", "stage", "source", "notes"}
  stage: applied | acknowledged | interviewing | offer | rejected | withdrawn

Usage:
  python3 skill/lib/mark_applied.py --role-id r-abc1234567 --profile <name> \
      [--stage applied] [--notes "..."] [--date 2026-06-27] [--root .]
"""
import os
import sys
import json
import argparse
import datetime

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAGES = ["applied", "acknowledged", "interviewing", "offer", "rejected", "withdrawn"]


def _load(path, default):
    if os.path.exists(path):
        text = open(path, encoding="utf-8").read().strip()
        return json.loads(text) if text else default
    return default


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser(description="Mark a role as applied for a profile.")
    ap.add_argument("--role-id", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--stage", default="applied", choices=STAGES)
    ap.add_argument("--notes", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--date", dest="date_applied", default=datetime.date.today().isoformat())
    ap.add_argument("--org", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--url", default=None)
    ap.add_argument("--root", default=DEFAULT_ROOT)
    args = ap.parse_args()

    history = os.path.join(args.root, "profiles", args.profile, "history")
    apps_path = os.path.join(history, "applications.json")
    seen_path = os.path.join(history, "seen-roles.json")

    applications = _load(apps_path, {})
    seen = _load(seen_path, {})
    ledger = seen.get(args.role_id, {})

    org = args.org if args.org is not None else ledger.get("org")
    title = args.title if args.title is not None else ledger.get("title")
    url = args.url if args.url is not None else ledger.get("url")

    existing = applications.get(args.role_id, {})
    applications[args.role_id] = {
        "org": org,
        "title": title,
        "url": url,
        "date_applied": existing.get("date_applied", args.date_applied),
        "stage": args.stage,
        "source": args.source or existing.get("source", ""),
        "notes": args.notes or existing.get("notes", ""),
    }
    _dump(apps_path, applications)

    # Flip status in the ledger so the role is never re-surfaced as new.
    if args.role_id in seen:
        seen[args.role_id]["status"] = "applied"
    else:
        seen[args.role_id] = {
            "org": org, "title": title, "url": url,
            "first_seen": args.date_applied, "last_seen": args.date_applied,
            "runs_seen": 0, "status": "applied", "provenance": [],
        }
    _dump(seen_path, seen)

    print(f"mark_applied.py: {args.role_id} -> stage '{args.stage}' for {args.profile}",
          file=sys.stderr)
    print(json.dumps(applications[args.role_id], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
