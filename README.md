# ai-job-finder

An **agentic, Claude-Code-native job-search system** that you run by conversation.

There is no webapp, no server, and nothing to deploy. You open the repo in
[Claude Code](https://claude.com/claude-code) and **Claude itself is the engine**: it
reads the instruction files, runs the search with its own tools (web search, fetch),
applies your ranking rules with judgement, and writes **static files to disk**. Every
artefact it produces opens straight from disk (`file://`) — no runtime reads the
filesystem at view-time.

## What it is

A reusable kit for running highly targeted, repeatable job searches. The same engine
serves any number of independent searches; each search self-describes how it wants to
be ranked, filtered, and flagged. The system tracks what it has already seen across
runs, suppresses roles you've applied to, and produces a per-search dashboard plus a
root index — all as plain HTML on disk.

## How it works

**Engine vs userspace — the core separation:**

- **Engine (generic, this is the kit):**
  - [CLAUDE.md](CLAUDE.md) — orchestration: the mandatory first action, how a run
    proceeds, commands, precedence, boundaries.
  - [skill/SKILL.md](skill/SKILL.md) — the generic per-profile run procedure (read-set,
    ranking, query manifest, two-pass retrieval, diff/suppress, render, archive,
    self-audit) plus the file-format schemas.
  - [skill/lib/](skill/lib/) — the committed Python that does the deterministic work.
  - [skill/dashboard-template.html](skill/dashboard-template.html) — the dashboard
    canvas the agent fills per run.

- **Userspace (swappable data):** `profiles/*`. **Each subfolder of `profiles/` is one
  self-contained search, and the folder name *is* the search name.** There is no
  "person" concept anywhere in the system — all identity lives inside that profile's
  `PROFILE.md`. One person with two searches and two people with one search each are
  identical to the engine. A profile holds its objectives and ranking logic
  (`PROFILE.md`, authoritative), supporting evidence (`cv.md`, `experience.md`,
  `skills.md`), its query manifest and target orgs (`targets.md`), enumerated careers
  URLs (`urls.md`), and a `history/` ledger that persists across runs.

## The determinism / judgement split

Anything deterministic, repetitive, and judgement-free is done **once** in a committed
script and called every run — fixing the logic, costing almost no tokens, and failing
loudly instead of silently corrupting state. Everything requiring judgement (search,
ranking, deciding whether two listings are the same role, confirming a role off its
detail page) stays with the agent.

The scripts in [skill/lib/](skill/lib/) (stdlib-only Python, JSON in / JSON out):

| Script | Job |
| --- | --- |
| `normalise.py` | Single source of truth for URL/text normalisation; imported by the others so they can't drift. |
| `role_id.py` | Mints stable role-ids — `r-` + first 10 hex of `SHA1(org \| title \| url)`. |
| `merge_urls.py` | Dedups the careers URLs across selected profiles into one fetch list. |
| `diff_roles.py` | Diffs a run against the ledger into new / persisting / removed-candidate / applied-suppressed. |
| `write_runlog.py` | Validates and archives a per-run log under `history/runs/<date>/`. |
| `build_index.py` | Builds the static root `index.html` from each profile's dashboard + meta sidecar. |
| `mark_applied.py` | Records an application and flips the role to `applied` in the ledger. |

Per the engine rules, role-ids are minted **only** via `role_id.py` and the ledger diff
is performed **only** via `diff_roles.py` — never by hand.

## How to run

1. Open this repo in Claude Code (VS Code extension, desktop, or CLI).
2. Ask it to run a search. Its mandatory first action is to enumerate `profiles/` and
   present them as a numbered list, then **wait** for you to choose one, several, or
   all. It does not begin retrieval until you select.
3. For each selected profile it follows [skill/SKILL.md](skill/SKILL.md) and emits:
   - a static `dashboard.html` (+ a `dashboard-meta.json` sidecar) in that profile's
     folder, and
   - after all selected profiles finish, a static root `index.html`.
4. Open either file directly from disk (`file://`) — no server required.

**Mark an application:** `mark <role-id> applied [stage]` records it in that profile's
`applications.json` and suppresses the role from future new-leads.

## Requirements

- Claude Code (e.g. with a Claude Max subscription).
- Python 3, standard library only — no third-party packages, no virtualenv.

## Setting up a new search

Create `profiles/<your-search-name>/` with at least a `PROFILE.md` (the authoritative
spine: objectives, ranking logic, income floor/target, geography, constraints) and a
`targets.md` (query manifest + target orgs). Add `urls.md`, `cv.md`, `experience.md`,
and `skills.md` as needed. The file-format schemas are documented in
[skill/SKILL.md](skill/SKILL.md). The `history/` ledger is created for you on first run.

A worked `examples/` profile is **forthcoming** — it does not exist in the repo yet.
Until then, use the schemas in `SKILL.md` as your template.

## Privacy model

`profiles/` is **real, private search data and is never committed.** It is protected
two ways:

1. **`.gitignore`** ignores `profiles/*` wholesale, allowing only `profiles/.gitkeep`
   (so the empty folder ships, but no content can).
2. **A shared pre-commit hook** in [.githooks/](.githooks/), wired in via
   `core.hooksPath`, **rejects any staged path under `profiles/`** other than
   `.gitkeep`. Because it's tracked in the repo, it protects every clone — not just the
   original author's machine.

To enable the hook after cloning:

```sh
git config core.hooksPath .githooks
```

**Never commit real profile data.**

## Web access (optional, local)

A search run makes many web calls. To avoid a permission prompt on every one, the repo
ships an **opt-in, allowlist-based** approval hook at
[.claude/hooks/web-approve.py](.claude/hooks/web-approve.py). It is **inert until you
wire it in locally** — cloning the repo changes nothing about your web access and adds
no risk.

What it does when enabled: it auto-approves **WebSearch** (read-only — snippets only, no
channel to send your data out), and auto-approves **WebFetch only for hosts on your local
allowlist** (exact host or a dot-boundary subdomain — `greenhouse.io` matches
`boards.greenhouse.io` but not `evil-greenhouse.io`). Every other fetch still prompts. It
**never blocks** anything and **fails safe**: on any error, a missing allowlist, or an
unparseable URL it passes through to the normal prompt — it never approves on uncertainty.

It's allowlist-based rather than blanket on purpose: a fetch to an attacker-chosen domain
is the realistic way profile data could leak (e.g. via prompt injection), and that case is
exactly the one kept behind a prompt.

To enable (entirely local, gitignored):

1. Copy **tier (a)** from
   [.claude/settings.local.json.example](.claude/settings.local.json.example) into
   `.claude/settings.local.json`.
2. Create `.claude/web-allowlist.txt` with one host per line (e.g. `charityjob.co.uk`,
   `greenhouse.io`).

The `.example` also documents a blanket **tier (b)** (auto-approve all fetches) with its
honest tradeoff — more convenient, but it removes the one stop that catches exfiltration,
so it's weaker for any profile holding sensitive data. Tier (a) is the default.

## Current status / limitations

This is an early public release of a working engine. Honest state:

- ✅ Engine orchestration (`CLAUDE.md`), the run procedure (`SKILL.md`), and all
  `skill/lib/` scripts are in place and functional.
- ✅ Privacy ringfence (gitignore + tracked pre-commit hook) is in place.
- 🚧 The dashboard template (`skill/dashboard-template.html`) still needs cleanup; the
  run procedure deliberately renders against it as-is for now.
- 🚧 The `urls.md` numbered-manifest format is specified but its full population /
  manifest work is pending.
- ✅ An optional, local, allowlist-based web-access hook ships (see "Web access");
  it's inert until opted in.
- 🚧 An `examples/` profile for new users is not yet built.

Treat the schemas and procedure as the stable contract; expect the template and the
manifest/allowlist tooling to evolve.

## License

[MIT](LICENSE) © 2026 Joel Marks.
