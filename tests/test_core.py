"""Pure-logic tests for docsort — no model, no network."""
import os, json
import pytest
from docsort import cli, config


def _tmp(text, tmp_path, name="TAGS.md"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_load_tags_bundled():
    s, su, ty = cli.load_tags(config._bundled("TAGS.md"))
    assert "CW" in s and "GATE" in s
    assert "99UNS" in su and "08DIG" in su
    assert "notes" in ty and "misc" in ty


def test_passes_filter():
    P = cli.passes_filter
    root, f = "C:/d", "C:/d/GATE/notes/x.pdf"
    assert P(f, root, [], []) is True
    assert P(f, root, [], ["GATE"]) is False          # excluded
    assert P(f, root, ["GATE"], []) is True            # included
    assert P(f, root, ["RES"], []) is False            # include miss
    assert P(f, root, [], ["GATE/notes"]) is False     # nested segment


def test_decide_and_proposal():
    s, su, ty = cli.load_tags(config._bundled("TAGS.md"))
    cli.STREAMS, cli.SUBJECTS, cli.TYPES = set(s), set(su), set(ty)
    assert cli.decide("CW 08DIG notes high") == ("CW", "08DIG", "notes", "high")
    st, sub, _, _ = cli.decide("CW 99UNS notes high PROPOSE:THERMO")
    assert sub == "~THERMO"


def test_tag_editor_roundtrip(tmp_path):
    from docsort import tagsio
    txt = open(config._bundled("TAGS.md"), encoding="utf-8").read()
    subs = tagsio.tag_block(txt, "SUBJECTS")
    subs.append("93TEST  a new subject")
    new = tagsio.replace_block(txt, "SUBJECTS", subs)
    _, su, _ = cli.load_tags(_tmp(new, tmp_path))
    assert "93TEST" in su


def test_skip_unknown(tmp_path, monkeypatch):
    """--skip-unknown leaves 99UNS files untouched; known files still rename."""
    monkeypatch.setenv("APPDATA", str(tmp_path))                 # isolate journal/index
    d = tmp_path / "run"; d.mkdir()
    (d / "unknown.pdf").write_text("x", encoding="utf-8")
    (d / "known.pdf").write_text("x", encoding="utf-8")

    def fake_classify(a, sysp, full, fn, rel):
        return ("CW", "99UNS", "misc", "low", "text") if "unknown" in fn \
            else ("CW", "08DIG", "notes", "high", "text")
    monkeypatch.setattr(cli, "classify", fake_classify)
    monkeypatch.setattr(cli, "resolve_model", lambda *a, **k: ("m", True))

    cli.main([str(d), "--apply", "--skip-unknown", "--no-misc"])
    assert (d / "unknown.pdf").exists()                          # untouched
    assert not (d / "[CW-99UNS] unknown.pdf").exists()           # NOT renamed
    assert (d / "[CW-08DIG] known.pdf").exists()                 # known still renamed


def test_report_and_undo(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))          # isolate the global index
    d = str(tmp_path / "run"); os.makedirs(os.path.join(d, "misc"))
    open(os.path.join(d, "[CW-08DIG] a.pdf"), "w").close()
    open(os.path.join(d, "misc", "[CW-99UNS] b.pdf"), "w").close()
    rows = [
        {"rel": "a.pdf", "name": "a.pdf", "status": "done", "stream": "CW", "subject": "08DIG",
         "type": "notes", "conf": "high", "source": "text", "dst": "[CW-08DIG] a.pdf", "error": ""},
        {"rel": "b.pdf", "name": "b.pdf", "status": "done", "stream": "CW", "subject": "99UNS",
         "type": "misc", "conf": "low", "source": "vision", "dst": "misc/[CW-99UNS] b.pdf", "error": ""},
    ]
    with open(os.path.join(d, "_docsort_state.jsonl"), "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    assert cli.report(d)
    assert os.path.exists(os.path.join(d, "DOCSORT-REPORT.md"))
    cli.undo(d)
    assert os.path.exists(os.path.join(d, "a.pdf"))       # rename reversed
    assert os.path.exists(os.path.join(d, "b.pdf"))       # misc move reversed


def test_apply_journal(tmp_path, monkeypatch):
    """--apply-journal replays a dry-run's recorded decisions as renames, with
    no model calls; files changed since the audit (mtime mismatch) are skipped."""
    monkeypatch.setenv("APPDATA", str(tmp_path))          # isolate the global index
    d = tmp_path / "run"; d.mkdir()
    f_ok = d / "a.pdf"; f_ok.write_text("x", encoding="utf-8")
    f_stale = d / "b.pdf"; f_stale.write_text("y", encoding="utf-8")
    f_unk = d / "c.pdf"; f_unk.write_text("z", encoding="utf-8")
    mt_ok = int(os.path.getmtime(f_ok))
    mt_unk = int(os.path.getmtime(f_unk))
    rows = [
        {"rel": "a.pdf", "name": "a.pdf", "mtime": mt_ok, "status": "done", "stream": "CW",
         "subject": "08DIG", "type": "notes", "conf": "high", "source": "text", "dst": "a.pdf", "error": ""},
        {"rel": "b.pdf", "name": "b.pdf", "mtime": 1, "status": "done", "stream": "CW",          # mtime mismatch
         "subject": "10CTRL", "type": "notes", "conf": "high", "source": "text", "dst": "b.pdf", "error": ""},
        {"rel": "c.pdf", "name": "c.pdf", "mtime": mt_unk, "status": "done", "stream": "CW",
         "subject": "99UNS", "type": "misc", "conf": "low", "source": "vision", "dst": "c.pdf", "error": ""},
    ]
    with open(d / "_docsort_state.jsonl", "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r) + "\n")

    cli.apply_journal(str(d), misc=True, skip_unknown=False)

    assert (d / "[CW-08DIG] a.pdf").exists()              # applied from journal
    assert not (d / "a.pdf").exists()
    assert (d / "b.pdf").exists()                         # stale (mtime) -> untouched
    assert not (d / "[CW-10CTRL] b.pdf").exists()
    assert (d / "misc" / "[CW-99UNS] c.pdf").exists()     # 99UNS swept to misc (misc=True)
