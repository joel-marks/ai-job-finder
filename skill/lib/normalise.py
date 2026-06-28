#!/usr/bin/env python3
"""normalise.py — the single source of truth for normalisation.

Imported by the other lib scripts so their notion of "the same URL" or
"the same text" can never drift apart. Also runnable as a tiny CLI for
ad-hoc checks.

Contract:
  normalise_text(v): lowercase, trim, collapse internal whitespace.
  normalise_url(v):  lowercase, strip scheme, strip querystring + fragment,
                     strip leading "www.", strip trailing slash.
"""
import re
import sys
import argparse
from urllib.parse import urlsplit


def normalise_text(value):
    """lowercase, trim, collapse internal whitespace."""
    if value is None:
        return ""
    text = str(value).lower().strip()
    return re.sub(r"\s+", " ", text)


def normalise_url(value):
    """lowercase, strip scheme, strip querystring+fragment, strip leading
    'www.', strip trailing slash. Returns host+path only."""
    if value is None:
        return ""
    raw = str(value).strip().lower()
    if not raw:
        return ""
    # Give urlsplit an authority to chew on even when no scheme is present,
    # so "example.com/jobs" parses the same as "https://example.com/jobs".
    work = raw if "://" in raw else "//" + raw.lstrip("/")
    parts = urlsplit(work)
    host = parts.netloc
    if host.startswith("www."):
        host = host[4:]
    # Query and fragment are simply never re-appended.
    cleaned = (host + parts.path).rstrip("/")
    return cleaned


def main():
    ap = argparse.ArgumentParser(description="Normalise a url or text value.")
    ap.add_argument("kind", choices=["url", "text"], help="which normaliser to run")
    ap.add_argument("value", help="the value to normalise")
    args = ap.parse_args()
    fn = normalise_url if args.kind == "url" else normalise_text
    print(fn(args.value))


if __name__ == "__main__":
    main()
