#!/usr/bin/env python3
"""merge_urls.py — build the deduped careers-URL sweep list for a run.

Reads each selected profile's urls.md (now a flat CSV, see below), normalises
and dedups every URL, attributes each back to the profiles that asked for it,
and writes _run-urls.json at the repo root. Overwrites every run.

urls.md is a flat, human-curated CSV — one record per line:

    <flag>, <url>

The FIRST field is a single-character status flag, human-maintained:
  v  verified        -> include for fetching, trusted
  n  needs checking  -> include, but carried as an UNVERIFIED source (surfaces
                        in the run self-audit so the agent flags its use)
  x  checked, broken -> EXCLUDED, logged as a known-broken skip (never silent)

Lines whose first non-space character is '#' are comments (section headers) and
are ignored. Blank lines are ignored. Any record we cannot parse (no comma,
unknown flag, missing/non-normalising URL) is SKIPPED and logged per-record —
both to stderr and into the JSON report — so a stray row can never vanish.

The flags are HUMAN-CURATED. This script never rewrites urls.md and never
auto-downgrades a flag. When a v-flagged URL fails to fetch during a run, the
agent records a PROPOSED v->x downgrade in the run self-audit for the user to
action by hand (see SKILL.md). Write-back is out of scope.

Output (_run-urls.json), an object envelope so the skips reach the self-audit:
  {
    "generated_for": [profile, ...],
    "urls": [ {"url": <normalised>, "fetch_method": "fetch",
               "requested_by": [profile, ...], "orgs": [...],
               "flag": "v"|"n", "verified": true|false}, ... ],
    "skipped_broken":   [ {"profile", "line", "url", "raw"}, ... ],   # x flags
    "skipped_malformed":[ {"profile", "line", "raw", "reason"}, ... ],
    "missing_or_empty": [ {"profile", "reason"}, ... ],
    "unverified_urls":  [ <normalised url>, ... ],                    # n flags kept
    "counts": {"unique", "verified", "unverified",
               "broken_skipped", "malformed_skipped"}
  }
The `urls` entries keep the prior per-entry shape (url / fetch_method /
requested_by / orgs) and add flag + verified; the envelope adds the report.

A missing or empty urls.md contributes nothing, is logged, and is not an error.

Usage:
  python3 skill/lib/merge_urls.py joel-rapid-bridging-work joel-long-term-totnes-career
"""
import os
import sys
import json
import argparse

from normalise import normalise_url

# repo root = two levels up from this file (skill/lib/merge_urls.py)
DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VALID_FLAGS = {"v", "n", "x"}
URLS_FILENAME = "urls.md"


def parse_line(raw):
    """Classify one raw line of a urls CSV.

    Returns one of:
      ("comment", None, None)              blank or '#'-prefixed line
      ("record", flag, normalised_url)     a well-formed v/n/x record
      ("malformed", None, reason)          a record we could not parse
    """
    stripped = raw.strip()
    if not stripped or stripped.startswith("#"):
        return ("comment", None, None)
    if "," not in stripped:
        return ("malformed", None, "no comma separator (expected '<flag>, <url>')")
    flag_part, url_part = stripped.split(",", 1)
    flag = flag_part.strip().lower()
    if flag not in VALID_FLAGS:
        return ("malformed", None, f"unknown status flag {flag_part.strip()!r} (expected v/n/x)")
    url_raw = url_part.strip()
    if not url_raw:
        return ("malformed", None, "missing url")
    url = normalise_url(url_raw)
    if not url:
        return ("malformed", None, f"url did not normalise: {url_raw!r}")
    return ("record", flag, url)


def main():
    ap = argparse.ArgumentParser(description="Merge careers URLs across profiles.")
    ap.add_argument("profiles", nargs="+", help="profile folder names")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="repo root (default: inferred)")
    ap.add_argument("--out", help="output path (default: <root>/_run-urls.json)")
    args = ap.parse_args()

    profiles = args.profiles

    merged = {}            # normalised url -> entry
    skipped_broken = []    # x flags
    skipped_malformed = [] # unparseable rows
    missing_or_empty = []

    for profile in profiles:
        path = os.path.join(args.root, "profiles", profile, URLS_FILENAME)
        if not os.path.exists(path):
            print(f"merge_urls.py: {profile}/{URLS_FILENAME} missing — contributes nothing",
                  file=sys.stderr)
            missing_or_empty.append({"profile": profile, "reason": f"{URLS_FILENAME} missing"})
            continue
        lines = open(path, encoding="utf-8").read().splitlines()
        record_count = 0
        for line_no, raw in enumerate(lines, start=1):
            kind, flag, payload = parse_line(raw)
            if kind == "comment":
                continue
            if kind == "malformed":
                reason = payload
                print(f"merge_urls.py: {profile}/{URLS_FILENAME}:{line_no} "
                      f"malformed — {reason}: {raw.strip()!r}", file=sys.stderr)
                skipped_malformed.append({"profile": profile, "line": line_no,
                                          "raw": raw.strip(), "reason": reason})
                continue
            # kind == "record"
            record_count += 1
            url = payload
            if flag == "x":
                print(f"merge_urls.py: {profile}/{URLS_FILENAME}:{line_no} "
                      f"known-broken (x) — skipped: {url}", file=sys.stderr)
                skipped_broken.append({"profile": profile, "line": line_no,
                                       "url": url, "raw": raw.strip()})
                continue
            # v or n -> include
            entry = merged.setdefault(url, {
                "url": url,
                "fetch_method": "fetch",
                "requested_by": [],
                "orgs": [],          # the CSV carries no org column; kept for schema parity
                "flag": "v",
                "verified": True,
            })
            if profile not in entry["requested_by"]:
                entry["requested_by"].append(profile)
            # Reconcile duplicates conservatively: verified only if EVERY
            # contributor marked it v; any n makes the merged entry unverified,
            # so its use still surfaces in the self-audit.
            if flag == "n":
                entry["verified"] = False
                entry["flag"] = "n"

        if record_count == 0 and not any(s["profile"] == profile for s in skipped_broken) \
                and not any(s["profile"] == profile for s in skipped_malformed):
            print(f"merge_urls.py: {profile}/{URLS_FILENAME} empty — contributes nothing",
                  file=sys.stderr)
            missing_or_empty.append({"profile": profile, "reason": f"{URLS_FILENAME} empty"})

    urls = [merged[k] for k in sorted(merged)]
    unverified_urls = [e["url"] for e in urls if not e["verified"]]
    result = {
        "generated_for": list(profiles),
        "urls": urls,
        "skipped_broken": skipped_broken,
        "skipped_malformed": skipped_malformed,
        "missing_or_empty": missing_or_empty,
        "unverified_urls": unverified_urls,
        "counts": {
            "unique": len(urls),
            "verified": sum(1 for e in urls if e["verified"]),
            "unverified": len(unverified_urls),
            "broken_skipped": len(skipped_broken),
            "malformed_skipped": len(skipped_malformed),
        },
    }

    out_path = args.out or os.path.join(args.root, "_run-urls.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    c = result["counts"]
    print(f"merge_urls.py: {c['unique']} unique URLs "
          f"({c['verified']} verified, {c['unverified']} unverified) from "
          f"{len(profiles)} profile(s); skipped {c['broken_skipped']} broken, "
          f"{c['malformed_skipped']} malformed -> {out_path}", file=sys.stderr)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
