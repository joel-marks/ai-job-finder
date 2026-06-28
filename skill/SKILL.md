---
name: job-search-run
description: The generic per-profile job-search run procedure for this engine. Followed once per selected profile. Deterministic bookkeeping is delegated to skill/lib/*; judgement stays with the agent.
manifest_version: 1.1.0
---

# SKILL.md — the generic run procedure

This is the engine's run procedure, followed **once per selected profile**. It is
generic: nothing here hardcodes a particular profile's ranking, income, or geography.
Each profile self-describes those in its own files.

`manifest_version` (frontmatter, currently `1.1.0`) versions this procedure and the
query-manifest contract. **Query ids are stable across versions, and a retired query
id is never reused.** Bump `manifest_version` when the contract changes; record the
version in every `run-log.json` and on every dashboard.

**Changes in 1.1.0:** `urls.md` is now a flat `flag, url` CSV (was a YAML
block-sequence); `seen-roles.json` records carry an `absent_runs` counter and a
deterministic close-path; profiles are preflight-validated before a run; and the
self-audit gains unverified/broken/malformed URL accounting plus proposed v→x
downgrades. Older ledgers upgrade transparently (`absent_runs` defaults to 0).

> Prerequisite (from CLAUDE.md): the user has already been shown the numbered list of
> `profiles/` (each annotated runnable / not-runnable via `validate_profile.py`) and
> has selected which to run. Do not start retrieval before that.

## The determinism split (why skill/lib/ exists)
Anything deterministic, repetitive, and judgement-free is done **once** in a committed
script and called every run — it fixes the logic, costs almost no tokens, and fails
loudly instead of silently corrupting state. Anything needing judgement stays with
you. The scripts are **required steps, not optional tools**:
- **role-ids are minted ONLY by `role_id.py`** — never compute a hash by hand.
- **the ledger diff is performed ONLY by `diff_roles.py`** — never diff by hand.

---

## 0. PREFLIGHT (per selected profile, required)
Before loading a selected profile, validate it with
`python3 skill/lib/validate_profile.py --profile <name>` → `{profile, valid, reason}`.
A profile is runnable **only** if its folder exists and contains a **non-empty
`PROFILE.md`** (the search spine). If `valid` is false, **skip that profile** — do
not crash — with a structured line stating state → consequence, e.g.
`Skipped <name>: PROFILE.md missing — required as the search spine`. Continue the run
for the other valid selected profiles. **Every skip is reported in the run summary
and in `run-log.json` (`skipped_profiles`)** — never silently dropped.

## 1. READ-SET (per profile)
Read the selected profile's files and hold this hierarchy of authority:

- **`PROFILE.md` is the spine — authoritative.** Objectives, ranking logic, income
  floor/target, geography, constraints. Everything ranks on what PROFILE.md says.
- **`skills.md`, `experience.md`, `cv.md` are supporting evidence**, not authority.
  The same facts recur across them and PROFILE.md (e.g. the Salvation Army role).
  **PROFILE.md wins; the rest are evidence. Never double-count** a single fact because
  it appears in several files.
- **`targets.md` supplies the query manifest, named target orgs, and lanes.**
- **`urls.md` supplies enumerated employer careers URLs** (schema below).

If two files disagree, PROFILE.md governs; note the contradiction in the self-audit
rather than silently picking one.

## 2. HISTORY (per profile)
Locate `profiles/<name>/history/`; **create it if absent.** Load:
- `seen-roles.json` — the role ledger (schema below).
- `applications.json` — applications in flight (schema below).
Create either **empty (`{}`) against schema** if absent. These are the run's memory;
they persist across runs and must never be edited by hand in ways the scripts own.

## 3. RANK on the profile's OWN logic
Rank strictly on the profile's stated decision rules — its tiers, its income
floor/target, its geography model, its tiebreakers. The engine does not impose a
ranking. If the profile defines tiers (e.g. fit windows), render to them.

## 4. VOCABULARY vs FILTERS (keep them formally separate)
- **SEARCH VOCABULARY = role-type terms, searched wide.** These go *into* queries.
  Promote **"change communications"** and **"transformation communications"** to
  first-class search terms alongside the profile's own terms.
- **JUDGING FILTERS = length/duration, salary band, geography, social-load.** These are
  applied **ONLY after retrieval**, never inside a query.
- **Hard rule: duration or length must NEVER appear in a query string.** You do not
  search "2 month contract"; you search the role type wide, then filter by duration
  when judging.

## 5. QUERY MANIFEST
The profile's `targets.md` defines the queries. **Execute every query verbatim — all
of them — before any judging.** Number them `Q01`, `Q02`, … in manifest order. Record
which queries returned nothing (`queries_null`). Stable ids: once a query has an id,
that id keeps its meaning across runs and versions; retire rather than renumber.

The source list in `targets.md` is a **floor, not a ceiling** — honour its standing
directive to attempt at least two off-list sources per run and record the full reach
of sites hit (productive or not) for the dashboard's "Net cast" list.

## 6. URLS SWEEP (required)
`urls.md` is a flat, human-curated `flag, url` CSV (schema below). **Always go
through `merge_urls.py`** — even for a single profile — never parse `urls.md` by
hand. Run `python3 skill/lib/merge_urls.py <name> [<name> …]`; it writes the
`_run-urls.json` envelope at repo root: deduped + normalised `urls`, plus the skip
report. Then:
- **Fetch each `urls[*]` once** and attribute results back via `requested_by`. The
  flag governs trust:
  - `verified: true` (flag `v`) — a trusted source.
  - `verified: false` (flag `n`) — fetch it, but carry an **"unverified source"**
    marker; list every unverified URL actually used in the self-audit
    (`unverified_sources`).
- **`skipped_broken`** (flag `x`) are known-broken and were excluded — surface the
  count/list in the self-audit (`broken_skips`); never silently drop them.
- **`skipped_malformed`** rows could not be parsed — surface each in the self-audit
  (`malformed_skips`) so a stray row is visible, never lost.
- An empty or missing `urls.md` contributes nothing — it lands in
  `missing_or_empty`; carry on.

**Proposed downgrades (no write-back).** The flags are human-curated; the engine
**never edits `urls.md`**. When a `v`-flagged URL **fails to fetch** during the run,
record a **PROPOSED `v→x` downgrade** in the self-audit (`proposed_downgrades`:
`{url, from: "v", to: "x", reason}`) for the user to action by hand. Do not change
the flag yourself.

## 7. TWO-PASS retrieval (locked method)
1. **Broad pass:** wide searches (vocabulary terms) to discover candidate roles and
   source URLs.
2. **Detail pass:** fetch the **individual detail page** of each candidate to confirm
   **contract type, salary, closing date, and open status** before featuring it.

**Never feature a role off an index/search snippet alone.** A snippet locates a role;
only the fetched detail page confirms it.

## 8. ROLE IDENTITY
- Assign role-ids **only via `role_id.py`** (batch the whole run's roles in one call).
- `role_id = "r-" + first 10 hex of SHA1(normalise_text(org) | normalise_text(title) |
  normalise_url(url))`.
- Collapse exact cross-source duplicates to **one** id; record every source that
  surfaced it as **provenance**.
- The hash catches **only exact `org|title|url` matches**. Judging whether two
  differently-worded listings are the **same role** is yours — merge them by hand
  (pick one canonical org/title/url, list all sources as provenance) before diffing.

## 9. DIFF AND SUPPRESS
Run `diff_roles.py` — **do not diff by hand.** It partitions the run into:
- **new** — ids absent from `seen-roles.json` (fresh entry, `absent_runs: 0`);
- **persisting** — ids in both (it bumps `last_seen`, `runs_seen`, merges provenance,
  and **resets `absent_runs` to 0**);
- **removed-candidates** — ledger ids with status `live` **absent this run** whose
  `absent_runs` is **still below** the close threshold. Their `absent_runs` is
  incremented; they remain `live` and are flagged for your attention.
- **auto-closed** — ledger ids with status `live` whose `absent_runs` has reached the
  threshold (default **2**, `--close-threshold`); the script sets `status: closed`,
  stamping `closed_date`/`closed_reason`. This is the deterministic close route.
- **applied-suppressed** — this run's ids that are present in `applications.json`.

### Close-path — three routes to `closed` (absence alone ≠ closure)
A single missed run is not closure (a query can simply miss). A live role becomes
`closed` only via:
1. **agent-confirmed** — a detail fetch returns 404 or an explicit "position closed"
   on a previously-live ad. Run `mark_closed.py` during the run
   (`--reason "agent-confirmed: 404"`).
2. **N-run threshold** — `diff_roles.py` auto-closes after `absent_runs` ≥ threshold.
3. **manual** — the user's `mark <role-id> closed [reason]` command (`mark_closed.py`).

`applied` and `excluded` roles are **never** auto-closed and never tracked for
absence.

**Suppression rule:** any id in `applications.json` is **pulled out of the new-leads
tiers** into an **"In flight"** section showing its stage. It is **never** re-surfaced
as new and **never** counted as new.

> Note the coupling: `mark_applied.py` flips a ledger id's status to `applied` and
> `mark_closed.py` to `closed`; `diff_roles.py` only tracks absence for `live` ids —
> so an applied or already-closed role that drops out of a run is correctly *not*
> mis-flagged as removed and never re-counted. Always change status via the commands,
> not by editing JSON.

## 10. RENDER
Fill `skill/dashboard-template.html` (the canvas template — placeholders like
`{{DATE}}`, `{{H1}}`, `{{PREAMBLE}}`, `{{BASELINE}}`, `{{DAYRATE}}`, `{{SITES_LIST}}`,
`{{SITES_COUNT}}`, `{{SECTIONS}}`, and the SECTION/ITEM block templates at its foot)
and write to `profiles/<name>/dashboard.html`. Render against the template **as-is** —
it is revised in a later sprint; do not modify it now. Also write a
`dashboard-meta.json` sidecar next to it (schema below) for `build_index.py`.

## 11. ARCHIVE
Into `profiles/<name>/history/runs/<YYYY-MM-DD>/`:
- copy the dashboard snapshot (`dashboard.html`);
- write `run-log.json` via `write_runlog.py` (it validates against schema and creates
  the dated folder).

## 12. INDEX
After **all** selected profiles are done, run `build_index.py` to regenerate the root
`index.html` from each profile's `dashboard.html` + `dashboard-meta.json`. It is pure
templated output — no client-side filesystem reads — so it works from `file://`.

## 13. SELF-AUDIT (required)
Surface on the dashboard **and** in `run-log.json`:
- `manifest_version`;
- queries run, and queries returning nothing;
- fetch failures and sources unreachable;
- **profiles skipped at preflight** (`skipped_profiles`) — state → reason;
- **unverified (`n`-flag) sources actually used** (`unverified_sources`);
- **known-broken (`x`-flag) URLs skipped** (`broken_skips`) and **malformed `urls.md`
  rows skipped** (`malformed_skips`) — both straight from the `_run-urls.json` report;
- **proposed `v→x` downgrades** (`proposed_downgrades`) for any verified URL that
  failed to fetch — the user actions these by hand; the engine never edits `urls.md`;
- **roles auto-closed / closed** this run (`counts.closed`);
- **what could not be confirmed** (e.g. salary/closing-date not found on the detail
  page) — honesty about gaps is part of the contract.

---

## SCHEMAS (the contract for all files)

### `urls.md` — a flat, human-curated `flag, url` CSV
One record per line: a single-character **status flag**, a comma, then the careers
URL. The flag is human-maintained — the engine reads it and **never writes it back**.
```csv
# === SECTION HEADER (a '#' line is a comment, ignored) ===
v, https://example.org/careers          # v = verified  -> fetch, trusted
n, https://needs-checking.org/jobs      # n = needs checking -> fetch, but UNVERIFIED
x, https://dead.example/careers         # x = broken    -> EXCLUDED, logged as skip
```
- `v` verified → included for fetching.
- `n` needs checking → included, but carried as an **unverified source** (surfaces in
  the self-audit).
- `x` checked-broken → **excluded** and logged as a known-broken skip.
- `#`-prefixed and blank lines are ignored; any other unparseable line (no comma,
  unknown flag, missing/non-normalising URL) is **skipped and logged per-record**.

The CSV carries **no org/fetch_method/priority columns** — those are gone from the
1.1.0 format. Parsing is done **only** by `merge_urls.py`, never by hand.

### `_run-urls.json` — the sweep envelope written by `merge_urls.py` (repo root)
Transient, git-ignored, regenerated every run. An object (not a bare array) so the
skips reach the self-audit:
```json
{
  "generated_for": ["joel-rapid-bridging-work"],
  "urls": [
    {"url": "example.org/careers", "fetch_method": "fetch",
     "requested_by": ["joel-rapid-bridging-work"], "orgs": [],
     "flag": "v", "verified": true}
  ],
  "skipped_broken":    [{"profile": "...", "line": 7,  "url": "...", "raw": "x, ..."}],
  "skipped_malformed": [{"profile": "...", "line": 9,  "raw": "...", "reason": "..."}],
  "missing_or_empty":  [{"profile": "...", "reason": "urls.md missing"}],
  "unverified_urls":   ["needs-checking.org/jobs"],
  "counts": {"unique": 1, "verified": 1, "unverified": 0,
             "broken_skipped": 1, "malformed_skipped": 1}
}
```
A duplicate URL is merged conservatively: `verified` is true only if **every**
contributor flagged it `v`; any `n` makes the merged entry unverified.

### `seen-roles.json` — the role ledger
Object keyed by `role_id`. `absent_runs` counts consecutive runs a `live` role has
been missing (drives the deterministic close-path); it defaults to `0` when absent, so
pre-1.1.0 ledgers upgrade transparently. `closed_date`/`closed_reason` are written
when a role is closed (by `diff_roles.py` at threshold, or by `mark_closed.py`).
```json
{
  "r-077711524e": {
    "org": "Example Trust",
    "title": "Change Communications Lead",
    "url": "https://example.org/jobs/1",
    "first_seen": "2026-06-27",
    "last_seen": "2026-06-27",
    "runs_seen": 1,
    "absent_runs": 0,
    "status": "live",            // live | closed | removed | excluded | applied
    "provenance": ["CharityJob", "Reed"],
    "closed_date": "2026-07-11",      // present only once closed
    "closed_reason": "absent 2 consecutive runs (threshold 2)"
  }
}
```

### `applications.json` — applications in flight
Object keyed by `role_id`:
```json
{
  "r-077711524e": {
    "org": "Example Trust",
    "title": "Change Communications Lead",
    "url": "https://example.org/jobs/1",
    "date_applied": "2026-06-27",
    "stage": "applied",          // applied | acknowledged | interviewing | offer | rejected | withdrawn
    "source": "CharityJob",
    "notes": "Tailored CV variant B"
  }
}
```

### `run-log.json` — one per run, archived under history/runs/<date>/
Required keys as below; `write_runlog.py` validates them and fails loud on violation.
The 1.1.0 self-audit keys (and `counts.closed`) are **optional** — validated only when
present, so older logs still pass.
```json
{
  "manifest_version": "1.1.0",
  "run_date": "2026-06-27",
  "profile": "joel-rapid-bridging-work",
  "queries_run": ["Q01", "Q02", "Q03"],
  "queries_null": ["Q02"],
  "fetch_failures": ["https://blocked.example/jobs"],
  "sources_hit": [{"name": "CharityJob", "count": 6}, {"name": "Reed", "count": 3}],
  "counts": {"new": 4, "persisting": 2, "removed": 1, "applied_suppressed": 1, "closed": 1},

  "unverified_sources": ["needs-checking.org/jobs"],
  "broken_skips": ["dead.example/careers"],
  "malformed_skips": ["bad line from urls.md"],
  "proposed_downgrades": [{"url": "example.org/careers", "from": "v", "to": "x",
                           "reason": "fetch failed (timeout) this run"}],
  "skipped_profiles": [{"profile": "joel-long-term-totnes-career",
                        "reason": "PROFILE.md missing — required as the search spine"}]
}
```

### `dashboard-meta.json` — sidecar next to dashboard.html, read by build_index.py
```json
{
  "profile": "joel-rapid-bridging-work",
  "last_run": "2026-06-27",
  "counts": {"new": 4, "persisting": 2, "in_flight": 1},
  "status_line": "4 new leads, 2 persisting, 1 application in flight."
}
```

---

## skill/lib/ — the scripts (JSON in / JSON out, stdlib only)
Run from the repo root. Each derives the repo root from its own location, so `--root`
is optional.

- **`normalise.py`** — single source of truth for normalisation, imported by the
  others so they can never drift. `normalise_url`: lowercase, strip scheme, strip
  query+fragment, strip leading `www.`, strip trailing slash. `normalise_text`:
  lowercase, trim, collapse internal whitespace.
- **`role_id.py`** — `--in roles.json` (array of `{org,title,url}`) → same array with
  `role_id` added. Batch the whole run in one call.
- **`merge_urls.py`** — `<profile> [<profile> …]` → reads each `urls.md` (the flat
  `flag, url` CSV), normalises and dedups the `v`/`n` URLs, excludes `x`, skips+logs
  malformed rows, and writes the `_run-urls.json` **envelope** (`urls` + skip report,
  see schema). Overwrites each run; handles empty/missing `urls.md` gracefully.
- **`diff_roles.py`** — `--roles run.json --seen … --applications … [--run-date …]
  [--close-threshold N]` → updates `seen-roles.json` in place and prints the
  `{new, persisting, removed_candidates, applied_suppressed, auto_closed}` partition.
  Tracks `absent_runs` for `live` roles and **auto-closes** at the threshold
  (default 2); never touches `applied`/`excluded` roles.
- **`validate_profile.py`** — `[--profile <name>]` → `{profile, valid, reason}` (or a
  JSON array over all `profiles/` subfolders when no `--profile`). Runnable = folder
  exists **and** non-empty `PROFILE.md`. Backs the enumeration annotations and the
  per-profile preflight skip.
- **`mark_closed.py`** — `--role-id … --profile … [--reason …]` → sets the id's status
  to `closed` in `seen-roles.json` (stamping `closed_date`/`closed_reason`). Backs the
  agent-confirmed and manual close routes and the CLAUDE.md `mark <role-id> closed`
  command.
- **`write_runlog.py`** — `--in runlog.json` → validates against the run-log schema and
  writes `profiles/<profile>/history/runs/<run_date>/run-log.json`. Fails loudly on a
  schema violation.
- **`build_index.py`** → scans `profiles/*/` for `dashboard.html` + `dashboard-meta.json`
  and writes the static root `index.html`.
- **`mark_applied.py`** — `--role-id … --profile … [--stage applied] [--notes …]` →
  adds/updates `applications.json` and flips the id to `applied` in `seen-roles.json`.
  Backs the CLAUDE.md `mark <role-id> applied [stage]` command.

Transient run files (`_run-urls.json` and any other scratch) are git-ignored.
