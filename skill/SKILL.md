---
name: job-search-run
description: The generic per-profile job-search run procedure for this engine. Followed once per selected profile. Deterministic bookkeeping is delegated to skill/lib/*; judgement stays with the agent.
manifest_version: 1.0.0
---

# SKILL.md — the generic run procedure

This is the engine's run procedure, followed **once per selected profile**. It is
generic: nothing here hardcodes a particular profile's ranking, income, or geography.
Each profile self-describes those in its own files.

`manifest_version` (frontmatter, currently `1.0.0`) versions this procedure and the
query-manifest contract. **Query ids are stable across versions, and a retired query
id is never reused.** Bump `manifest_version` when the contract changes; record the
version in every `run-log.json` and on every dashboard.

> Prerequisite (from CLAUDE.md): the user has already been shown the numbered list of
> `profiles/` and has selected which to run. Do not start retrieval before that.

## The determinism split (why skill/lib/ exists)
Anything deterministic, repetitive, and judgement-free is done **once** in a committed
script and called every run — it fixes the logic, costs almost no tokens, and fails
loudly instead of silently corrupting state. Anything needing judgement stays with
you. The scripts are **required steps, not optional tools**:
- **role-ids are minted ONLY by `role_id.py`** — never compute a hash by hand.
- **the ledger diff is performed ONLY by `diff_roles.py`** — never diff by hand.

---

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
- **Single profile:** fetch **every** careers URL in its `urls.md`.
- **Multiple selected profiles:** run `merge_urls.py` over the selected names; it
  writes `_run-urls.json` at repo root (deduped, normalised, with `requested_by`).
  Fetch each **unique** URL **once**, then attribute results back to the profiles that
  requested it.
- An empty or missing `urls.md` contributes nothing — `merge_urls.py` logs it; carry
  on.

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
- **new** — ids absent from `seen-roles.json`;
- **persisting** — ids in both (it bumps `last_seen`, `runs_seen`, merges provenance);
- **removed-candidates** — ledger ids with status `live` that are **absent this run**.
  The script only **flags** these; deciding to transition one to `closed` is **your**
  call after verification.
- **applied-suppressed** — this run's ids that are present in `applications.json`.

**Suppression rule:** any id in `applications.json` is **pulled out of the new-leads
tiers** into an **"In flight"** section showing its stage. It is **never** re-surfaced
as new and **never** counted as new.

> Note the coupling: `mark_applied.py` flips a ledger id's status to `applied`, and
> `diff_roles.py` only flags `live` ids as removed-candidates — so an applied role
> that drops out of a run is correctly *not* mis-flagged as removed. Always mark
> applications via the command, not by editing JSON.

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
- **what could not be confirmed** (e.g. salary/closing-date not found on the detail
  page) — honesty about gaps is part of the contract.

---

## SCHEMAS (the contract for all files)

### `urls.md` — a YAML list of records
One record per employer careers page. (Populated in the cleanup sprint; the parser in
`merge_urls.py` targets this shape — a block sequence of flat mappings, optionally
inside a ```yaml fence.)
```yaml
- org: Example Trust
  careers_url: https://example.org/careers
  fetch_method: fetch        # fetch | browse | search
  sector_tag: charity
  priority: 1                # 1–3
  last_checked: 2026-06-01
  notes: ATS is Greenhouse; list view fetches cleanly
```

### `seen-roles.json` — the role ledger
Object keyed by `role_id`:
```json
{
  "r-077711524e": {
    "org": "Example Trust",
    "title": "Change Communications Lead",
    "url": "https://example.org/jobs/1",
    "first_seen": "2026-06-27",
    "last_seen": "2026-06-27",
    "runs_seen": 1,
    "status": "live",            // live | closed | removed | excluded | applied
    "provenance": ["CharityJob", "Reed"]
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
```json
{
  "manifest_version": "1.0.0",
  "run_date": "2026-06-27",
  "profile": "joel-rapid-bridging-work",
  "queries_run": ["Q01", "Q02", "Q03"],
  "queries_null": ["Q02"],
  "fetch_failures": ["https://blocked.example/jobs"],
  "sources_hit": [{"name": "CharityJob", "count": 6}, {"name": "Reed", "count": 3}],
  "counts": {"new": 4, "persisting": 2, "removed": 1, "applied_suppressed": 1}
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
- **`merge_urls.py`** — `<profile> [<profile> …]` → reads each `urls.md`, extracts and
  normalises every `careers_url`, dedups, writes `_run-urls.json` at repo root as
  `[{url, fetch_method, requested_by:[…], orgs:[…]}]`. Overwrites each run; handles
  empty/missing `urls.md` gracefully.
- **`diff_roles.py`** — `--roles run.json --seen … --applications … [--run-date …]` →
  updates `seen-roles.json` in place and prints the
  `{new, persisting, removed_candidates, applied_suppressed}` partition. Pure set
  logic; never closes a role.
- **`write_runlog.py`** — `--in runlog.json` → validates against the run-log schema and
  writes `profiles/<profile>/history/runs/<run_date>/run-log.json`. Fails loudly on a
  schema violation.
- **`build_index.py`** → scans `profiles/*/` for `dashboard.html` + `dashboard-meta.json`
  and writes the static root `index.html`.
- **`mark_applied.py`** — `--role-id … --profile … [--stage applied] [--notes …]` →
  adds/updates `applications.json` and flips the id to `applied` in `seen-roles.json`.
  Backs the CLAUDE.md `mark <role-id> applied [stage]` command.

Transient run files (`_run-urls.json` and any other scratch) are git-ignored.
