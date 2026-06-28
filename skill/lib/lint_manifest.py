#!/usr/bin/env python3
"""lint_manifest.py — audit a profile's numbered query manifest.

The manifest is a clearly-delimited block inside a profile's targets.md:

    <!-- manifest:begin -->
    Q01: digital project manager contract
    Q02: interim communications charity
    <!-- manifest:end -->

Contract (see SKILL.md §5):
  - One query per line, "Qnn: <query string>". ids are zero-padded, UNIQUE, and
    STABLE: a retired query keeps its number; a new query takes the next free id.
    Gaps are legitimate (a retired id is never reused).
  - Inside the block, blank lines and comment lines ('#...' or '<!--...-->') are
    ignored; every other line MUST be a well-formed Qnn record.

Checks:
  - STRUCTURAL (fail loud, exit non-zero): the block is present and well-formed;
    every record parses; ids are well-formed (zero-padded Qnn) and unique; at
    least one query is present.
  - WARNINGS (exit 0): a query string carrying a BANNED token — numeric duration,
    salary band, geography-everywhere ("london"), social-load exclusion, or a
    speed constraint. None of these belong in a query string; they are
    post-retrieval filters (see SKILL.md §4). Geo-SCOPED terms (Exeter, Devon,
    Totnes, …) are deliberately allowed and not flagged — only bare "london" is.

Output (stdout, always): JSON
  {profile, query_count, id_range, ids, duplicate_ids,
   banned_token_warnings: [{id, string, reason}], structural_errors: [...]}
The JSON is emitted even on structural failure (so it stays auditable); the
process then exits non-zero with the errors on stderr.

Usage:
  python3 skill/lib/lint_manifest.py --in profiles/<name>/targets.md
  python3 skill/lib/lint_manifest.py --in profiles/<name>/targets.md --profile <name>
"""
import os
import re
import sys
import json
import argparse

BEGIN = re.compile(r"<!--\s*manifest:begin\s*-->", re.I)
END = re.compile(r"<!--\s*manifest:end\s*-->", re.I)
RECORD = re.compile(r"^(Q\d+):\s*(\S.*?)\s*$")
ID_OK = re.compile(r"^Q\d{2,}$")

# Tokens that must NEVER appear in a query string — they are post-retrieval
# filters, not search vocabulary. (reason, compiled-pattern)
BANNED = [
    ("numeric duration",
     re.compile(r"\b(\d+\s*(?:day|days|week|weeks|month|months|year|years)"
                r"|up to \d+|\d+\s*-\s*\d+\s*(?:month|months|week|weeks))\b", re.I)),
    ("salary band",
     re.compile(r"(£|\b\d+\s*k\b|\bsalary\b|\bper annum\b)", re.I)),
    ("geography-everywhere (London belongs in the post-filter)",
     re.compile(r"\blondon\b", re.I)),
    ("social-load exclusion",
     re.compile(r"\bsocial media\b", re.I)),
    ("speed constraint",
     re.compile(r"\bimmediate start\b", re.I)),
]


def parse_manifest(text):
    """Return (records, structural_errors). records = [(id, query, line_no)]."""
    lines = text.splitlines()
    begins = [i for i, l in enumerate(lines) if BEGIN.search(l)]
    ends = [i for i, l in enumerate(lines) if END.search(l)]
    errors = []
    if not begins or not ends:
        errors.append("manifest block not found: expected "
                      "<!-- manifest:begin --> … <!-- manifest:end -->")
        return [], errors
    b, e = begins[0], ends[0]
    if e < b:
        errors.append("<!-- manifest:end --> appears before <!-- manifest:begin -->")
        return [], errors

    records = []
    for ln in range(b + 1, e):
        s = lines[ln].strip()
        if not s or s.startswith("#") or s.startswith("<!--"):
            continue
        m = RECORD.match(s)
        if not m:
            errors.append(f"line {ln + 1}: not a 'Qnn: <query>' record: {s!r}")
            continue
        rid, qstr = m.group(1), m.group(2)
        if not ID_OK.match(rid):
            errors.append(f"line {ln + 1}: id {rid!r} is not a zero-padded Qnn")
        records.append((rid, qstr, ln + 1))
    return records, errors


def main():
    ap = argparse.ArgumentParser(description="Lint a profile's query manifest.")
    ap.add_argument("--in", dest="infile", required=True, help="path to targets.md")
    ap.add_argument("--profile", default=None,
                    help="profile name (default: parent folder of targets.md)")
    args = ap.parse_args()

    text = open(args.infile, encoding="utf-8").read()
    records, errors = parse_manifest(text)
    ids = [r[0] for r in records]

    seen, duplicate_ids = set(), []
    for i in ids:
        if i in seen and i not in duplicate_ids:
            duplicate_ids.append(i)
        seen.add(i)
    if duplicate_ids:
        errors.append(f"duplicate ids: {', '.join(duplicate_ids)}")

    if not records and not errors:
        errors.append("manifest block contains no queries")

    warnings = []
    for rid, qstr, _ in records:
        for reason, rx in BANNED:
            if rx.search(qstr):
                warnings.append({"id": rid, "string": qstr, "reason": reason})

    nums = [int(re.sub(r"\D", "", i)) for i in ids if re.sub(r"\D", "", i)]
    id_range = [f"Q{min(nums):02d}", f"Q{max(nums):02d}"] if nums else []

    profile = args.profile or os.path.basename(
        os.path.dirname(os.path.abspath(args.infile)))

    out = {
        "profile": profile,
        "query_count": len(records),
        "id_range": id_range,
        "ids": ids,
        "duplicate_ids": duplicate_ids,
        "banned_token_warnings": warnings,
        "structural_errors": errors,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))

    for w in warnings:
        print(f"lint_manifest.py: WARNING {w['id']} — {w['reason']}: {w['string']!r}",
              file=sys.stderr)
    if errors:
        sys.exit("lint_manifest.py: STRUCTURAL FAILURE:\n  - " + "\n  - ".join(errors))


if __name__ == "__main__":
    main()
