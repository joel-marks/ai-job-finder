# CLAUDE.md — engine orchestration

## What this is
This repo is an **agentic job-search system**. You, Claude Code, **are the engine**:
there is no server, no web service, no application to build or run. You read the
instruction files, run the search with your own tools, and write **static files to
disk**. Every artefact must open directly from disk (`file://`) — never depend on a
runtime that reads the filesystem at view-time.

## Engine vs userspace (the core separation)
- **Engine (generic, this is the kit):** `CLAUDE.md` (this file) + `skill/` (the run
  procedure in `skill/SKILL.md`, the reusable scripts in `skill/lib/`, and
  `skill/dashboard-template.html`).
- **Userspace (data):** `profiles/*`. Each subfolder of `profiles/` is **one
  self-contained search**, and the folder name **is** the search name. There is no
  "person" concept anywhere — all identity lives in that profile's `PROFILE.md`. One
  person with two profiles and two people with one profile each are identical to the
  system.

The engine is generic. It never hardcodes one profile's ranking, income, or geography
— each profile self-describes how it wants to be ranked and flagged.

## MANDATORY first action on any run
Before searching anything:
1. Enumerate the subfolders of `profiles/` by running
   `python3 skill/lib/validate_profile.py` (no args). It returns, for every
   subfolder, `{profile, valid, reason}`.
2. Present them to the user as a **numbered list** — these are the searches —
   annotating each **runnable** or **not-runnable: <reason>**. An empty folder, or
   one lacking a non-empty `PROFILE.md`, still appears but is clearly flagged
   (users may create empty folders; this must not break enumeration).
3. Ask which to run: one, several, or all.
4. **Wait for the selection.** Never assume. Do not begin retrieval until the user
   has chosen.

If **no** subfolder is runnable (e.g. a fresh clone), say so plainly and tell the
user to add a search at `profiles/<name>/` with a non-empty `PROFILE.md` (the search
spine), pointing to the README and the forthcoming `examples/` starter profile. Do
not invent `examples/` if it does not yet exist.

## How a run proceeds
Follow `skill/SKILL.md` — the generic run procedure — once per selected profile. All
procedure detail lives there; this file does not duplicate it. Each selected
profile's own files (`PROFILE.md` and its supporting evidence) supply the data.

`skill/lib/` scripts are **required steps, not optional tools**. In particular:
- role-ids are computed **only** via `skill/lib/role_id.py`, never by hand;
- the ledger diff is performed **only** via `skill/lib/diff_roles.py`, never by hand.
Your value is judgement; arithmetic and bookkeeping are the scripts' job.

## Commands
- **Mark applied:** `mark <role-id> applied [stage]` — runs
  `skill/lib/mark_applied.py` against the relevant profile: records the application
  in that profile's `applications.json` and flips the id's status to `applied` in its
  `seen-roles.json`, so the role is pulled from new-leads and never re-surfaced.
- **Mark closed:** `mark <role-id> closed [reason]` — runs
  `skill/lib/mark_closed.py` against the relevant profile: sets the id's status to
  `closed` in its `seen-roles.json` (the manual / agent-confirmed close override).
  Use when a role is known gone before the deterministic N-absent-runs threshold in
  `diff_roles.py` catches it. Never edit `seen-roles.json` by hand.

## Precedence
The user's **latest instruction in the session overrides the files.** Where a file
and a live instruction conflict, follow the instruction and say so.

## Boundaries
The system emits **static files only** — no server, no runtime directory reading. Do
not add client-side scripts that read the filesystem at view-time. Every dashboard and
index must work opened straight from disk.
