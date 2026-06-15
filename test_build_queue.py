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
