#!/usr/bin/env python3
"""mark_closed.py — set a role's status to "closed" in a profile's ledger.

The manual / agent-confirmed close override, analogous to mark_applied.py. Use
it for the two non-deterministic close routes:
  - agent-confirmed: a detail fetch returned 404 or "position closed" on a
    previously-live ad — the agent runs this during the run.
  - manual: the user knows a role is gone (backs the CLAUDE.md
    `mark <role-id> closed [reason]` command).
The third route — N consecutive absent runs — is handled automatically by
diff_roles.py and does not use this script.

Sets status="closed" in seen-roles.json for the id, stamping closed_date and
closed_reason. If the id is not yet in the ledger it is created as a minimal
closed entry (mirrors mark_applied.py). Never touches applications.json.

Usage:
  python3 skill/lib/mark_closed.py --role-id r-abc1234567 --profile <name> \
      [--reason "404 on detail page"] [--date 2026-06-27] [--root .]
"""
import os
import sys
import json
import argparse
import datetime

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
    ap = argparse.ArgumentParser(description="Mark a role as closed for a profile.")
    ap.add_argument("--role-id", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--reason", default="")
    ap.add_argument("--date", dest="closed_date", default=datetime.date.today().isoformat())
    ap.add_argument("--org", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--url", default=None)
    ap.add_argument("--root", default=DEFAULT_ROOT)
    args = ap.parse_args()

    seen_path = os.path.join(args.root, "profiles", args.profile, "history", "seen-roles.json")
    seen = _load(seen_path, {})

    reason = args.reason or "manual close"
    if args.role_id in seen:
        entry = seen[args.role_id]
        entry["status"] = "closed"
        entry["closed_date"] = args.closed_date
        entry["closed_reason"] = reason
        if args.org is not None:
            entry["org"] = args.org
        if args.title is not None:
            entry["title"] = args.title
        if args.url is not None:
            entry["url"] = args.url
    else:
        entry = {
            "org": args.org, "title": args.title, "url": args.url,
            "first_seen": args.closed_date, "last_seen": args.closed_date,
            "runs_seen": 0, "absent_runs": 0, "status": "closed",
            "closed_date": args.closed_date, "closed_reason": reason,
            "provenance": [],
        }
        seen[args.role_id] = entry
        print(f"mark_closed.py: {args.role_id} was not in the ledger — created as closed",
              file=sys.stderr)

    _dump(seen_path, seen)
    print(f"mark_closed.py: {args.role_id} -> closed for {args.profile} ({reason})",
          file=sys.stderr)
    print(json.dumps(seen[args.role_id], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
