# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) (`YY.MM.MICRO`).

## [Unreleased]

_Nothing yet._

## [26.6.2] - 2026-06-14

### Security
- Pin GitHub Actions to full commit SHAs (`actions/checkout`,
  `actions/setup-python`) instead of mutable tags, so a moved tag cannot silently
  change what CI runs.

### Added
- This `CHANGELOG.md`.
- README link to Instagram's official
  [Download your information](https://privacycenter.instagram.com/guide/dyi/?entry_point=privacy_center_home)
  guide for requesting your data export.

## [26.6.1] - 2026-06-14

### Changed
- CI: bump `actions/checkout@v4` to `v5` and `actions/setup-python@v5` to `v6` so
  the workflow runs on the Node 24 runtime ahead of GitHub's Node 20 deprecation
  (2026-06-16). No changes to the tool itself.

## [26.6.0] - 2026-06-14

First public release. Offline Instagram unfollow tooling in two clearly separated
stages: a read-only offline analyser (zero account risk) and an opt-in
browser-console unfollower.

### Added
- `insta_unfollow.py`, an offline, read-only, standard-library analyser that
  reads an Instagram data export and writes a `candidates.csv` / `candidates.md`
  worksheet (mutual / non-mutual, oldest-follow first). Hardened against
  CSV-formula and markdown injection.
- `build_queue.py`, which generates `unfollow_queue.js` from the `decision`
  column of `candidates.csv`, or from a plain handle list.
- `unfollow.js`, a paste-into-console unfollower: dry-run-first, randomised
  human-pace delays, and action-block detection that stops on contact.
  - Resumes across sessions via `localStorage`: already-unfollowed accounts are
    skipped for free, the session cap counts only new unfollows, and
    `CONFIG.reset` wipes saved progress.
  - Robust scroll / lazy-load handling so a long Following list is not falsely
    declared finished at Instagram's chunk boundaries.
- `diag.js`, a console diagnostic for when Instagram changes its markup.
- `unfollow_queue.example.js`, an example target-list format.
- pytest suites for the analyser and queue generator, run in CI (GitHub Actions,
  Python 3.9 and 3.12).
- Documentation: `README.md`, `DISCLAIMER.md` (Instagram ToS, account risk,
  as-is / no-warranty), and an MIT `LICENSE`.

[Unreleased]: https://github.com/ggfevans/insta-unfollow/compare/v26.6.2...HEAD
[26.6.2]: https://github.com/ggfevans/insta-unfollow/compare/v26.6.1...v26.6.2
[26.6.1]: https://github.com/ggfevans/insta-unfollow/compare/v26.6.0...v26.6.1
[26.6.0]: https://github.com/ggfevans/insta-unfollow/releases/tag/v26.6.0
