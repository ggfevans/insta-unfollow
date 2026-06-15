# insta-unfollow

[![CI](https://github.com/ggfevans/insta-unfollow/actions/workflows/ci.yml/badge.svg)](https://github.com/ggfevans/insta-unfollow/actions/workflows/ci.yml)

Find and bulk-unfollow Instagram accounts from your own browser, with no password
ever leaving your machine. Instagram has no bulk-unfollow by design, a
[dark pattern](https://deceptive.design/) that keeps your following list sticky;
this hands that control back.

Two stages, and the separation *is* the safety model:

1. **`insta_unfollow.py`** (offline analyser): read-only, no network, no login,
   stdlib Python. Turns your data export into a worksheet of unfollow candidates.
   **Zero account risk.**
2. **`unfollow.js`** (opt-in console script): clicks the real Unfollow buttons at
   a human pace, dry-runs first, stops on action-blocks, and resumes across
   sessions. Automating actions breaks Instagram's ToS; using it is your call.

> ⚠️ **`unfollow.js` can get your account action-blocked, restricted, or
> permanently banned. Provided as-is, no warranty, entirely at your own risk.**
> See [DISCLAIMER.md](DISCLAIMER.md).

## Requirements

- Python 3.9+ (stdlib only, nothing to install to run it)
- A desktop browser logged into Instagram
- Your Instagram data export ([Download your information](https://privacycenter.instagram.com/guide/dyi/?entry_point=privacy_center_home), pick **JSON** if offered)

## Usage

1. **Unzip your export here** so `connections/followers_and_following/following.json` exists (HTML works too).
2. **Build the worksheet** (writes `candidates.csv` + `candidates.md`):
   ```bash
   python insta_unfollow.py .
   ```
3. **Decide:** in `candidates.csv`, put `unfollow` (or `u`) in the `decision` column for accounts to drop.
4. **Generate the list** (writes `unfollow_queue.js`):
   ```bash
   python build_queue.py --from-csv candidates.csv
   ```
5. **Unfollow:** open your Instagram profile and click your **Following** count. In the DevTools Console (Cmd+Opt+J / Ctrl+Shift+J), paste `unfollow_queue.js`, then `unfollow.js`. It **dry-runs by default**: verify the handles, set `CONFIG.dryRun = false`, and paste `unfollow.js` again to do it for real.
6. **Resume any day:** re-paste both files. Done accounts are skipped (via `localStorage`) and the per-session cap counts only new unfollows, so you work through a long list over time. `CONFIG.reset = true` starts over.

Start with a small cap and ramp up only if you see no blocks. If the console logs
"0 rows matched", Instagram changed its markup, so paste `diag.js` to see what it sees.

## Files

| File | What it is |
|------|------------|
| `insta_unfollow.py` | Offline, read-only export analyser → `candidates.csv` / `.md` |
| `build_queue.py` | Turns decisions into `unfollow_queue.js` |
| `unfollow.js` | Browser-console unfollower (dry-run-first, resumable) |
| `diag.js` | Console diagnostic when selectors break |
| `unfollow_queue.example.js` | Example target-list format |

Your export and generated files are git-ignored and never leave your machine.

## Notes

- **Tests:** `pip install pytest && python -m pytest -q`
- **Versioning:** [CalVer](https://calver.org/) `YY.MM.MICRO`; see [CHANGELOG.md](CHANGELOG.md).
- **AI disclosure:** built with Claude plus human review. Read the code before you run it.
- **Licence:** MIT, see [LICENSE](LICENSE).
