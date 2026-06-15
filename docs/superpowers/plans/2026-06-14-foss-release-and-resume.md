# insta-unfollow FOSS Release + Resumable Unfollower — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the `insta-unfollow` working directory into a safe, public, MIT-licensed FOSS project and fix `unfollow.js` so it resumes across sessions instead of restarting at the top of the list.

**Architecture:** A safety-critical allowlist `.gitignore` is created and `git init` run *before* anything is staged, guaranteeing personal data (4,945 real handles, the Instagram export, generated CSVs) can never be committed. The two-stage tool keeps its shape: an offline read-only Python analyser and an opt-in browser-console unfollower. The unfollower gains `localStorage`-backed resume; a new `build_queue.py` closes the decisions→queue gap with a pytest suite.

**Tech Stack:** Python 3.9+ (standard library only), pytest (dev), vanilla browser JavaScript (console script), git.

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `.gitignore` | Create | Allowlist — ship only the tool, ignore all personal data |
| `LICENSE` | Create | MIT licence text |
| `README.md` | Create | What/why, requirements, end-to-end workflow, layout, tests |
| `DISCLAIMER.md` | Create | Instagram-ToS / account-risk / no-warranty / privacy |
| `build_queue.py` | Create | Decisions (`candidates.csv`) or handle list → `unfollow_queue.js` |
| `test_build_queue.py` | Create | pytest suite for `build_queue.py` |
| `unfollow_queue.example.js` | Create | Example target-list format (fake handles) |
| `unfollow.js` | Modify | Add `localStorage` resume; dry-run never persists |
| `insta_unfollow.py` | Ship as-is | Existing offline analyser |
| `test_insta_unfollow.py` | Ship as-is | Existing analyser tests |
| `diag.js` | Ship as-is | Existing console diagnostic |

---

## Task 1: Safety-critical scaffolding — allowlist `.gitignore` + `git init`

**This task MUST run first.** It guarantees no personal data can ever be staged.

**Files:**
- Create: `/Users/gvns/code/projects/insta-unfollow/.gitignore`

- [ ] **Step 1: Create the allowlist `.gitignore`**

```gitignore
# Ship ONLY the tool. Personal data (your export, candidates, queues) stays local.
# Allowlist style: ignore everything, then re-include the files that make up the tool.
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

- [ ] **Step 2: Initialise the repository**

Run:
```bash
cd /Users/gvns/code/projects/insta-unfollow && git init -b main
```
Expected: `Initialized empty Git repository ...`

- [ ] **Step 3: Verify personal data is ignored and only the tool is visible**

Run:
```bash
git check-ignore -v to_unfollow.txt connections candidates.csv candidates.md decisions.csv review.csv unfollow_queue.js .DS_Store
```
Expected: every one of those paths is printed (i.e. matched by `.gitignore` `*`).

Run:
```bash
git check-ignore unfollow_queue.example.js insta_unfollow.py unfollow.js diag.js build_queue.py README.md LICENSE; echo "exit=$?"
```
Expected: **no output**, `exit=1` (none of the tool files are ignored).

Run:
```bash
git status --short
```
Expected: the listed untracked files are ONLY `.gitignore`, `insta_unfollow.py`, `test_insta_unfollow.py`, `unfollow.js`, `diag.js`, and `docs/` (the spec/plan). **If any personal-data path (`to_unfollow.txt`, `connections/`, `candidates.csv`, `decisions.csv`, `review.csv`, `unfollow_queue.js`) appears, STOP — do not commit.**

- [ ] **Step 4: Commit the baseline**

```bash
git add .gitignore insta_unfollow.py test_insta_unfollow.py unfollow.js diag.js docs/
git commit -m "chore: add allowlist .gitignore and import existing tool

Allowlist gitignore ships only the tool files; the Instagram export and all
generated personal data stay local and can never be staged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
Expected: a commit is created listing those files only.

---

## Task 2: MIT `LICENSE`

**Files:**
- Create: `/Users/gvns/code/projects/insta-unfollow/LICENSE`

- [ ] **Step 1: Write the licence**

```
MIT License

Copyright (c) 2026 Gareth Evans

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Commit**

```bash
git add LICENSE
git commit -m "docs: add MIT licence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `build_queue.py` — decisions → queue generator (TDD)

**Files:**
- Create: `/Users/gvns/code/projects/insta-unfollow/build_queue.py`
- Test: `/Users/gvns/code/projects/insta-unfollow/test_build_queue.py`

- [ ] **Step 1: Write the failing tests**

Create `test_build_queue.py`:

```python
import json

import build_queue
from build_queue import (
    DEFAULT_MARKERS,
    dedupe,
    main,
    render_queue_js,
    select_from_csv,
    select_from_list,
)


def test_select_from_csv_picks_only_unfollow_marked():
    rows = [
        {"username": "alice", "decision": "unfollow"},
        {"username": "bob", "decision": ""},
        {"username": "carol", "decision": "keep"},
        {"username": "dave", "decision": "U"},   # case-insensitive marker
    ]
    assert list(select_from_csv(rows, DEFAULT_MARKERS)) == ["alice", "dave"]


def test_select_from_list_ignores_blanks_and_comments():
    lines = ["alice\n", "\n", "# a comment\n", "  bob  \n"]
    assert list(select_from_list(lines)) == ["alice", "bob"]


def test_dedupe_casefold_preserves_first_seen_order():
    assert dedupe(["Alice", "bob", "ALICE", "carol"]) == ["Alice", "bob", "carol"]


def test_render_queue_js_round_trips():
    js = render_queue_js(["alice", "bob"])
    line = next(l for l in js.splitlines() if l.startswith("window.UNFOLLOW_TARGETS"))
    payload = line[len("window.UNFOLLOW_TARGETS = "):].rstrip(";")
    assert json.loads(payload) == ["alice", "bob"]


def test_render_queue_js_escapes_handles_safely():
    # A pathological handle must be JSON-escaped, never break the JS string.
    js = render_queue_js(['a"; alert(1)//'])
    line = next(l for l in js.splitlines() if l.startswith("window.UNFOLLOW_TARGETS"))
    payload = line[len("window.UNFOLLOW_TARGETS = "):].rstrip(";")
    assert json.loads(payload) == ['a"; alert(1)//']


def test_main_from_csv_writes_queue(tmp_path):
    csv_path = tmp_path / "candidates.csv"
    csv_path.write_text("username,decision\nalice,unfollow\nbob,keep\n", encoding="utf-8")
    out_path = tmp_path / "unfollow_queue.js"
    rc = main(["--from-csv", str(csv_path), "--out", str(out_path)])
    assert rc == 0
    content = out_path.read_text(encoding="utf-8")
    assert "alice" in content and "bob" not in content


def test_main_from_list_writes_queue(tmp_path):
    list_path = tmp_path / "to_unfollow.txt"
    list_path.write_text("alice\nbob\nAlice\n", encoding="utf-8")
    out_path = tmp_path / "unfollow_queue.js"
    rc = main(["--from-list", str(list_path), "--out", str(out_path)])
    assert rc == 0
    line = next(
        l for l in out_path.read_text(encoding="utf-8").splitlines()
        if l.startswith("window.UNFOLLOW_TARGETS")
    )
    payload = line[len("window.UNFOLLOW_TARGETS = "):].rstrip(";")
    assert json.loads(payload) == ["alice", "bob"]


def test_main_empty_selection_errors_and_writes_nothing(tmp_path):
    csv_path = tmp_path / "candidates.csv"
    csv_path.write_text("username,decision\nbob,keep\n", encoding="utf-8")
    out_path = tmp_path / "unfollow_queue.js"
    rc = main(["--from-csv", str(csv_path), "--out", str(out_path)])
    assert rc == 2
    assert not out_path.exists()


def test_main_missing_input_errors(tmp_path):
    rc = main(["--from-csv", str(tmp_path / "nope.csv"), "--out", str(tmp_path / "q.js")])
    assert rc == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/gvns/code/projects/insta-unfollow && python -m pytest test_build_queue.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_queue'` (or ImportError on the names).

- [ ] **Step 3: Implement `build_queue.py`**

Create `build_queue.py`:

```python
#!/usr/bin/env python3
"""build_queue.py — turn unfollow decisions into unfollow_queue.js.

Reads either the analyser's candidates.csv (selecting rows whose `decision`
cell marks an unfollow) or a plain newline-delimited handle list, and writes
unfollow_queue.js defining `window.UNFOLLOW_TARGETS` for unfollow.js to load.

Strictly local: no network, standard library only. Python 3.9+.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys

DEFAULT_MARKERS = ("unfollow", "u", "yes", "y", "drop", "x")

# Instagram handles are letters, digits, periods and underscores.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]+$")


def select_from_csv(rows, markers):
    """Yield usernames from candidates.csv rows whose decision is a marker."""
    marker_set = {m.strip().casefold() for m in markers}
    for row in rows:
        decision = (row.get("decision") or "").strip().casefold()
        username = (row.get("username") or "").strip()
        if username and decision in marker_set:
            yield username


def select_from_list(lines):
    """Yield handles from a newline-delimited list (skips blanks and # comments)."""
    for line in lines:
        handle = line.strip()
        if handle and not handle.startswith("#"):
            yield handle


def dedupe(handles):
    """De-duplicate case-insensitively, preserving first-seen order."""
    seen = set()
    result = []
    for handle in handles:
        key = handle.casefold()
        if key not in seen:
            seen.add(key)
            result.append(handle)
    return result


def render_queue_js(handles):
    """Render the unfollow_queue.js file content (handles JSON-escaped)."""
    return (
        "// Paste this FIRST. Loads the unfollow target list.\n"
        "// Generated by build_queue.py — do not edit by hand.\n"
        "window.UNFOLLOW_TARGETS = {};\n".format(json.dumps(handles))
    )


def _read_csv_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.readlines()


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Generate unfollow_queue.js from your unfollow decisions.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--from-csv",
        metavar="PATH",
        help="candidates.csv with a filled `decision` column (default: candidates.csv).",
    )
    source.add_argument(
        "--from-list",
        metavar="PATH",
        help="Plain newline-delimited handle list (one username per line).",
    )
    parser.add_argument(
        "--out",
        default="unfollow_queue.js",
        help="Output path (default: unfollow_queue.js).",
    )
    parser.add_argument(
        "--markers",
        default=",".join(DEFAULT_MARKERS),
        help="Comma-separated decision values that mean 'unfollow' "
        "(default: {}).".format(",".join(DEFAULT_MARKERS)),
    )
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    markers = [m for m in args.markers.split(",") if m.strip()]

    try:
        if args.from_list:
            handles = list(select_from_list(_read_lines(args.from_list)))
        else:
            csv_path = args.from_csv or "candidates.csv"
            handles = list(select_from_csv(_read_csv_rows(csv_path), markers))
    except OSError as exc:
        print("ERROR: cannot read input: {}".format(exc), file=sys.stderr)
        return 2

    handles = dedupe(handles)

    for handle in handles:
        if not _HANDLE_RE.match(handle):
            print("WARNING: unusual handle kept as-is: {!r}".format(handle), file=sys.stderr)

    if not handles:
        print(
            "ERROR: no unfollow targets selected — nothing written. "
            "Did you fill the `decision` column (e.g. 'unfollow')?",
            file=sys.stderr,
        )
        return 2

    try:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(render_queue_js(handles))
    except OSError as exc:
        print("ERROR: cannot write {}: {}".format(args.out, exc), file=sys.stderr)
        return 2

    print("Wrote {} ({} targets).".format(args.out, len(handles)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/gvns/code/projects/insta-unfollow && python -m pytest test_build_queue.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add build_queue.py test_build_queue.py
git commit -m "feat: add build_queue.py to generate unfollow_queue.js from decisions

Reads the analyser's candidates.csv (decision column) or a plain handle list;
emits window.UNFOLLOW_TARGETS with JSON-escaped handles. Closes the manual gap
between deciding and running the console unfollower.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `unfollow_queue.example.js`

**Files:**
- Create: `/Users/gvns/code/projects/insta-unfollow/unfollow_queue.example.js`

- [ ] **Step 1: Write the example queue**

```javascript
// Paste this FIRST. Loads the unfollow target list.
// This is an EXAMPLE showing the format only. Generate your real list with:
//   python build_queue.py --from-csv candidates.csv
window.UNFOLLOW_TARGETS = ["example_handle_one", "example_handle_two", "example_handle_three"];
```

- [ ] **Step 2: Commit**

```bash
git add unfollow_queue.example.js
git commit -m "docs: add example unfollow_queue format

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `unfollow.js` — `localStorage`-backed resume

This fixes the bug: progress lived in function-local `done`/`count`, re-created
on every paste, so each run re-walked from the top, re-counted the cap from zero,
and re-touched already-unfollowed rows Instagram re-renders as "Following" —
burning the cap before reaching new accounts.

**Files:**
- Modify: `/Users/gvns/code/projects/insta-unfollow/unfollow.js`

- [ ] **Step 1: Add `reset` to the CONFIG block**

Replace:
```javascript
    scrollPauseMs: 1800,
    dryRun: false,     // LIVE — this will actually unfollow. Set true to re-test.
  };
```
With:
```javascript
    scrollPauseMs: 1800,
    dryRun: false,     // LIVE — this will actually unfollow. Set true to re-test.
    reset: false,      // set true for ONE run to wipe saved progress and start over.
  };
```

- [ ] **Step 2: Add the resume readout (load progress from localStorage)**

Replace:
```javascript
  console.log(`▶ ${targets.size} targets loaded. dryRun=${CONFIG.dryRun}, cap=${CONFIG.cap}`);
```
With:
```javascript
  // ---- Resume across runs: completed handles persist in localStorage ----
  const STORE_KEY = "iu_unfollowed_v1";
  const loadDone = () => {
    try {
      return new Set(JSON.parse(localStorage.getItem(STORE_KEY) || "[]"));
    } catch {
      console.warn("⚠ localStorage unavailable — progress won't persist this run.");
      return new Set();
    }
  };
  const saveDone = (set) => {
    try { localStorage.setItem(STORE_KEY, JSON.stringify([...set])); } catch {}
  };
  if (CONFIG.reset) {
    try { localStorage.removeItem(STORE_KEY); } catch {}
    console.log("↺ Stored progress cleared (CONFIG.reset). Set it back to false next run.");
  }
  const done = loadDone(); // handles already unfollowed in previous sessions
  const remaining = [...targets].filter((t) => !done.has(t)).length;
  console.log(
    `▶ ${targets.size} targets · ${done.size} done · ${remaining} remaining · ` +
      `dryRun=${CONFIG.dryRun} · cap=${CONFIG.cap}`
  );
```

- [ ] **Step 3: Replace the old per-run state declaration**

Replace:
```javascript
  const done = new Set();
  let count = 0;
```
With:
```javascript
  const attempted = new Set(); // guards re-processing within THIS run (incl. dry run)
  let count = 0;
```

- [ ] **Step 4: Make the row loop resume-aware and persist only real unfollows**

Replace:
```javascript
    for (const btn of rowButtons) {
      if (count >= CONFIG.cap) return "cap";
      const handle = handleForButton(btn);
      if (!handle || done.has(handle) || !targets.has(handle)) continue;

      done.add(handle);
      if (CONFIG.dryRun) {
        count++;
        console.log(`[dry] #${count} would unfollow @${handle}`);
        continue;
      }

      btn.scrollIntoView({ block: "center" });
      btn.click();
      await sleep(rand(700, 1400)); // wait for confirm sheet

      const confirm = findButtonByText(document, "unfollow");
      if (!confirm) {
        console.warn(`⚠ no confirm dialog for @${handle} — skipped`);
        continue;
      }
      confirm.click();
      count++;
      console.log(`✓ #${count} unfollowed @${handle}`);
```
With:
```javascript
    for (const btn of rowButtons) {
      if (count >= CONFIG.cap) return "cap";
      const handle = handleForButton(btn);
      // Skip non-targets, anything done in a previous run (free skip — no click,
      // no cap cost), and anything already handled this run.
      if (!handle || !targets.has(handle) || done.has(handle) || attempted.has(handle)) continue;
      attempted.add(handle);

      if (CONFIG.dryRun) {
        count++;
        console.log(`[dry] #${count} would unfollow @${handle}`);
        continue; // dry run never persists — it must not poison real progress
      }

      btn.scrollIntoView({ block: "center" });
      btn.click();
      await sleep(rand(700, 1400)); // wait for confirm sheet

      const confirm = findButtonByText(document, "unfollow");
      if (!confirm) {
        console.warn(`⚠ no confirm dialog for @${handle} — skipped`);
        continue;
      }
      confirm.click();
      done.add(handle);
      saveDone(done); // persist only real unfollows, immediately
      count++;
      console.log(`✓ #${count} unfollowed @${handle}`);
```

- [ ] **Step 5: Update the header usage comment to mention resume**

Replace:
```javascript
 *   6. It runs in DRY RUN first — it only LOGS who it would unfollow. Verify the
 *      handles look right. Then set  CONFIG.dryRun = false  (edit below) and
 *      paste again to actually unfollow.
```
With:
```javascript
 *   6. It runs in DRY RUN first — it only LOGS who it would unfollow. Verify the
 *      handles look right. Then set  CONFIG.dryRun = false  (edit below) and
 *      paste again to actually unfollow.
 *   7. RESUME: progress is saved in your browser (localStorage). Re-paste both
 *      files on later days and it skips everyone already unfollowed, advancing
 *      ~one cap deeper each session. Set CONFIG.reset = true for one run to
 *      wipe saved progress and start over.
```

- [ ] **Step 6: Syntax-check the edited script**

Run: `cd /Users/gvns/code/projects/insta-unfollow && node --check unfollow.js`
Expected: no output, exit 0 (valid syntax). If `node` is unavailable, skip and rely on Step 7.

- [ ] **Step 7: Manual behaviour verification (live session)**

The user has Instagram open. Ask them to:
1. Re-paste `unfollow_queue.js` then `unfollow.js`.
2. Confirm the new readout prints, e.g. `▶ 4945 targets · 82 done · 4863 remaining · ...` — the **done** count reflects prior unfollows (or 0 on a clean browser).
3. After a session, re-paste and confirm **done** has grown and the script skips the earlier ones rather than restarting at the top.

Record the observed readout as the verification evidence.

- [ ] **Step 8: Commit**

```bash
git add unfollow.js
git commit -m "fix: resume unfollow.js across runs via localStorage

Progress was function-local and reset on every paste, so each run restarted at
the top, re-counted the cap, and re-touched already-unfollowed rows — never
reaching the tail of a long list. Completed handles now persist in localStorage
and are skipped for free; the cap counts only new unfollows; dry runs never
persist; CONFIG.reset wipes progress.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `README.md`

**Files:**
- Create: `/Users/gvns/code/projects/insta-unfollow/README.md`

- [ ] **Step 1: Write the README**

````markdown
# insta-unfollow

Offline tooling to find — and then actually unfollow — the Instagram accounts
you no longer want to follow, **without handing your password to any third-party
service**.

It works in two clearly separated stages, and that separation *is* the safety
model:

1. **Offline analyser (`insta_unfollow.py`)** — read-only, no network, no login,
   standard-library Python. Reads your *already-downloaded* Instagram data export
   and builds a worksheet of unfollow candidates. **Zero account risk.**
2. **Opt-in console unfollower (`unfollow.js`)** — a script you paste into your
   own browser's developer console. It clicks the real "Following → Unfollow"
   buttons at a human pace, dry-runs first, stops the instant Instagram shows an
   action-block, and **resumes across sessions** so you can work through a long
   list over several days. Automating actions is against Instagram's Terms of
   Service — see [DISCLAIMER.md](DISCLAIMER.md). Using it is your choice.

## Requirements

- Python 3.9+ (standard library only — nothing to install to *run* it)
- A desktop browser logged into Instagram (Chrome, Firefox, or Edge)
- Your Instagram data export: Instagram → *Settings* → *Your activity* →
  *Download your information* (choose **JSON** if offered)

## Workflow

1. **Download & unzip your export** so that
   `connections/followers_and_following/following.json` sits inside this folder.
   (HTML exports also work.)
2. **Build the candidate worksheet:**
   ```bash
   python insta_unfollow.py .
   ```
   Writes `candidates.csv` and `candidates.md` — one row per account you follow,
   flagged mutual / non-mutual, oldest-follow first. Nothing is judged for you;
   the `decision` column is intentionally blank.
3. **Decide.** In `candidates.csv`, put `unfollow` (or `u`) in the `decision`
   column for every account you want to drop. Leave the rest blank.
4. **Generate the queue:**
   ```bash
   python build_queue.py --from-csv candidates.csv
   ```
   Writes `unfollow_queue.js` with your target list. (You can also feed a plain
   handle list: `python build_queue.py --from-list to_unfollow.txt`.)
5. **Unfollow, in your browser:**
   - Open `https://www.instagram.com/`, go to **your** profile, and click your
     **Following** count to open the list dialog.
   - Open DevTools → Console (Cmd+Opt+J / Ctrl+Shift+J).
   - Paste the contents of `unfollow_queue.js`, press Enter.
   - Paste the contents of `unfollow.js`, press Enter.
   - It **dry-runs by default** — it only logs who it *would* unfollow. Verify
     the handles, then set `CONFIG.dryRun = false` and paste `unfollow.js` again
     to do it for real.
6. **Resume on later days.** Re-paste both files any time. Already-unfollowed
   accounts are skipped for free (tracked in your browser's `localStorage`), and
   each session only counts *new* unfollows toward the cap — so you steadily work
   through the whole list instead of restarting at the top. To start over, set
   `CONFIG.reset = true` for one run.

## Pacing & safety

`unfollow.js` defaults to a conservative per-session cap with randomised,
human-speed delays, and it **stops immediately** if Instagram shows an
action-block. Start small, ramp up over days only if you see no blocks, and read
[DISCLAIMER.md](DISCLAIMER.md) before the live run.

If the console logs "0 rows matched", Instagram has probably changed its markup —
paste `diag.js` to dump what the script currently sees.

## Repo layout

| File | What it is |
|------|------------|
| `insta_unfollow.py` | Offline, read-only export analyser → `candidates.csv` / `.md` |
| `build_queue.py` | Turns your decisions into `unfollow_queue.js` |
| `unfollow.js` | Browser-console unfollower (dry-run-first, resumable) |
| `diag.js` | Console diagnostic for selector debugging |
| `unfollow_queue.example.js` | Example target-list format (fake handles) |
| `test_*.py` | Test suites |

Your personal data — the export, `candidates.csv`, `unfollow_queue.js`, etc. — is
git-ignored and never leaves your machine.

## Tests

```bash
pip install pytest
python -m pytest -q
```

## Licence

MIT — see [LICENSE](LICENSE).
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with two-stage safety model and full workflow

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: `DISCLAIMER.md`

**Files:**
- Create: `/Users/gvns/code/projects/insta-unfollow/DISCLAIMER.md`

- [ ] **Step 1: Write the disclaimer**

```markdown
# Disclaimer

**Use `unfollow.js` at your own risk.**

`insta-unfollow` is an independent, unofficial tool. It is not affiliated with,
endorsed by, or connected to Instagram or Meta Platforms, Inc.

## The offline analyser is safe

`insta_unfollow.py` and `build_queue.py` are **offline and read-only**. They make
no network calls, use no Instagram API, require no login or password, and only
read a data export you downloaded yourself. Your data never leaves your computer.

## The console unfollower carries real risk

`unfollow.js` automates actions inside your logged-in session. **Automating
interactions violates Instagram's Terms of Service** and can result in:

- temporary action-blocks (hours to days where you can't follow/unfollow),
- longer feature restrictions, or
- in the worst case, account suspension.

The script tries to reduce that risk — it acts at a randomised, human-like pace,
caps how much it does per session, and halts the moment it detects an
action-block — but **no precaution can guarantee your account's safety.**

If you choose to use it:

- Start with a small cap and only ramp up over days if you see no blocks.
- Run the dry run first and confirm the targets are correct.
- Stop if you get any block and wait 24–48 hours before trying again.

## No warranty

This software is provided "as is", without warranty of any kind. The authors are
not liable for any consequence of its use, including any action taken against your
Instagram account. See [LICENSE](LICENSE).
```

- [ ] **Step 2: Commit**

```bash
git add DISCLAIMER.md
git commit -m "docs: add disclaimer covering Instagram ToS and account risk

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Final verification & publish readiness

**Files:** none created — verification only.

- [ ] **Step 1: Full test suite passes**

Run: `cd /Users/gvns/code/projects/insta-unfollow && python -m pytest -q`
Expected: all tests pass (both `test_insta_unfollow.py` and `test_build_queue.py`).

- [ ] **Step 2: Audit exactly what is tracked — no personal data**

Run: `git ls-files`
Expected output is ONLY:
```
.gitignore
DISCLAIMER.md
LICENSE
README.md
build_queue.py
diag.js
docs/superpowers/plans/2026-06-14-foss-release-and-resume.md
docs/superpowers/specs/2026-06-14-foss-release-and-resume-design.md
insta_unfollow.py
test_build_queue.py
test_insta_unfollow.py
unfollow.js
unfollow_queue.example.js
```
**If any other path appears (especially `to_unfollow.txt`, `connections/`,
`candidates.csv`, `decisions.csv`, `review.csv`, `unfollow_queue.js`), STOP and
fix `.gitignore` before going further.**

- [ ] **Step 3: Confirm the working tree is clean**

Run: `git status --short`
Expected: no output (everything committed).

- [ ] **Step 4: STOP — publish requires explicit user go-ahead**

Publishing is outward-facing and effectively irreversible (handles/code become
public and may be cached/indexed). Do **not** create or push to a remote until
the user explicitly confirms. When they do, the command is:

```bash
gh repo create insta-unfollow --public --source=. --remote=origin --description "Offline Instagram unfollow-candidate analyser + resumable browser-console unfollower" --push
```

Before running it, re-run `git ls-files` (Step 2) one last time and read the list
aloud to the user for sign-off.

---

## Self-Review

**Spec coverage:** allowlist `.gitignore` → Task 1; MIT `LICENSE` → Task 2;
`build_queue.py` + test → Task 3; `unfollow_queue.example.js` → Task 4;
`unfollow.js` resume → Task 5; `README.md` → Task 6; `DISCLAIMER.md` → Task 7;
test/gitignore audit → Task 8. All spec sections covered.

**Placeholder scan:** no TBD/TODO; every code step shows complete content.

**Type/name consistency:** `STORE_KEY`, `loadDone`, `saveDone`, `done`,
`attempted`, `count` used consistently across `unfollow.js` steps;
`select_from_csv`, `select_from_list`, `dedupe`, `render_queue_js`, `main`,
`DEFAULT_MARKERS` match between `build_queue.py` and `test_build_queue.py`;
`window.UNFOLLOW_TARGETS` is the shared contract between `build_queue.py`,
`unfollow_queue.example.js`, and `unfollow.js`.
```
