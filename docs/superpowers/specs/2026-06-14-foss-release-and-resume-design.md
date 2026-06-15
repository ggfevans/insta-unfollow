# insta-unfollow — FOSS release + resumable unfollower (design)

**Date:** 2026-06-14
**Status:** Approved (brainstorming) → ready for implementation plan

## Goal

Make the existing `insta-unfollow` working directory safe and presentable as a
public MIT-licensed FOSS project, and fix the unfollower script so it resumes
across runs instead of restarting from the top of the list every time.

## Background / current state

The directory is **not yet a git repository**. It contains two kinds of files:

**The tool (publishable):**
- `insta_unfollow.py` — offline, read-only, stdlib-only analyser. Reads an
  unzipped Instagram data export and writes a `candidates.csv` / `candidates.md`
  worksheet with a blank `decision` column. Already hardened against CSV-formula
  injection and markdown-injection.
- `test_insta_unfollow.py` — pytest suite for the analyser.
- `unfollow.js` — paste-into-browser-console assistant that clicks the real
  Following-list UI at a human pace, dry-run-first, with action-block detection.
- `diag.js` — console diagnostic helper for selector debugging.

**Personal data (must NEVER be published):**
- `to_unfollow.txt` (4,945 real handles), `unfollow_queue.js`,
  `candidates.csv`, `candidates.md`, `decisions.csv`, `review.csv`
- `connections/` — the full Instagram data export
- `.DS_Store`

## Scope

1. FOSS scaffolding: allowlist `.gitignore`, `LICENSE` (MIT), `README.md`,
   `DISCLAIMER.md`.
2. `unfollow.js`: add `localStorage`-backed resume so successive sessions march
   through the whole list. **(Primary code change.)**
3. `build_queue.py` + `test_build_queue.py`: generate `unfollow_queue.js` from
   the analyser's decisions, closing the manual gap in the workflow.

Out of scope: CI, CONTRIBUTING/CODE_OF_CONDUCT/SECURITY, issue templates
(deferred — "Standard" scope, not "Full"). Multi-account namespacing of resume
state (single key, documented caveat).

## Component designs

### 1. `.gitignore` — allowlist (safety-critical, create FIRST)

Ignore everything, then un-ignore only the tool + project docs. This *fails
safe*: any new personal-data file (a fresh `candidates.csv`, a new export) can
never be accidentally committed; shipping a new file requires an explicit
`git add -f` or a new allowlist line.

```gitignore
# Ship ONLY the tool. Personal data (your export, candidates, queues) stays local.
*
!.gitignore
!LICENSE
!README.md
!DISCLAIMER.md
!docs/
!docs/**
!insta_unfollow.py
!test_insta_unfollow.py
!build_queue.py
!test_build_queue.py
!unfollow.js
!unfollow_queue.example.js
!diag.js
```

**Hard ordering requirement:** `.gitignore` must exist *before* `git init` +
the first `git add`. Verify `git status` lists only the intended files before
the first commit.

### 2. `LICENSE` — MIT

Standard MIT text, `Copyright (c) 2026 Gareth Evans`.

### 3. `README.md` (brief)

Sections:
- One-line description + the **two-stage safety model** up front:
  (a) offline analyser = zero account risk; (b) opt-in console unfollower =
  ToS-restricted, your choice.
- Requirements: Python 3.9+, a desktop browser, your Instagram data export.
- **Workflow** (end-to-end, numbered): download & unzip export → run
  `insta_unfollow.py` → fill the `decision` column → `build_queue.py` →
  paste `unfollow_queue.js` then `unfollow.js` in the console → dry-run → live →
  re-run on later days (resume) until done.
- Repo layout (the shipped files).
- Resume + `CONFIG.reset` explained.
- Safety / Instagram ToS → link to `DISCLAIMER.md`.
- Running the tests (`python -m pytest`).
- Licence.

### 4. `DISCLAIMER.md`

Instagram-ToS reality, action-block / suspension risk, "start conservative,
ramp slowly", no-warranty (mirrors MIT), and the privacy guarantee: the analyser
is offline and your data never leaves your machine.

### 5. `unfollow.js` — resumable

Root cause of the current bug: progress lives in function-local `done`/`count`
(re-created on every paste), so each run re-walks from the top, re-counts the cap
from zero, and re-touches already-unfollowed rows that Instagram re-renders as
"Following" — burning the cap before reaching new accounts.

Fix — persist completed handles to `localStorage`:

```js
const STORE_KEY = "iu_unfollowed_v1";
function loadDone() {
  try { return new Set(JSON.parse(localStorage.getItem(STORE_KEY) || "[]")); }
  catch { console.warn("⚠ localStorage unavailable — progress won't persist"); return new Set(); }
}
function saveDone(set) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify([...set])); } catch {}
}
```

Behaviour:
- On start: `if (CONFIG.reset) localStorage.removeItem(STORE_KEY);` then
  `const done = loadDone();`
- Log resume stats: `resuming: N already done · M targets remaining · cap C`.
- Skip any target already in `done` **without clicking and without counting**
  toward the cap (free skip).
- On each *successful live* unfollow: `done.add(handle); saveDone(done); count++`.
- `count` (the cap) increments only on **new** unfollows → each session advances.
- **Dry run does NOT persist** (so testing can't poison real progress).
- Block-detection and pacing behaviour unchanged.
- `CONFIG.reset = false` added to the config block.

Caveat to document: state is keyed per `instagram.com` origin, so it is shared
across IG accounts in the same browser profile — use `CONFIG.reset` when
switching accounts.

### 6. `build_queue.py` + test

A ~30–40-line stdlib generator that closes the decisions→queue gap. Two input
modes:
- `--from-csv candidates.csv` (default): select rows whose `decision` cell,
  trimmed + casefolded, is in a marker set (default: `unfollow, u, yes, y, drop,
  x`). Configurable via `--markers`.
- `--from-list to_unfollow.txt`: one handle per line.

Output: `unfollow_queue.js` containing
`window.UNFOLLOW_TARGETS = <json array>;` — handles JSON-encoded
(`json.dumps`) so usernames are safely escaped. De-duplicate (casefold),
preserve first-seen order, warn on obviously malformed handles, print the count.

`test_build_queue.py` (pytest): fixtures for both modes assert the emitted file
selects unfollow-marked / listed handles, excludes kept ones, de-dupes, and that
the output parses as `window.UNFOLLOW_TARGETS = [...]` with the expected list.

A committed `unfollow_queue.example.js` (2–3 fake handles) shows the format
without shipping real data.

## Data flow

```
Instagram export (zip)
  └─ unzip → connections/...                 [local, git-ignored]
       └─ insta_unfollow.py → candidates.csv [local, git-ignored]
            └─ human fills `decision` column
                 └─ build_queue.py → unfollow_queue.js   [local, git-ignored]
                      └─ paste unfollow_queue.js + unfollow.js in console
                           └─ resumable sessions (localStorage) until done
```

Everything except the four/six shipped source files stays on disk, never
committed.

## Error handling / edge cases

- `build_queue.py`: missing input file → clear error + nonzero exit; empty
  selection → warn and exit nonzero (don't write an empty queue silently);
  malformed CSV → reuse the analyser's tolerant posture (skip + count).
- `unfollow.js`: `localStorage` blocked (private mode) → warn, continue in-memory
  for the session.
- First commit: abort if `git status` shows any personal-data path.

## Testing strategy

- Python: pytest for both `insta_unfollow.py` (existing) and `build_queue.py`
  (new). `python -m pytest` must pass before the first commit.
- `unfollow.js`: no automated harness (console script against a live, changing
  third-party DOM — a JSDOM mock would test the mock, not Instagram).
  Deliberate scope decision. Verified manually via the resume readout on the
  next live run; the resume logic is small and self-evident.

## Decisions (resolved during brainstorming)

- FOSS scope: **Standard**.
- Copyright holder: **Gareth Evans**.
- Resume mechanism: **localStorage**.
- Queue gap: **B — add `build_queue.py`**.
