#!/usr/bin/env python3
"""validate_profile.py — deterministic profile preflight.

A profile is RUNNABLE iff its folder exists and contains a non-empty
PROFILE.md (the search spine). A missing or empty PROFILE.md is a core,
gracefully-handled error — never a crash. The user may create empty folders;
they still enumerate, clearly flagged not-runnable.

Single profile:  --profile <name>  -> {"profile", "valid", "reason"}
All profiles:    (no --profile)     -> [ {"profile","valid","reason"}, ... ]
                                       over every subfolder of profiles/, sorted.
                                       An empty/absent profiles/ yields [].

Used in two places (see CLAUDE.md and SKILL.md):
  - the mandatory enumeration step annotates each numbered search runnable /
    not-runnable: <reason>;
  - the per-profile load skips an invalid selected profile with its reason,
    continuing the run for the valid ones.

Usage:
  python3 skill/lib/validate_profile.py                       # all, JSON array
  python3 skill/lib/validate_profile.py --profile <name>      # one, JSON object
"""
import os
import sys
import json
import argparse

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def validate(root, name):
    folder = os.path.join(root, "profiles", name)
    if not os.path.isdir(folder):
        return {"profile": name, "valid": False, "reason": "profile folder missing"}
    spine = os.path.join(folder, "PROFILE.md")
    if not os.path.isfile(spine):
        return {"profile": name, "valid": False,
                "reason": "PROFILE.md missing — required as the search spine"}
    try:
        body = open(spine, encoding="utf-8").read()
    except OSError as exc:
        return {"profile": name, "valid": False,
                "reason": f"PROFILE.md unreadable — {exc.strerror or exc}"}
    if not body.strip():
        return {"profile": name, "valid": False,
                "reason": "PROFILE.md is empty — the search spine has no content"}
    return {"profile": name, "valid": True, "reason": "runnable"}


def list_profiles(root):
    base = os.path.join(root, "profiles")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if os.path.isdir(os.path.join(base, d)))


def main():
    ap = argparse.ArgumentParser(description="Validate profile runnability.")
    ap.add_argument("--profile", help="a single profile (default: all subfolders)")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="repo root (default: inferred)")
    args = ap.parse_args()

    if args.profile:
        result = validate(args.root, args.profile)
    else:
        result = [validate(args.root, name) for name in list_profiles(args.root)]
        runnable = sum(1 for r in result if r["valid"])
        print(f"validate_profile.py: {runnable}/{len(result)} profile(s) runnable",
              file=sys.stderr)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
