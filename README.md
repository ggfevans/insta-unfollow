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
