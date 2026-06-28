#!/usr/bin/env python3
"""web-approve.py — PreToolUse approval hook for web access (allowlist-based).

INERT BY DEFAULT. This file is committed but does NOTHING unless you wire it into
your *local* .claude/settings.local.json (see .claude/settings.local.json.example)
and create a *local* .claude/web-allowlist.txt. Both local files are gitignored.

With no allowlist file present it approves only WebSearch and passes EVERY WebFetch
through to the normal permission prompt — i.e. identical to default Claude Code
behaviour. So cloning this repo changes nothing about a cloner's web access and adds
no risk; the behaviour only turns on when *you* opt in locally.

Behaviour (implemented to the current PreToolUse hook schema,
https://code.claude.com/docs/en/hooks):
  - reads the hook event JSON from stdin: {"tool_name": ..., "tool_input": {...}, ...}
  - WebSearch        -> APPROVE  (read-only; returns result snippets, no exfiltration
                                  channel — it cannot POST your data anywhere)
  - WebFetch         -> APPROVE only if tool_input.url's host equals, or is a
                       dot-boundary subdomain of, an entry in the allowlist; else
                       PASS THROUGH so the normal permission prompt still fires
  - any other tool   -> PASS THROUGH (no opinion — must never affect unrelated tools)
  - FAIL SAFE: any error, missing/empty allowlist, missing url, or unparseable url
                       -> PASS THROUGH. It NEVER approves on uncertainty, and it
                       NEVER emits a denial (so it can never block anything).

Two mechanisms, both per the documented schema:
  - APPROVE      = print a hookSpecificOutput object with permissionDecision "allow",
                   then exit 0.
  - PASS THROUGH = print nothing and exit 0. Per the docs, "Exit code 0 with no output
                   means the hook has no decision to report, so the tool call continues
                   through the normal permission flow ... staying silent doesn't
                   approve it."

Dot-boundary match (no substring matching): entry "greenhouse.io" matches
"greenhouse.io" and "boards.greenhouse.io" but NOT "evil-greenhouse.io".

Python 3 standard library only. No network. No file writes. Read-only on the allowlist.
"""
import os
import sys
import json
from urllib.parse import urlsplit


def _approve(reason):
    """Emit the 'allow' decision and exit 0."""
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    sys.stdout.write("\n")
    sys.exit(0)


def _passthrough():
    """Emit nothing and exit 0 -> the normal permission flow continues (may prompt)."""
    sys.exit(0)


def _allowlist_path():
    """The allowlist ships next to this hook: .claude/web-allowlist.txt.

    This file is .claude/hooks/web-approve.py, so the allowlist is one directory up.
    Resolving from __file__ keeps it correct regardless of the process cwd.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "web-allowlist.txt")


def _load_allowlist():
    """Return a set of lowercased host entries, or an empty set if absent/empty.

    Lines that are blank or start with '#' are ignored. Entries tolerate an
    accidental leading dot, scheme, or trailing path — only the host label is kept.
    """
    path = _allowlist_path()
    hosts = set()
    if not os.path.isfile(path):
        return hosts
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            entry = line.strip().lower()
            if not entry or entry.startswith("#"):
                continue
            entry = entry.lstrip(".")
            if "://" in entry:                 # strip an accidental scheme
                entry = entry.split("://", 1)[1]
            entry = entry.split("/", 1)[0]      # strip an accidental path
            entry = entry.split("@")[-1]        # strip accidental userinfo
            entry = entry.split(":", 1)[0]      # strip an accidental port
            if entry:
                hosts.add(entry)
    return hosts


def _host_allowed(host, allowlist):
    """Exact host or dot-boundary subdomain match. Never a substring match."""
    if not host or not allowlist:
        return False
    host = host.lower()
    for entry in allowlist:
        if host == entry or host.endswith("." + entry):
            return True
    return False


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        _passthrough()                          # empty stdin -> fail safe
    event = json.loads(raw)                      # parse error -> caught below
    tool_name = event.get("tool_name")

    if tool_name == "WebSearch":
        _approve("WebSearch is read-only (no exfiltration channel)")

    if tool_name != "WebFetch":
        _passthrough()                           # no opinion on other tools

    # WebFetch: approve only when the target host is on the local allowlist.
    url = (event.get("tool_input") or {}).get("url")
    if not url:
        _passthrough()
    host = urlsplit(url).hostname                # lowercased; port/userinfo stripped; None if unparseable
    if not host:
        _passthrough()
    if _host_allowed(host, _load_allowlist()):
        _approve("WebFetch host %r is on the local web allowlist" % host)
    _passthrough()                               # not allowlisted -> prompt as normal


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise                                    # preserve the intended exit code (0)
    except Exception:
        # Deny-by-default on uncertainty: any unexpected error -> pass through, exit 0.
        sys.exit(0)
