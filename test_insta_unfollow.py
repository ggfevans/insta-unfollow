"""Tests for insta_unfollow.py — run with: python3 -m unittest -v"""
import json
import os
import tempfile
import unittest
from datetime import datetime

import insta_unfollow as iu


def epoch(year, month, day, hour=12, minute=0):
    """Local (Vancouver) wall-clock time -> Unix epoch int."""
    dt = datetime(year, month, day, hour, minute, tzinfo=iu.LOCAL_TZ)
    return int(dt.timestamp())


NOW = datetime(2024, 3, 20, 12, 0, tzinfo=iu.LOCAL_TZ)


class SanitizeCsvCellTests(unittest.TestCase):
    def test_neutralises_formula_leading_chars(self):
        for payload in ("=cmd()", "+1", "-1", "@SUM(A1)"):
            self.assertEqual(iu.sanitize_csv_cell(payload), "'" + payload)

    def test_neutralises_leading_tab_and_cr(self):
        self.assertEqual(iu.sanitize_csv_cell("\tx"), "'\tx")
        self.assertEqual(iu.sanitize_csv_cell("\rx"), "'\rx")

    def test_leaves_safe_text_untouched(self):
        self.assertEqual(iu.sanitize_csv_cell("alice"), "alice")
        self.assertEqual(iu.sanitize_csv_cell(""), "")

    def test_coerces_non_strings(self):
        self.assertEqual(iu.sanitize_csv_cell(6), "6")
        self.assertEqual(iu.sanitize_csv_cell(True), "True")


class MarkdownEscapeTests(unittest.TestCase):
    def test_escapes_table_and_link_metacharacters(self):
        self.assertEqual(iu.md_escape("a|b"), "a\\|b")
        self.assertEqual(iu.md_escape("x[y]z"), "x\\[y\\]z")
        self.assertEqual(iu.md_escape("(p)"), "\\(p\\)")

    def test_collapses_newlines(self):
        self.assertNotIn("\n", iu.md_escape("a\nb"))


class SafeMdLinkTests(unittest.TestCase):
    def test_http_url_becomes_clickable_link(self):
        out = iu.safe_md_link("alice", "https://www.instagram.com/alice")
        self.assertEqual(out, "[alice](https://www.instagram.com/alice)")

    def test_non_http_scheme_is_not_linked(self):
        out = iu.safe_md_link("alice", "javascript:alert(1)")
        self.assertNotIn("](", out)
        self.assertIn("alice", out)

    def test_empty_url_renders_plain_text(self):
        out = iu.safe_md_link("alice", "")
        self.assertNotIn("](", out)
        self.assertIn("alice", out)


class ParseRelationshipsTests(unittest.TestCase):
    def test_parses_following_object_shape(self):
        data = {
            "relationships_following": [
                {
                    "title": "",
                    "string_list_data": [
                        {
                            "href": "https://www.instagram.com/alice",
                            "value": "alice",
                            "timestamp": epoch(2024, 3, 14),
                        }
                    ],
                }
            ]
        }
        result = iu.parse_following_json(data)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(len(result.records), 1)
        rec = result.records[0]
        self.assertEqual(rec.username, "alice")
        self.assertEqual(rec.profile_url, "https://www.instagram.com/alice")
        self.assertEqual(rec.timestamp, epoch(2024, 3, 14))

    def test_parses_followers_bare_list_shape(self):
        data = [
            {
                "string_list_data": [
                    {"href": "https://www.instagram.com/bob", "value": "bob", "timestamp": 123}
                ]
            }
        ]
        result = iu.parse_followers_json(data)
        self.assertEqual([r.username for r in result.records], ["bob"])

    def test_skips_malformed_records_and_counts_them(self):
        data = {
            "relationships_following": [
                {"string_list_data": []},          # empty -> skip
                {"foo": 1},                          # no string_list_data -> skip
                {"string_list_data": [{"value": "carol", "href": "u", "timestamp": 5}]},
            ]
        }
        result = iu.parse_following_json(data)
        self.assertEqual([r.username for r in result.records], ["carol"])
        self.assertEqual(result.skipped, 2)

    def test_parses_following_title_only_shape(self):
        # Real export quirk: following.json puts the username in the top-level
        # 'title' and omits 'value' from string_list_data.
        data = {
            "relationships_following": [
                {
                    "title": "realuser",
                    "string_list_data": [
                        {"href": "https://www.instagram.com/realuser", "timestamp": epoch(2024, 3, 14)}
                    ],
                }
            ]
        }
        result = iu.parse_following_json(data)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.records[0].username, "realuser")
        self.assertEqual(result.records[0].profile_url, "https://www.instagram.com/realuser")
        self.assertEqual(result.records[0].timestamp, epoch(2024, 3, 14))

    def test_normalises_app_deeplink_profile_url(self):
        data = {
            "relationships_following": [
                {
                    "title": "bcconservation",
                    "string_list_data": [
                        {"href": "https://www.instagram.com/_u/bcconservation", "timestamp": epoch(2024, 3, 14)}
                    ],
                }
            ]
        }
        rec = iu.parse_following_json(data).records[0]
        self.assertEqual(rec.profile_url, "https://www.instagram.com/bcconservation")

    def test_derives_username_from_href_when_value_and_title_absent(self):
        data = {"relationships_following": [{"string_list_data": [{"href": "https://www.instagram.com/heidi/"}]}]}
        result = iu.parse_following_json(data)
        self.assertEqual(result.records[0].username, "heidi")

    def test_missing_timestamp_yields_none_not_crash(self):
        data = {"relationships_following": [{"string_list_data": [{"value": "dave", "href": "u"}]}]}
        result = iu.parse_following_json(data)
        self.assertEqual(result.records[0].username, "dave")
        self.assertIsNone(result.records[0].timestamp)


class BuildCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.following = [
            iu.Record("alice", "https://www.instagram.com/alice", epoch(2024, 3, 14)),
            iu.Record("Bob", "https://www.instagram.com/Bob", epoch(2024, 3, 1)),
            iu.Record("alice", "https://www.instagram.com/alice", epoch(2024, 3, 14)),  # dup
        ]
        # follower 'bob' lower-case must match followed 'Bob' (case-insensitive)
        self.followers = [iu.Record("bob", "https://www.instagram.com/bob", 1)]
        self.cands = iu.build_candidates(self.following, self.followers, NOW)

    def test_dedupes_following_by_casefolded_username(self):
        self.assertEqual(len(self.cands), 2)

    def test_marks_mutual_case_insensitively(self):
        bob = next(c for c in self.cands if c["username"] == "Bob")
        self.assertTrue(bob["follows_me_back"])
        self.assertTrue(bob["mutual"])

    def test_marks_non_mutual(self):
        alice = next(c for c in self.cands if c["username"] == "alice")
        self.assertFalse(alice["follows_me_back"])
        self.assertFalse(alice["mutual"])

    def test_computes_followed_on_and_age(self):
        alice = next(c for c in self.cands if c["username"] == "alice")
        self.assertEqual(alice["followed_on"], "2024-03-14")
        self.assertEqual(alice["follow_age_days"], 6)

    def test_decision_column_is_blank(self):
        self.assertEqual(self.cands[0]["decision"], "")

    def test_missing_timestamp_blank_date_and_age(self):
        cands = iu.build_candidates([iu.Record("e", "u", None)], [], NOW)
        self.assertEqual(cands[0]["followed_on"], "")
        self.assertEqual(cands[0]["follow_age_days"], "")


class CsvRowsTests(unittest.TestCase):
    def test_header_matches_columns(self):
        rows = iu.csv_rows([])
        self.assertEqual(rows[0], iu.CSV_COLUMNS)

    def test_sanitises_injection_in_username(self):
        cands = iu.build_candidates([iu.Record("=evil", "https://x/y", epoch(2024, 3, 14))], [], NOW)
        rows = iu.csv_rows(cands)
        username_idx = iu.CSV_COLUMNS.index("username")
        self.assertEqual(rows[1][username_idx], "'=evil")


class RenderMarkdownTests(unittest.TestCase):
    def test_sections_present_and_ordered_oldest_first(self):
        following = [
            iu.Record("old_nonmutual", "https://www.instagram.com/old_nonmutual", epoch(2024, 1, 1)),
            iu.Record("new_nonmutual", "https://www.instagram.com/new_nonmutual", epoch(2024, 3, 1)),
            iu.Record("a_mutual", "https://www.instagram.com/a_mutual", epoch(2024, 2, 1)),
        ]
        followers = [iu.Record("a_mutual", "u", 1)]
        cands = iu.build_candidates(following, followers, NOW)
        md = iu.render_markdown(cands)
        self.assertIn("Non-mutuals", md)
        self.assertIn("Mutuals", md)
        # oldest non-mutual listed before the newer one
        self.assertLess(md.index("old_nonmutual"), md.index("new_nonmutual"))
        # mutual rendered as a clickable link
        self.assertIn("[a_mutual](https://www.instagram.com/a_mutual)", md)


class FindExportFilesTests(unittest.TestCase):
    def _make_tree(self, files):
        base = tempfile.mkdtemp()
        d = os.path.join(base, "connections", "followers_and_following")
        os.makedirs(d)
        for name in files:
            with open(os.path.join(d, name), "w") as fh:
                fh.write("{}" if name.endswith(".json") else "<html></html>")
        return base

    def test_detects_json_with_split_followers(self):
        base = self._make_tree(["following.json", "followers_1.json", "followers_2.json"])
        found = iu.find_export_files(base)
        self.assertEqual(found.fmt, "json")
        self.assertIsNotNone(found.following_path)
        self.assertEqual(len(found.followers_paths), 2)

    def test_prefers_json_over_html(self):
        base = self._make_tree(["following.json", "followers.json", "following.html"])
        found = iu.find_export_files(base)
        self.assertEqual(found.fmt, "json")

    def test_falls_back_to_html(self):
        base = self._make_tree(["following.html", "followers.html"])
        found = iu.find_export_files(base)
        self.assertEqual(found.fmt, "html")

    def test_missing_directory_raises_export_error(self):
        empty = tempfile.mkdtemp()
        with self.assertRaises(iu.ExportError):
            iu.find_export_files(empty)


class HtmlParsingTests(unittest.TestCase):
    def test_extracts_username_and_url_from_anchor(self):
        html = (
            '<div><a href="https://www.instagram.com/frank" target="_blank">frank</a>'
            "<div>Mar 14, 2024</div></div>"
        )
        result = iu.parse_html_relationships(html)
        self.assertEqual(result.records[0].username, "frank")
        self.assertEqual(result.records[0].profile_url, "https://www.instagram.com/frank")


if __name__ == "__main__":
    unittest.main()
