#!/usr/bin/env python3
"""insta_unfollow.py — offline Instagram "unfollow candidate" worksheet builder.

Strictly OFFLINE and READ-ONLY: it never logs in, makes no network calls, uses
no Instagram API and no credentials. It only reads an *already unzipped*
Instagram data export from disk and writes two local files (candidates.csv,
candidates.md) plus a stdout summary.

The export contains NO post-recency or engagement data, so this tool does NOT
fabricate an "inactive" / "toxic" signal — those need human judgement. Its job
is to surface and sort candidates; the blank `decision` column is yours to fill.

Standard library only. Python 3.9+.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from collections import namedtuple
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

# Local timezone for human-readable dates (per project: Qualicum Beach, BC).
# Falls back to the system local timezone if the zoneinfo database is absent.
try:
    from zoneinfo import ZoneInfo

    LOCAL_TZ = ZoneInfo("America/Vancouver")
except Exception:  # pragma: no cover - depends on host tz database
    LOCAL_TZ = datetime.now().astimezone().tzinfo


Record = namedtuple("Record", ["username", "profile_url", "timestamp"])
ParseResult = namedtuple("ParseResult", ["records", "skipped"])
Found = namedtuple("Found", ["fmt", "following_path", "followers_paths", "base"])

CSV_COLUMNS = [
    "username",
    "profile_url",
    "followed_on",
    "follow_age_days",
    "follows_me_back",
    "mutual",
    "decision",
]


class ExportError(Exception):
    """Raised for unrecoverable problems with the export (missing/garbled)."""


# --------------------------------------------------------------------------- #
# Output sanitisation (defence: untrusted export -> files opened in other apps)
# --------------------------------------------------------------------------- #
_CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_MD_SPECIAL = set("\\`[]()|")


def sanitize_csv_cell(value):
    """Neutralise spreadsheet formula injection.

    A cell that begins with =, +, -, @, tab or CR can be executed as a formula
    by Excel/Sheets. Prefixing a single quote forces it to be treated as text.
    """
    text = "" if value is None else str(value)
    if text and text[0] in _CSV_DANGEROUS_PREFIXES:
        return "'" + text
    return text


def md_escape(text):
    """Escape markdown metacharacters that could break a table cell or a link."""
    if text is None:
        return ""
    text = str(text).replace("\r", " ").replace("\n", " ")
    return "".join("\\" + ch if ch in _MD_SPECIAL else ch for ch in text)


def _is_http_url(url):
    try:
        return urlsplit(url).scheme in ("http", "https")
    except ValueError:
        return False


def safe_md_link(text, url):
    """Render a clickable link only for http(s) URLs; otherwise plain text.

    Prevents javascript:/data: and other unexpected schemes from becoming
    clickable, and escapes the label/target so a crafted username can't inject
    markup.
    """
    label = md_escape(text)
    if url and _is_http_url(url):
        return "[{}]({})".format(label, md_escape(url))
    if url:
        return "{} ({})".format(label, md_escape(url))
    return label


# --------------------------------------------------------------------------- #
# Parsing — schema is detected/tolerated, never assumed
# --------------------------------------------------------------------------- #
def _locate_items(data, preferred_keys):
    """Find the list of relationship entries within a parsed JSON document."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in preferred_keys:
            if isinstance(data.get(key), list):
                return data[key]
        for value in data.values():  # fallback: first list-of-things value
            if isinstance(value, list):
                return value
    return []


def _clean_profile_url(href):
    """Strip Instagram's `/_u/` app-deeplink prefix so the URL opens on the web."""
    if not href:
        return href
    try:
        parts = urlsplit(href)
    except ValueError:
        return href
    segments = [s for s in parts.path.split("/") if s]
    if segments and segments[0] == "_u":
        new_path = "/" + "/".join(segments[1:])
        return urlunsplit((parts.scheme, parts.netloc, new_path, "", ""))
    return href


def _username_from_href(href):
    """Last resort: pull the handle from a profile URL path."""
    try:
        path = urlsplit(_clean_profile_url(href)).path.strip("/")
    except ValueError:
        return ""
    return path.split("/")[0] if path else ""


def _record_from_item(item):
    """Build a Record from one entry, or None if no username can be found.

    The export is inconsistent: followers entries carry the username in
    string_list_data[0].value, while following entries omit `value` and put it
    in the top-level `title`. We try value -> title -> derive from href.
    """
    if not isinstance(item, dict):
        return None
    sld = item.get("string_list_data")
    first = sld[0] if isinstance(sld, list) and sld and isinstance(sld[0], dict) else {}

    href = first.get("href")
    href = _clean_profile_url(href if isinstance(href, str) else "")

    username = None
    for candidate in (first.get("value"), item.get("title")):
        if isinstance(candidate, str) and candidate.strip():
            username = candidate.strip()
            break
    if username is None:
        username = _username_from_href(href) or None
    if username is None:
        return None

    ts = first.get("timestamp")
    if not isinstance(ts, int) or isinstance(ts, bool) or ts <= 0:
        ts = None
    return Record(username, href, ts)


def parse_relationships(data, preferred_keys=()):
    records, skipped = [], 0
    for item in _locate_items(data, preferred_keys):
        rec = _record_from_item(item)
        if rec is None:
            skipped += 1
        else:
            records.append(rec)
    return ParseResult(records, skipped)


def parse_following_json(data):
    return parse_relationships(data, ("relationships_following",))


def parse_followers_json(data):
    return parse_relationships(data, ("relationships_followers", "relationships_follow"))


# --- HTML fallback (stdlib parser: no external entities, no network) -------- #
_HTML_DATE_FORMATS = (
    "%b %d, %Y %I:%M %p",
    "%b %d, %Y, %I:%M %p",
    "%b %d, %Y",
    "%B %d, %Y %I:%M %p",
    "%B %d, %Y",
)


def _parse_html_date(text):
    text = " ".join(text.split())
    if not text:
        return None
    for fmt in _HTML_DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=LOCAL_TZ)
            return int(dt.timestamp())
        except ValueError:
            continue
    return None


class _RelationshipHTMLParser(HTMLParser):
    """Extracts (username, href, date) tuples from an export HTML page.

    Each followed/follower account appears as an <a href> with the username as
    its text; the follow date renders as text after the anchor.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = []
        self._in_anchor = False
        self._href = ""
        self._label_parts = []
        self._pending = None  # (username, href)
        self._trailing = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._flush_pending()
            self._href = dict(attrs).get("href") or ""
            self._in_anchor = True
            self._label_parts = []

    def handle_endtag(self, tag):
        if tag == "a" and self._in_anchor:
            self._in_anchor = False
            username = "".join(self._label_parts).strip()
            self._pending = (username, self._href)
            self._trailing = []

    def handle_data(self, data):
        if self._in_anchor:
            self._label_parts.append(data)
        elif self._pending is not None:
            self._trailing.append(data)

    def _flush_pending(self):
        if self._pending is not None:
            username, href = self._pending
            if username:
                ts = _parse_html_date("".join(self._trailing))
                self.records.append(Record(username, href, ts))
            self._pending = None
            self._trailing = []

    def finalize(self):
        self._flush_pending()


def parse_html_relationships(html_text):
    parser = _RelationshipHTMLParser()
    parser.feed(html_text)
    parser.close()
    parser.finalize()
    return ParseResult(parser.records, 0)


# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #
def format_followed_on(timestamp):
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, LOCAL_TZ).strftime("%Y-%m-%d")


def compute_age_days(timestamp, now):
    if timestamp is None:
        return ""
    followed = datetime.fromtimestamp(timestamp, LOCAL_TZ)
    return (now - followed).days


# --------------------------------------------------------------------------- #
# Candidate building + rendering
# --------------------------------------------------------------------------- #
def build_candidates(following, followers, now):
    """One row per unique followed account, flagged mutual/non-mutual."""
    follower_set = {r.username.casefold() for r in followers if r.username}
    seen = set()
    candidates = []
    for rec in following:
        if not rec.username:
            continue
        key = rec.username.casefold()
        if key in seen:
            continue
        seen.add(key)
        mutual = key in follower_set
        candidates.append(
            {
                "username": rec.username,
                "profile_url": rec.profile_url,
                "followed_on": format_followed_on(rec.timestamp),
                "follow_age_days": compute_age_days(rec.timestamp, now),
                "follows_me_back": mutual,
                "mutual": mutual,
                "decision": "",
                "_timestamp": rec.timestamp,
            }
        )
    return candidates


def csv_rows(candidates):
    rows = [list(CSV_COLUMNS)]
    for c in candidates:
        rows.append([sanitize_csv_cell(c[col]) for col in CSV_COLUMNS])
    return rows


def _oldest_first_key(candidate):
    ts = candidate.get("_timestamp")
    return (ts is None, ts if ts is not None else 0)


def render_markdown(candidates):
    non_mutual = sorted((c for c in candidates if not c["mutual"]), key=_oldest_first_key)
    mutual = sorted((c for c in candidates if c["mutual"]), key=_oldest_first_key)

    lines = ["# Instagram unfollow candidates", ""]
    lines.append(
        "_Offline analysis of a data export. No engagement/recency data exists, "
        "so nothing here judges an account — review and decide for yourself._"
    )
    lines.append("")

    sections = [
        ("1. Non-mutuals", "I follow, they don't follow back — sorted oldest-follow first", non_mutual),
        ("2. Mutuals", "We follow each other — sorted oldest-follow first", mutual),
    ]
    for title, description, group in sections:
        lines.append("## {} ({})".format(title, len(group)))
        lines.append("_{}_".format(description))
        lines.append("")
        if not group:
            lines.append("_None._")
            lines.append("")
            continue
        lines.append("| # | Username | Followed on | Age (days) | Profile |")
        lines.append("|--:|----------|-------------|-----------:|---------|")
        for i, c in enumerate(group, 1):
            age = c["follow_age_days"]
            lines.append(
                "| {} | {} | {} | {} | {} |".format(
                    i,
                    md_escape(c["username"]),
                    md_escape(c["followed_on"]) or "—",
                    age if age != "" else "—",
                    safe_md_link(c["username"], c["profile_url"]),
                )
            )
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# File discovery + IO
# --------------------------------------------------------------------------- #
def find_export_files(base):
    """Locate the following/followers files beneath `base`. JSON preferred."""
    base_real = os.path.realpath(base)

    def find(pattern):
        return sorted(glob.glob(os.path.join(base_real, "**", pattern), recursive=True))

    following_json = find("following*.json")
    followers_json = find("followers*.json")
    if following_json or followers_json:
        if not following_json:
            raise ExportError(
                "Found follower JSON but no following*.json under {}. "
                "Expected connections/followers_and_following/following.json".format(base_real)
            )
        return Found("json", following_json[0], followers_json, base_real)

    following_html = find("following*.html")
    followers_html = find("followers*.html")
    if following_html or followers_html:
        if not following_html:
            raise ExportError(
                "Found follower HTML but no following*.html under {}.".format(base_real)
            )
        return Found("html", following_html[0], followers_html, base_real)

    raise ExportError(
        "No Instagram export files found under {}. Expected "
        "connections/followers_and_following/following.json (or .html). "
        "Unzip your export here, then re-run.".format(base_real)
    )


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ExportError("Malformed JSON in {}: {}".format(path, exc))
    except OSError as exc:
        raise ExportError("Cannot read {}: {}".format(path, exc))


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        raise ExportError("Cannot read {}: {}".format(path, exc))


def load_export(found):
    """Return (following ParseResult, followers ParseResult) for the export."""
    if found.fmt == "json":
        following = parse_following_json(_read_json(found.following_path))
        per_file = [parse_followers_json(_read_json(p)) for p in found.followers_paths]
    else:
        following = parse_html_relationships(_read_text(found.following_path))
        per_file = [parse_html_relationships(_read_text(p)) for p in found.followers_paths]

    followers = ParseResult(
        [r for pr in per_file for r in pr.records],
        sum(pr.skipped for pr in per_file),
    )
    return following, followers


def write_csv(candidates, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(candidates))


def write_markdown(candidates, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(candidates))
        fh.write("\n")


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _rel(path):
    try:
        return os.path.relpath(path)
    except (ValueError, OSError):
        return path


def print_detection_report(found, following, followers):
    print("== Detection report ==")
    print("Export format   : {}".format(found.fmt.upper()))
    print("Following file  : {}".format(_rel(found.following_path)))
    if found.followers_paths:
        print("Followers files : {}".format(", ".join(_rel(p) for p in found.followers_paths)))
    else:
        print("Followers files : (none found — every account will read as non-mutual)")
    print("Following records: {} (skipped {} malformed)".format(len(following.records), following.skipped))
    print("Followers records: {} (skipped {} malformed)".format(len(followers.records), followers.skipped))
    if following.records:
        s = following.records[0]
        print("Sample followed record:")
        print("  username : {}".format(s.username))
        print("  profile  : {}".format(s.profile_url))
        print("  timestamp: {} ({})".format(s.timestamp, format_followed_on(s.timestamp) or "n/a"))
    print()


def print_summary(candidates, total_followers):
    total = len(candidates)
    mutual = sum(1 for c in candidates if c["mutual"])
    print("== Summary ==")
    print("Total followed : {}".format(total))
    print("Total followers: {}".format(total_followers))
    print("Mutual         : {}".format(mutual))
    print("Non-mutual     : {}".format(total - mutual))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Offline Instagram unfollow-candidate worksheet (read-only, no network).",
    )
    parser.add_argument(
        "export_path",
        nargs="?",
        default=".",
        help="Root of the unzipped Instagram export (default: current directory).",
    )
    parser.add_argument(
        "--out",
        default=".",
        help="Directory to write candidates.csv / candidates.md (default: current directory).",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print the detection report and exit without writing any files.",
    )
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)

    try:
        found = find_export_files(args.export_path)
        following, followers = load_export(found)
    except ExportError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2

    print_detection_report(found, following, followers)

    if args.inspect:
        print("(--inspect) No files written.")
        return 0

    if not following.records:
        print("ERROR: no usable 'following' records were parsed; nothing to write.", file=sys.stderr)
        return 2

    out_dir = os.path.realpath(args.out)
    if not os.path.isdir(out_dir):
        print("ERROR: output directory does not exist: {}".format(out_dir), file=sys.stderr)
        return 2

    now = datetime.now(LOCAL_TZ)
    candidates = build_candidates(following.records, followers.records, now)
    unique_followers = len({r.username.casefold() for r in followers.records if r.username})

    csv_path = os.path.join(out_dir, "candidates.csv")
    md_path = os.path.join(out_dir, "candidates.md")
    write_csv(candidates, csv_path)
    write_markdown(candidates, md_path)

    print("Wrote {}".format(_rel(csv_path)))
    print("Wrote {}".format(_rel(md_path)))
    print()
    print_summary(candidates, unique_followers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
