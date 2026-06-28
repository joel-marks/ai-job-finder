#!/usr/bin/env python3
"""role_id.py — assign deterministic role-ids to a batch of roles.

This is the ONLY sanctioned way to mint a role_id. Never compute one by hand.

Input  (JSON array): [{"org": .., "title": .., "url": ..}, ...]
Output (JSON array): the same objects, each with "role_id" added. Any other
                     keys already on an object (e.g. provenance) are preserved.

role_id = "r-" + first 10 hex chars of SHA1(
    normalise_text(org) | normalise_text(title) | normalise_url(url) )

The hash collapses only EXACT org|title|url matches. Judging whether two
differently-worded listings are the same role stays with the agent.

Usage:
  python3 skill/lib/role_id.py --in roles.json --out roles-with-ids.json
  cat roles.json | python3 skill/lib/role_id.py
"""
import sys
import json
import hashlib
import argparse

from normalise import normalise_text, normalise_url


def compute_role_id(org, title, url):
    key = "|".join([normalise_text(org), normalise_text(title), normalise_url(url)])
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return "r-" + digest[:10]


def main():
    ap = argparse.ArgumentParser(description="Add role_id to a batch of roles.")
    ap.add_argument("--in", dest="infile", help="input JSON file (default: stdin)")
    ap.add_argument("--out", dest="outfile", help="output JSON file (default: stdout)")
    args = ap.parse_args()

    raw = open(args.infile, encoding="utf-8").read() if args.infile else sys.stdin.read()
    roles = json.loads(raw)
    if not isinstance(roles, list):
        sys.exit("role_id.py: input must be a JSON array of {org,title,url}")

    for r in roles:
        if not isinstance(r, dict):
            sys.exit("role_id.py: every element must be an object")
        r["role_id"] = compute_role_id(r.get("org"), r.get("title"), r.get("url"))

    out = json.dumps(roles, indent=2, ensure_ascii=False)
    if args.outfile:
        with open(args.outfile, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
        print(f"role_id.py: wrote {len(roles)} roles -> {args.outfile}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
