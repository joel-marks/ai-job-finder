#!/usr/bin/env python3
"""merge_urls.py — build the deduped careers-URL sweep list for a run.

Reads each selected profile's urls.md, extracts every careers_url, normalises
and dedups them, attributes each back to the profiles (and orgs) that asked for
it, and writes _run-urls.json at the repo root. Overwrites every run.

urls.md is a YAML block-sequence of flat mappings (see SKILL.md for the schema):
  - org: Example Trust
    careers_url: https://example.org/careers
    fetch_method: fetch          # fetch | browse | search
    sector_tag: charity
    priority: 1
    last_checked: 2026-06-01
    notes: ...

A missing or empty urls.md contributes nothing and is logged to stderr.

Output (_run-urls.json), a JSON array:
  [{"url": <normalised>, "fetch_method": .., "requested_by": [profile,...],
    "orgs": [org,...]}, ...]

Usage:
  python3 skill/lib/merge_urls.py joel-rapid-bridging-work joel-long-term-totnes-career
  echo '["profile-a","profile-b"]' | python3 skill/lib/merge_urls.py
"""
import os
import re
import sys
import json
import argparse

from normalise import normalise_url, normalise_text

# repo root = two levels up from this file (skill/lib/merge_urls.py)
DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        v = v[1:-1]
    return v


def _add_kv(record, segment):
    if ":" not in segment:
        return
    key, value = segment.split(":", 1)
    record[key.strip()] = _scalar(value)


def parse_urls_md(text):
    """Parse a urls.md body into a list of dict records.

    Tolerant of markdown headings (#...) and ```fences```. stdlib only — this
    handles the constrained block-sequence-of-flat-mappings shape defined in
    SKILL.md, not arbitrary YAML.
    """
    fenced = re.findall(r"```(?:ya?ml)?\n(.*?)```", text, re.S)
    body = "\n".join(fenced) if fenced else text
    records, current = [], None
    for line in body.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current is not None:
                records.append(current)
            current = {}
            _add_kv(current, stripped[2:].strip())
        elif current is not None:
            _add_kv(current, stripped)
    if current is not None:
        records.append(current)
    return records


def main():
    ap = argparse.ArgumentParser(description="Merge careers URLs across profiles.")
    ap.add_argument("profiles", nargs="*", help="profile folder names")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="repo root (default: inferred)")
    ap.add_argument("--out", help="output path (default: <root>/_run-urls.json)")
    args = ap.parse_args()

    profiles = args.profiles
    if not profiles and not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            profiles = json.loads(piped)
    if not profiles:
        sys.exit("merge_urls.py: no profiles given")

    merged = {}  # normalised url -> entry
    for profile in profiles:
        path = os.path.join(args.root, "profiles", profile, "urls.md")
        if not os.path.exists(path):
            print(f"merge_urls.py: {profile}/urls.md missing — skipped", file=sys.stderr)
            continue
        text = open(path, encoding="utf-8").read()
        records = parse_urls_md(text)
        if not records:
            print(f"merge_urls.py: {profile}/urls.md empty — contributes nothing", file=sys.stderr)
            continue
        for rec in records:
            careers = rec.get("careers_url")
            if not careers:
                continue
            url = normalise_url(careers)
            if not url:
                continue
            entry = merged.setdefault(url, {
                "url": url,
                "fetch_method": rec.get("fetch_method") or "fetch",
                "requested_by": [],
                "orgs": [],
            })
            if profile not in entry["requested_by"]:
                entry["requested_by"].append(profile)
            org = rec.get("org")
            if org and org not in entry["orgs"]:
                entry["orgs"].append(org)

    result = [merged[k] for k in sorted(merged)]
    out_path = args.out or os.path.join(args.root, "_run-urls.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"merge_urls.py: {len(result)} unique URLs from {len(profiles)} profile(s) "
          f"-> {out_path}", file=sys.stderr)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
