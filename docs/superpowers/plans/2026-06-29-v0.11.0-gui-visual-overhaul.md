# v0.11.0 — GUI Visual Overhaul (Flet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stale fixed Tkinter GUI with a modern, low-resource Flet (Python) front end — Discord-like dark look, minimal animations, run view that foregrounds progress + time/ETA + per-file tier — with no change to the engine or its behaviour.

**Architecture:** A new UI-agnostic core module (`docsort/runcore.py`) holds the pure, testable logic: parse the engine's `PROGRESS` stream, parse the per-file result rows, and build the `docsort` CLI command. A `RunController` in the same module wraps `subprocess.Popen` in a thread and pushes parsed events to a callback. The Flet UI (`docsort/gui.py`, rewritten) consumes the core and never re-implements parsing. The UI drives the **existing** `docsort` CLI as a subprocess exactly as today — same flags, same output contract — so no engine code is touched. Tag-block editing logic moves to `docsort/tagsio.py` so it is reusable without Tkinter.

**Tech Stack:** Python 3.9+, Flet (Flutter-based, Python), the existing `docsort` CLI engine, pytest. Flet is an **optional dependency** under a `[gui]` extra; the CLI install stays dependency-light.

**Engine output contract (read-only — do NOT change it):**
- Progress line: `PROGRESS {i}/{N} done={d} failed={f} tps={t} toks={k} eta={e}s` (cli.py:532).
- Per-file result row (printed after each file, cli.py:515): fixed columns
  `{stream:5}{subject:7}{type:10}{conf:5}{source:14}{basename[:46]}` then an optional trailing
  marker `  ->misc` / `  ->skip` / `  FAIL`. `source` is the tier (`text`, `text5`, `vision`,
  `vision3`, `frontier:claude`, `filename`, `error`).
- `PROGRESS` does **not** carry `skipped` or the current filename. The UI derives `skipped` by
  counting result rows that end in `->skip`, and shows completed files (with tier) in the feed.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `docsort/runcore.py` | Pure parse + command-build + `RunController` (subprocess/thread/events). No UI, no engine logic. | Create |
| `docsort/tagsio.py` | `tag_block(text, header)` / `replace_block(text, header, lines)` — TAGS.md block read/rewrite, moved out of the Tkinter `App`. | Create |
| `docsort/gui.py` | Flet front end: theme, nav rail, view routing, Run/Tags/Folders/Reports/Stats views. Consumes `runcore` + `tagsio`. | Replace |
| `tests/test_runcore.py` | Unit tests for `parse_progress`, `parse_result_row`, `build_run_cmd`, `RunController`. | Create |
| `tests/test_core.py` | Update `test_tag_editor_roundtrip` to import from `tagsio` instead of `gui.App`. | Modify |
| `pyproject.toml` | `version = "0.11.0"`; add `[project.optional-dependencies] gui = ["flet>=0.21"]`. | Modify |
| `docsort/__init__.py` | `__version__ = "0.11.0"`. | Modify |
| `CHANGELOG.md` | `[0.11.0]` entry. | Modify |
| `.github/workflows/release.yml` | Build the GUI exe with `flet pack` (see Task D2). | Modify |

---

## Phase A — Extract the testable core (no UI switch yet)

### Task A1: `parse_progress` in runcore

**Files:**
- Create: `docsort/runcore.py`
- Test: `tests/test_runcore.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runcore.py
from docsort import runcore


def test_parse_progress_basic():
    d = runcore.parse_progress("PROGRESS 34/50 done=33 failed=1 tps=41 toks=1234 eta=26s")
    assert d == {"i": 34, "n": 50, "pct": 68, "done": 33, "failed": 1,
                 "tps": "41", "toks": "1234", "eta": "26"}


def test_parse_progress_zero_total():
    d = runcore.parse_progress("PROGRESS 0/0 done=0 failed=0 tps=0 toks=0 eta=0s")
    assert d["pct"] == 0 and d["n"] == 0


def test_parse_progress_rejects_other_lines():
    assert runcore.parse_progress("[model] 'x' not loaded -> 'y'") is None
    assert runcore.parse_progress("CW 08DIG notes high text a.pdf") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runcore.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docsort.runcore'`

- [ ] **Step 3: Write minimal implementation**

```python
# docsort/runcore.py
"""UI-agnostic run core for docsort: parse the engine's stdout contract,
build the CLI command, and drive the run as a subprocess. No UI imports."""
from __future__ import annotations
import sys, subprocess, threading


def parse_progress(line):
    """Parse a 'PROGRESS i/N done= failed= tps= toks= eta=Es' line. None if not one."""
    parts = line.split()
    if not parts or parts[0] != "PROGRESS" or len(parts) < 2 or "/" not in parts[1]:
        return None
    try:
        i_s, n_s = parts[1].split("/")
        i, n = int(i_s), int(n_s)
    except ValueError:
        return None
    kv = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
    pct = int(100 * i / n) if n else 0
    return {"i": i, "n": n, "pct": pct,
            "done": int(kv.get("done", 0) or 0), "failed": int(kv.get("failed", 0) or 0),
            "tps": kv.get("tps", ""), "toks": kv.get("toks", ""),
            "eta": kv.get("eta", "").rstrip("s")}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runcore.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add docsort/runcore.py tests/test_runcore.py
git commit -m "feat(runcore): parse_progress for the engine PROGRESS line"
```

---

### Task A2: `parse_result_row` in runcore

**Files:**
- Modify: `docsort/runcore.py`
- Test: `tests/test_runcore.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runcore.py (append)
STREAMS = {"CW", "GATE", "PROJ", "RES", "REC", "REF"}
SUBJECTS = {"08DIG", "10CTRL", "99UNS", "NA"}


def test_parse_result_row_basic():
    line = "CW   08DIG  notes     high text          control_bode_notes.pdf"
    r = runcore.parse_result_row(line, STREAMS, SUBJECTS)
    assert r["stream"] == "CW" and r["subject"] == "08DIG"
    assert r["type"] == "notes" and r["conf"] == "high" and r["source"] == "text"
    assert r["name"] == "control_bode_notes.pdf"
    assert r["tag"] == "[CW-08DIG]" and r["skipped"] is False


def test_parse_result_row_strips_markers():
    line = "GATE 99UNS  pyq       high text          gate_2024_ec_paper.pdf  ->skip"
    r = runcore.parse_result_row(line, STREAMS, SUBJECTS)
    assert r["name"] == "gate_2024_ec_paper.pdf" and r["skipped"] is True


def test_parse_result_row_rejects_non_rows():
    assert runcore.parse_result_row("PROGRESS 1/2 done=1 failed=0", STREAMS, SUBJECTS) is None
    assert runcore.parse_result_row("[model] note", STREAMS, SUBJECTS) is None
    assert runcore.parse_result_row("ZZ 08DIG notes high text x.pdf", STREAMS, SUBJECTS) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runcore.py -k result_row -v`
Expected: FAIL — `AttributeError: module 'docsort.runcore' has no attribute 'parse_result_row'`

- [ ] **Step 3: Write minimal implementation**

```python
# docsort/runcore.py (append)
_MARKERS = {"->misc", "->skip", "FAIL"}


def parse_result_row(line, streams, subjects):
    """Parse a per-file result row into a dict, or None if the line isn't one.
    Recognised by: first token is a known STREAM and second a known SUBJECT."""
    toks = line.split()
    if len(toks) < 6:
        return None
    st, su, ty, cf, src = toks[0], toks[1], toks[2], toks[3], toks[4]
    if st not in streams or su not in subjects:
        return None
    rest = toks[5:]
    skipped = "->skip" in rest
    while rest and rest[-1] in _MARKERS:
        rest.pop()
    return {"stream": st, "subject": su, "type": ty, "conf": cf, "source": src,
            "name": " ".join(rest), "tag": f"[{st}-{su}]", "skipped": skipped}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runcore.py -k result_row -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add docsort/runcore.py tests/test_runcore.py
git commit -m "feat(runcore): parse_result_row for per-file engine rows"
```

---

### Task A3: `build_run_cmd` in runcore

**Files:**
- Modify: `docsort/runcore.py`
- Test: `tests/test_runcore.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runcore.py (append)
def test_build_run_cmd_defaults():
    cmd = runcore.build_run_cmd({}, python="PY", folder="F")
    assert cmd == ["PY", "-m", "docsort.cli", "F"]


def test_build_run_cmd_all_toggles():
    opts = {"host": "HOME", "model": "qwen", "vision": True, "apply": True,
            "copy": True, "misc": False, "skip_unknown": True, "frontier": "claude"}
    cmd = runcore.build_run_cmd(opts, python="PY", folder="F")
    assert cmd == ["PY", "-m", "docsort.cli", "F",
                   "--host", "HOME", "--model", "qwen", "--vision-model", "qwen",
                   "--vision", "--apply", "--copy", "--no-misc",
                   "--skip-unknown", "--frontier", "claude"]


def test_build_run_cmd_model_auto_and_misc_default():
    cmd = runcore.build_run_cmd({"model": "auto", "misc": True}, python="PY", folder="F")
    assert "--model" not in cmd and "--no-misc" not in cmd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runcore.py -k build_run_cmd -v`
Expected: FAIL — `AttributeError: ... has no attribute 'build_run_cmd'`

- [ ] **Step 3: Write minimal implementation**

```python
# docsort/runcore.py (append)
def build_run_cmd(opts, python=None, folder=None):
    """Build the `python -m docsort.cli <folder> ...` command from UI options.
    Mirrors the existing gui.run() flag mapping exactly. `misc` defaults ON."""
    cmd = [python or sys.executable, "-m", "docsort.cli", folder]
    if opts.get("host"):
        cmd += ["--host", opts["host"]]
    model = opts.get("model", "auto")
    if model and model != "auto":
        cmd += ["--model", model, "--vision-model", model]
    if opts.get("vision"):
        cmd.append("--vision")
    if opts.get("apply"):
        cmd.append("--apply")
    if opts.get("copy"):
        cmd.append("--copy")
    if not opts.get("misc", True):
        cmd.append("--no-misc")
    if opts.get("skip_unknown"):
        cmd.append("--skip-unknown")
    fr = opts.get("frontier", "none")
    if fr and fr != "none":
        cmd += ["--frontier", fr]
    return cmd
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runcore.py -k build_run_cmd -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add docsort/runcore.py tests/test_runcore.py
git commit -m "feat(runcore): build_run_cmd from UI options"
```

---

### Task A4: Move tag-block logic to `tagsio.py`

The Tkinter `App` holds `_tag_block` / `_replace_block` as staticmethods (gui.py:287-296). Move them to a UI-free module so the Flet UI (and the test) use them without importing Tkinter.

**Files:**
- Create: `docsort/tagsio.py`
- Modify: `tests/test_core.py:38-46` (the `test_tag_editor_roundtrip` test)

- [ ] **Step 1: Update the existing test to the new home (it will fail)**

Replace `tests/test_core.py` lines 38-46 with:

```python
def test_tag_editor_roundtrip(tmp_path):
    from docsort import tagsio
    txt = open(config._bundled("TAGS.md"), encoding="utf-8").read()
    subs = tagsio.tag_block(txt, "SUBJECTS")
    subs.append("93TEST  a new subject")
    new = tagsio.replace_block(txt, "SUBJECTS", subs)
    _, su, _ = cli.load_tags(_tmp(new, tmp_path))
    assert "93TEST" in su
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_core.py::test_tag_editor_roundtrip -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docsort.tagsio'`

- [ ] **Step 3: Create `tagsio.py` with the moved logic**

Copy the exact body of `App._tag_block` and `App._replace_block` (gui.py:287-296) into module functions:

```python
# docsort/tagsio.py
"""Read and rewrite the ```tags blocks in TAGS.md, UI-free.
A block is delimited by '## <HEADER>' then a fenced ```tags ... ``` region;
each non-empty line's first whitespace token is the code."""
from __future__ import annotations


def tag_block(text, header):
    """Return the list of raw lines inside the ```tags block under '## <header>'."""
    lines = text.splitlines()
    out, in_hdr, in_fence = [], False, False
    for ln in lines:
        if ln.strip().startswith("## "):
            in_hdr = ln.strip()[3:].split()[0].upper() == header.upper()
            in_fence = False
            continue
        if in_hdr and ln.strip().startswith("```"):
            if in_fence:
                break
            in_fence = True
            continue
        if in_hdr and in_fence and ln.strip():
            out.append(ln.rstrip())
    return out


def replace_block(text, header, lines):
    """Return `text` with the ```tags block under '## <header>' replaced by `lines`."""
    src = text.splitlines()
    out, i, n = [], 0, len(src)
    while i < n:
        ln = src[i]
        out.append(ln)
        if ln.strip().startswith("## ") and ln.strip()[3:].split()[0].upper() == header.upper():
            i += 1
            while i < n and not src[i].strip().startswith("```"):
                out.append(src[i]); i += 1
            if i < n:
                out.append(src[i]); i += 1            # opening fence
            out.extend(lines)                          # new body
            while i < n and not src[i].strip().startswith("```"):
                i += 1                                  # skip old body
            if i < n:
                out.append(src[i]); i += 1            # closing fence
            continue
        i += 1
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")
```

> NOTE: If the current `App._tag_block` / `App._replace_block` bodies differ from the above, copy
> the **actual** current bodies verbatim instead — they are known-correct and already tested. The
> goal of this task is a pure move, not a rewrite.

- [ ] **Step 4: Run the full suite to verify green**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (all existing tests + the moved one)

- [ ] **Step 5: Commit**

```bash
git add docsort/tagsio.py tests/test_core.py
git commit -m "refactor(tagsio): move TAGS.md block logic out of the Tkinter App"
```

---

## Phase B — Flet runtime core + shell + Run view

### Task B1: `RunController` in runcore (subprocess + thread + events)

Wrap `subprocess.Popen` in a thread; classify each stdout line via `parse_progress` / `parse_result_row`; push typed events `("progress", dict)`, `("file", dict)`, `("log", str)`, `("done", None)` to a callback. Drop benign `MuPDF error` lines (matches current gui.py:250).

**Files:**
- Modify: `docsort/runcore.py`
- Test: `tests/test_runcore.py`

- [ ] **Step 1: Write the failing test (hermetic — fake emitter subprocess, no flet/network)**

```python
# tests/test_runcore.py (append)
import sys as _sys, time as _time


def test_run_controller_emits_events():
    emitter = ("import sys;"
               "print('starting');"
               "print('PROGRESS 1/2 done=1 failed=0 tps=10 toks=5 eta=3s');"
               "print('CW 08DIG notes high text a.pdf');"
               "print('MuPDF error: ignore me');"
               "sys.stdout.flush()")
    cmd = [_sys.executable, "-c", emitter]
    events = []
    streams = {"CW"}; subjects = {"08DIG"}
    ctrl = runcore.RunController(streams, subjects, on_event=events.append)
    ctrl.start(cmd, cwd=".")
    for _ in range(100):                 # wait up to ~5s for the 'done' event
        if any(e[0] == "done" for e in events):
            break
        _time.sleep(0.05)
    kinds = [e[0] for e in events]
    assert "progress" in kinds and "file" in kinds and "done" in kinds
    prog = next(e[1] for e in events if e[0] == "progress")
    assert prog["i"] == 1 and prog["n"] == 2
    fil = next(e[1] for e in events if e[0] == "file")
    assert fil["name"] == "a.pdf"
    assert not any("MuPDF error" in (e[1] if isinstance(e[1], str) else "") for e in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runcore.py -k run_controller -v`
Expected: FAIL — `AttributeError: ... has no attribute 'RunController'`

- [ ] **Step 3: Write minimal implementation**

```python
# docsort/runcore.py (append)
class RunController:
    """Runs the docsort CLI as a subprocess in a background thread and emits
    typed events to `on_event`: ('progress', dict) | ('file', dict) |
    ('log', str) | ('done', None). Thread-safe stop via terminate()."""

    def __init__(self, streams, subjects, on_event):
        self.streams = set(streams)
        self.subjects = set(subjects)
        self.on_event = on_event
        self.proc = None
        self._thread = None

    def start(self, cmd, cwd):
        if self.proc:
            return
        self._thread = threading.Thread(target=self._run, args=(cmd, cwd), daemon=True)
        self._thread.start()

    def _run(self, cmd, cwd):
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            for line in self.proc.stdout:
                if "MuPDF error" in line:
                    continue
                s = line.rstrip("\n")
                prog = parse_progress(s)
                if prog is not None:
                    self.on_event(("progress", prog)); continue
                row = parse_result_row(s, self.streams, self.subjects)
                if row is not None:
                    self.on_event(("file", row)); continue
                self.on_event(("log", line))
            self.proc.wait()
        except Exception as e:
            self.on_event(("log", f"[gui] error: {e}\n"))
        finally:
            self.proc = None
            self.on_event(("done", None))

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass

    @property
    def running(self):
        return self.proc is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runcore.py -k run_controller -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docsort/runcore.py tests/test_runcore.py
git commit -m "feat(runcore): RunController (threaded subprocess -> typed events)"
```

---

### Task B2: Flet app shell — theme, nav rail, view routing

Rewrite `docsort/gui.py` as a Flet app. This task delivers the **shell only**: dark theme, a left
`NavigationRail` (Run / Tags / Folders / Reports / Stats), and a content area that swaps a placeholder
per section. Later tasks fill each view. The `docsort-gui` entry point and `python -m docsort.gui` both
launch it. Guard the Flet import so a CLI-only install gives a helpful message.

**Files:**
- Replace: `docsort/gui.py`
- Manual verify (no unit test — UI rendering)

- [ ] **Step 1: Replace `docsort/gui.py` with the Flet shell**

```python
#!/usr/bin/env python3
"""docsort.gui — modern Flet front end.

Visual overhaul of the classifier UI. The run still executes as the existing
`python -m docsort.cli ...` subprocess (see docsort.runcore.RunController), so the
engine and its behaviour are unchanged — this module is presentation only.

  docsort-gui            (or: python -m docsort.gui)
Requires the [gui] extra:  pip install "docsort[gui]"
"""
from __future__ import annotations
import os, sys

try:
    import flet as ft
except ImportError:                       # CLI-only install
    ft = None

from . import config
from .cli import available_models, load_tags

# repo root / site-packages dir that contains the docsort package (for `-m docsort.cli`)
PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- palette (Discord-like dark) ----
BG      = "#1b1b27"
PANEL   = "#232334"
PANEL2  = "#2a2a3d"
FG      = "#e6e6ef"
MUTED   = "#9aa0b4"
ACCENT  = "#7c5cff"
OK      = "#3ddc84"
FAIL    = "#e0715e"


def main():
    if ft is None:
        sys.stderr.write(
            "docsort-gui needs the GUI extra. Install it with:\n"
            '    pip install "docsort[gui]"\n')
        sys.exit(1)
    ft.app(target=_build)


def _build(page: "ft.Page"):
    page.title = "docsort"
    page.bgcolor = BG
    page.padding = 0
    page.window_min_width = 720
    page.window_min_height = 560
    page.theme_mode = ft.ThemeMode.DARK

    content = ft.Container(expand=True, padding=18, content=ft.Text("Run", color=FG))

    def select(idx):
        # later tasks return real views; shell shows the section name
        names = ["Run", "Tags", "Folders", "Reports", "Stats"]
        content.content = ft.Text(names[idx], color=FG, size=18)
        page.update()

    rail = ft.NavigationRail(
        selected_index=0,
        bgcolor=PANEL,
        indicator_color=ACCENT,
        min_width=84,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(icon=ft.icons.PLAY_ARROW, label="Run"),
            ft.NavigationRailDestination(icon=ft.icons.LABEL, label="Tags"),
            ft.NavigationRailDestination(icon=ft.icons.FOLDER, label="Folders"),
            ft.NavigationRailDestination(icon=ft.icons.DESCRIPTION, label="Reports"),
            ft.NavigationRailDestination(icon=ft.icons.BAR_CHART, label="Stats"),
        ],
        on_change=lambda e: select(e.control.selected_index),
    )

    page.add(ft.Row([rail, ft.VerticalDivider(width=1, color=PANEL2), content],
                    expand=True, spacing=0))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Install the GUI extra into the dev venv**

Run: `.venv\Scripts\python.exe -m pip install flet>=0.21`
Expected: flet installs.

- [ ] **Step 3: Manual verify the shell launches**

Run: `.venv\Scripts\python.exe -m docsort.gui`
Expected: a dark window opens with a left rail of 5 icons; clicking each swaps the right-side label
between Run / Tags / Folders / Reports / Stats. Close the window.

- [ ] **Step 4: Verify the import guard and that nothing else broke**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (Flet UI isn't imported by tests; `runcore`/`tagsio`/`cli` tests still pass).

- [ ] **Step 5: Commit**

```bash
git add docsort/gui.py
git commit -m "feat(gui): Flet app shell — dark theme + nav rail + routing"
```

---

### Task B3: Run view — controls + progress hero + counters + feed

Fill the Run section: folder picker, host field, model dropdown (auto + loaded models via
`available_models`), the run toggles, Run/Stop, and the live panel — progress hero (percent, `i/N`,
elapsed, ETA), counters (done / skipped / failed / tok-s), and a feed of completed files with tier +
tag. Wire to `runcore.RunController`, `parse_progress`, and the `file` events. Elapsed is a client-side
wall clock; `skipped` is tallied from `file` events with `skipped=True`. UI updates from the controller
thread are marshalled onto the Flet page via `page.run_thread` (Flet's UI-thread dispatch).

**Files:**
- Modify: `docsort/gui.py`
- Manual verify

- [ ] **Step 1: Add the Run view builder and wire it into routing**

Add this function to `docsort/gui.py` and change `select(0)` to render it:

```python
def _run_view(page):
    import time
    from .runcore import RunController, build_run_cmd

    streams, subjects, _types = load_tags(config.tags_path())
    cfg = config.load_config()

    folder = ft.TextField(label="Folder", color=FG, expand=True,
                          value=(cfg.get("last_folder") or ""))
    host = ft.TextField(label="Host (name or URL, blank = default)", color=FG, width=320)
    model = ft.Dropdown(label="Model", width=240, value="auto",
                        options=[ft.dropdown.Option("auto")])
    t_vision = ft.Switch(label="Vision", value=False)
    t_apply = ft.Switch(label="Apply (rename)", value=False)
    t_copy = ft.Switch(label="Work on a copy", value=False)
    t_misc = ft.Switch(label="Move 99UNS -> misc", value=True)
    t_skip = ft.Switch(label="Skip unknown", value=False)
    frontier = ft.Dropdown(label="Frontier", width=160, value="none",
                           options=[ft.dropdown.Option("none"), ft.dropdown.Option("claude")])

    pct = ft.Text("0%", size=42, weight=ft.FontWeight.W_500, color=FG)
    of_n = ft.Text("file 0 / 0", size=13, color=MUTED)
    elapsed = ft.Text("0:00", size=18, weight=ft.FontWeight.W_500, color=FG)
    remaining = ft.Text("~--", size=18, weight=ft.FontWeight.W_500, color=ACCENT)
    bar = ft.ProgressBar(value=0.0, color=ACCENT, bgcolor=PANEL2, height=10,
                         border_radius=6)
    c_done = ft.Text("0", size=20, color=OK, weight=ft.FontWeight.W_500)
    c_skip = ft.Text("0", size=20, color=FG, weight=ft.FontWeight.W_500)
    c_fail = ft.Text("0", size=20, color=FG, weight=ft.FontWeight.W_500)
    c_tps = ft.Text("0", size=20, color=FG, weight=ft.FontWeight.W_500)
    feed = ft.ListView(expand=True, spacing=2, padding=4, auto_scroll=True)
    status = ft.Text("idle", color=MUTED)

    state = {"t0": None, "skipped": 0}

    def refresh_models(_=None):
        api = config.resolve_api(cfg, host.value.strip() or None)
        try:
            ms = available_models(api)
        except Exception:
            ms = []
        model.options = [ft.dropdown.Option("auto")] + [ft.dropdown.Option(m) for m in ms]
        page.update()

    def metric(label, value_ctrl):
        return ft.Container(bgcolor=PANEL, border_radius=8, padding=10, expand=True,
                            content=ft.Column([ft.Text(label, size=11, color=MUTED),
                                               value_ctrl], spacing=2))

    def on_event(ev):
        kind, payload = ev
        def apply():
            if kind == "progress":
                bar.value = payload["pct"] / 100
                pct.value = f"{payload['pct']}%"
                of_n.value = f"file {payload['i']} / {payload['n']}"
                c_done.value = str(payload["done"])
                c_fail.value = str(payload["failed"])
                c_tps.value = payload["tps"] or "0"
                remaining.value = "~" + (payload["eta"] + "s" if payload["eta"] else "--")
            elif kind == "file":
                if payload["skipped"]:
                    state["skipped"] += 1
                    c_skip.value = str(state["skipped"])
                feed.controls.append(_feed_row(payload))
            elif kind == "log":
                pass
            elif kind == "done":
                status.value = "done"; status.color = OK
                run_btn.disabled = False; stop_btn.disabled = True
            page.update()
        page.run_thread(apply)

    ctrl = RunController(streams, subjects, on_event=on_event)

    def tick():
        # client-side elapsed clock while running
        import threading
        if ctrl.running and state["t0"]:
            s = int(time.time() - state["t0"])
            elapsed.value = f"{s // 60}:{s % 60:02d}"
            page.update()
            threading.Timer(1.0, tick).start()

    def start_run(_):
        f = folder.value.strip()
        if not os.path.isdir(f):
            status.value = f"not a folder: {f}"; status.color = FAIL; page.update(); return
        opts = {"host": host.value.strip(), "model": model.value, "vision": t_vision.value,
                "apply": t_apply.value, "copy": t_copy.value, "misc": t_misc.value,
                "skip_unknown": t_skip.value, "frontier": frontier.value}
        cmd = build_run_cmd(opts, python=sys.executable, folder=f)
        feed.controls.clear()
        state["t0"] = time.time(); state["skipped"] = 0
        for c in (pct,): c.value = "0%"
        bar.value = 0.0; c_done.value = c_fail.value = c_skip.value = "0"
        status.value = "running..."; status.color = ACCENT
        run_btn.disabled = True; stop_btn.disabled = False
        page.update()
        ctrl.start(cmd, cwd=PKG_PARENT)
        tick()

    run_btn = ft.FilledButton("Run", icon=ft.icons.PLAY_ARROW, on_click=start_run,
                              style=ft.ButtonStyle(bgcolor=ACCENT))
    stop_btn = ft.OutlinedButton("Stop", icon=ft.icons.STOP, disabled=True,
                                 on_click=lambda _: ctrl.stop())
    browse = ft.IconButton(ft.icons.FOLDER_OPEN, on_click=lambda _: _pick_folder(page, folder))
    host.on_blur = refresh_models
    refresh_models()

    hero = ft.Container(bgcolor=PANEL, border_radius=12, padding=18, content=ft.Column([
        ft.Row([ft.Row([pct, of_n], spacing=10, vertical_alignment=ft.CrossAxisAlignment.END),
                ft.Row([ft.Column([ft.Text("elapsed", size=11, color=MUTED), elapsed], spacing=2),
                        ft.Column([ft.Text("remaining", size=11, color=MUTED), remaining], spacing=2)],
                       spacing=22)],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bar,
        ft.Row([metric("done", c_done), metric("skipped", c_skip),
                metric("failed", c_fail), metric("tok/s", c_tps)], spacing=10),
    ], spacing=14))

    controls = ft.Column([
        ft.Row([folder, browse]),
        ft.Row([host, model, frontier], wrap=True),
        ft.Row([t_vision, t_apply, t_copy, t_misc, t_skip], wrap=True),
        ft.Row([run_btn, stop_btn, status]),
    ], spacing=10)

    return ft.Column([controls, hero,
                      ft.Container(bgcolor=PANEL, border_radius=12, padding=6, expand=True,
                                   content=feed)],
                     spacing=14, expand=True)


def _feed_row(p):
    return ft.Row([
        ft.Icon(ft.icons.CHECK, color=OK, size=16),
        ft.Text(p["name"], color=FG, size=13, expand=True, no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS),
        ft.Text(p["source"], color=MUTED, size=11),
        ft.Container(bgcolor=PANEL2, border_radius=6, padding=ft.padding.symmetric(2, 8),
                     content=ft.Text(p["tag"], color=ACCENT, size=11)),
    ], spacing=10)


def _pick_folder(page, field):
    def on_result(e):
        if e.path:
            field.value = e.path; page.update()
    fp = ft.FilePicker(on_result=on_result)
    page.overlay.append(fp); page.update()
    fp.get_directory_path()
```

Then in `_build`, replace the placeholder `select` so index 0 renders the run view:

```python
    run_view = _run_view(page)
    def select(idx):
        if idx == 0:
            content.content = run_view
        else:
            content.content = ft.Text(["", "Tags", "Folders", "Reports", "Stats"][idx],
                                      color=FG, size=18)
        page.update()
    content.content = run_view
```

- [ ] **Step 2: Manual verify against a real run**

Pre-req: LM Studio running with a Qwen-VL model loaded. Run:
`.venv\Scripts\python.exe -m docsort.gui`
Pick a small test folder (e.g. a copy of a few PDFs). Leave Apply OFF (dry-run). Click Run.
Expected: model dropdown lists loaded models; progress hero shows climbing %, `i/N`, elapsed clock and
ETA; counters move; the feed appends completed files each with a tier label and `[STREAM-SUBJECT]` tag;
Stop ends the run and re-enables Run.

- [ ] **Step 3: Verify Stop + dry-run safety**

Re-run, click Stop mid-way. Expected: subprocess ends, status shows done, no files renamed (Apply was
off). Confirm no `[..]` prefixes appeared in the folder.

- [ ] **Step 4: Run the suite (unchanged logic still green)**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docsort/gui.py
git commit -m "feat(gui): Run view — controls, progress hero, counters, file feed"
```

---

## Phase C — Carry-over views (parity with the old GUI)

### Task C1: Tags view (structured editor, reuses tagsio)

Recreate the structured tag editor in Flet: three columns (STREAMS / SUBJECTS / TYPES) read via
`tagsio.tag_block`, each row editable, add/delete buttons, Save rewrites via `tagsio.replace_block` to
`config.tags_path()`.

**Files:**
- Modify: `docsort/gui.py`
- Manual verify

- [ ] **Step 1: Add the Tags view builder**

```python
def _tags_view(page):
    from . import tagsio
    path = config.tags_path()
    text = open(path, encoding="utf-8").read()
    cols = {}
    col_row = ft.Row(expand=True, spacing=10)
    palette = {"STREAMS": ACCENT, "SUBJECTS": "#5b8cff", "TYPES": OK}

    def make_col(name):
        items = tagsio.tag_block(text, name)
        lv = ft.ListView(expand=True, spacing=4)
        fields = []
        def add_row(value=""):
            tf = ft.TextField(value=value, color=FG, dense=True, text_size=13)
            fields.append(tf)
            row = ft.Row([tf, ft.IconButton(ft.icons.DELETE, icon_color=FAIL,
                          on_click=lambda e, t=tf, r=None: remove(t))], spacing=4)
            tf._row = row
            lv.controls.append(row); fields_index[tf] = row
            page.update()
        def remove(tf):
            lv.controls.remove(fields_index[tf]); fields.remove(tf); page.update()
        fields_index = {}
        for it in items:
            add_row(it)
        cols[name] = fields
        return ft.Container(bgcolor=PANEL, border_radius=12, padding=10, expand=True,
            content=ft.Column([
                ft.Text(name, color=palette[name], weight=ft.FontWeight.W_500),
                lv,
                ft.TextButton("+ add", on_click=lambda e: add_row("")),
            ], spacing=8, expand=True))

    for n in ("STREAMS", "SUBJECTS", "TYPES"):
        col_row.controls.append(make_col(n))

    status = ft.Text("", color=OK)
    def save(_):
        new = text
        for n in ("STREAMS", "SUBJECTS", "TYPES"):
            lines = [tf.value.rstrip() for tf in cols[n] if tf.value.strip()]
            new = tagsio.replace_block(new, n, lines)
        try:
            open(path, "w", encoding="utf-8").write(new)
            status.value = "tags saved"; status.color = OK
        except Exception as e:
            status.value = f"save failed: {e}"; status.color = FAIL
        page.update()

    return ft.Column([
        ft.Text("First token on each line = the code.", color=MUTED, size=12),
        col_row,
        ft.Row([ft.FilledButton("Save", on_click=save, style=ft.ButtonStyle(bgcolor=ACCENT)),
                status]),
    ], spacing=12, expand=True)
```

Wire index 1 in `select` to `_tags_view(page)` (build once, reuse like the run view).

- [ ] **Step 2: Manual verify**

Run the GUI, open Tags. Expected: three columns populated from TAGS.md; add a row (e.g. `93TEST  a test`),
Save, reopen — it persists. Delete it, Save again.

- [ ] **Step 3: Confirm the engine sees the edit**

Run: `.venv\Scripts\python.exe -c "from docsort import cli, config; print('93TEST' in cli.load_tags(config.tags_path())[1])"`
Expected: prints `True` while the row exists, `False` after deletion.

- [ ] **Step 4: Suite green**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docsort/gui.py
git commit -m "feat(gui): Tags view — structured editor over tagsio"
```

---

### Task C2: Folders view (exclude / include → config.json)

Port the Folders dialog (gui.py:352) to a Flet view: two lists (Exclude / Include), add-folder (folder
picker) and delete per list, Save writes `exclude` / `include` arrays into `config.config_path()` as JSON
(same shape the engine already reads).

**Files:**
- Modify: `docsort/gui.py`
- Manual verify

- [ ] **Step 1: Add the Folders view builder**

```python
def _folders_view(page):
    import json
    cfgp = config.config_path()
    try:
        data = json.load(open(cfgp, encoding="utf-8"))
    except Exception:
        data = {}

    def make_list(key, label, colour):
        lv = ft.ListView(expand=True, spacing=2)
        items = list(data.get(key) or [])
        def render():
            lv.controls.clear()
            for it in list(items):
                lv.controls.append(ft.Row([
                    ft.Text(it, color=FG, size=12, expand=True, no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.IconButton(ft.icons.DELETE, icon_color=FAIL,
                                  on_click=lambda e, v=it: (items.remove(v), render(), page.update())),
                ], spacing=4))
        def add(_):
            def on_result(e):
                if e.path:
                    items.append(e.path); render(); page.update()
            fp = ft.FilePicker(on_result=on_result)
            page.overlay.append(fp); page.update(); fp.get_directory_path()
        render()
        box = ft.Container(bgcolor=PANEL, border_radius=12, padding=10, expand=True,
            content=ft.Column([ft.Text(label, color=colour, weight=ft.FontWeight.W_500),
                               lv, ft.TextButton("+ add folder", on_click=add)],
                              spacing=8, expand=True))
        return box, items

    ex_box, ex_items = make_list("exclude", "Exclude", FAIL)
    in_box, in_items = make_list("include", "Include", OK)
    status = ft.Text("", color=OK)

    def save(_):
        data["exclude"] = list(ex_items); data["include"] = list(in_items)
        try:
            json.dump(data, open(cfgp, "w", encoding="utf-8"), indent=2)
            status.value = "folders saved"; status.color = OK
        except Exception as e:
            status.value = f"save failed: {e}"; status.color = FAIL
        page.update()

    return ft.Column([
        ft.Text("Exclude = skip these. Include = if non-empty, ONLY these.", color=MUTED, size=12),
        ft.Row([ex_box, in_box], expand=True, spacing=10),
        ft.Row([ft.FilledButton("Save", on_click=save, style=ft.ButtonStyle(bgcolor=ACCENT)), status]),
    ], spacing=12, expand=True)
```

Wire index 2 in `select` to `_folders_view(page)`.

- [ ] **Step 2: Manual verify**

Open Folders, add an exclude path, Save. Inspect: `.venv\Scripts\python.exe -c "import json,docsort.config as c; print(json.load(open(c.config_path()))['exclude'])"`
Expected: the path you added is listed.

- [ ] **Step 3: Suite green**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add docsort/gui.py
git commit -m "feat(gui): Folders view — exclude/include lists to config.json"
```

---

### Task C3: Reports + Stats views

Reports: read `DOCSORT-REPORT.md` from the run folder or `<folder>COPY` (matches gui.py:335) and show it
in a scrollable monospace text. Stats: render lifetime totals from the global index using the existing
`cli.lifetime_stats`-equivalent path. The CLI prints stats (cli.py:388-398) but has no return value, so
read the index file directly for display.

**Files:**
- Modify: `docsort/gui.py`
- Manual verify

- [ ] **Step 1: Add Reports + Stats view builders**

```python
def _reports_view(page, folder_getter):
    body = ft.Text("", selectable=True, color=FG, font_family="Consolas", size=12)
    info = ft.Text("", color=MUTED, size=12)
    def load(_=None):
        folder = (folder_getter() or "").strip()
        cands = [os.path.join(folder, "DOCSORT-REPORT.md"),
                 os.path.join(folder + "COPY", "DOCSORT-REPORT.md")]
        path = next((p for p in cands if os.path.isfile(p)), None)
        if not path:
            info.value = "No DOCSORT-REPORT.md yet — run a tagging pass first."
            body.value = ""
        else:
            info.value = path
            body.value = open(path, encoding="utf-8").read()
        page.update()
    return ft.Column([ft.Row([ft.FilledButton("Load report", on_click=load), info]),
                      ft.Container(bgcolor=PANEL, border_radius=12, padding=12, expand=True,
                                   content=ft.Column([body], scroll=ft.ScrollMode.AUTO, expand=True))],
                     spacing=12, expand=True)


def _stats_view(page):
    import json
    idx = os.path.join(config.user_dir(), "index.jsonl")
    lines = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
    if not os.path.isfile(idx):
        lines.controls.append(ft.Text("No runs yet — run a tagging pass first.", color=MUTED))
    else:
        runs = [json.loads(l) for l in open(idx, encoding="utf-8") if l.strip()]
        files = sum(int(r.get("files", 0) or 0) for r in runs)
        lines.controls.append(ft.Text(f"{len(runs)} runs · {files} files tagged",
                                       color=FG, size=16, weight=ft.FontWeight.W_500))
    return ft.Column([ft.Text("Lifetime stats", color=MUTED, size=12), lines],
                     spacing=12, expand=True)
```

Wire index 3 to `_reports_view(page, lambda: folder.value)` (capture the run view's folder field — pass it
in, or read the saved `last_folder` from config) and index 4 to `_stats_view(page)`.

> NOTE: confirm the global index filename via `config.user_dir()` + the name written in
> `cli.py` around line 388 (`index.jsonl`). If the per-run record key for file count differs from
> `files`, read the actual key used when the index record is appended and use that here.

- [ ] **Step 2: Manual verify**

After a real dry-run/apply pass that wrote a report: open Reports → Load report → the markdown shows.
Open Stats → lifetime line shows run/file totals.

- [ ] **Step 3: Suite green**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add docsort/gui.py
git commit -m "feat(gui): Reports + Stats views"
```

---

### Task C4: Verbose collapsible live-log pane (full parity)

The old GUI had a raw live-log pane. Restore it for parity, but collapsible (collapsed by default so it
doesn't crowd the run view) and verbose (every line the engine emits — `log` events plus a readable echo
of progress/file events). Wire the Run view's `on_event` `log` branch into it.

**Files:**
- Modify: `docsort/gui.py`
- Manual verify

- [ ] **Step 1: Add a log pane to the Run view and surface every event**

In `_run_view`, add a log control and an expandable container, and append to it from `on_event`:

```python
    log = ft.ListView(expand=True, spacing=1, padding=6, auto_scroll=True)

    def log_line(text, color=MUTED):
        log.controls.append(ft.Text(text.rstrip("\n"), color=color, size=11,
                                    font_family="Consolas", selectable=True))
```

Replace the `on_event` body's branches so every event also echoes into the verbose log:

```python
    def on_event(ev):
        kind, payload = ev
        def apply():
            if kind == "progress":
                bar.value = payload["pct"] / 100
                pct.value = f"{payload['pct']}%"
                of_n.value = f"file {payload['i']} / {payload['n']}"
                c_done.value = str(payload["done"])
                c_fail.value = str(payload["failed"])
                c_tps.value = payload["tps"] or "0"
                remaining.value = "~" + (payload["eta"] + "s" if payload["eta"] else "--")
                log_line(f"[progress] {payload['i']}/{payload['n']} "
                         f"done={payload['done']} failed={payload['failed']} "
                         f"tps={payload['tps']} eta={payload['eta']}s")
            elif kind == "file":
                if payload["skipped"]:
                    state["skipped"] += 1
                    c_skip.value = str(state["skipped"])
                feed.controls.append(_feed_row(payload))
                log_line(f"{payload['tag']} {payload['source']:14} {payload['name']}", color=FG)
            elif kind == "log":
                log_line(payload, color=MUTED)
            elif kind == "done":
                status.value = "done"; status.color = OK
                run_btn.disabled = False; stop_btn.disabled = True
                log_line("[done]", color=OK)
            page.update()
        page.run_thread(apply)
```

Wrap the log in a collapsible `ExpansionTile` (collapsed by default) and append it to the returned
`Column` after the feed container:

```python
    log_panel = ft.ExpansionTile(
        title=ft.Text("Log (verbose)", color=MUTED, size=12),
        initially_expanded=False,
        controls=[ft.Container(bgcolor="#15151f", border_radius=8, padding=4,
                               height=180, content=log)],
    )
```

Add `log_panel` to the final layout:

```python
    return ft.Column([controls, hero,
                      ft.Container(bgcolor=PANEL, border_radius=12, padding=6, expand=True,
                                   content=feed),
                      log_panel],
                     spacing=14, expand=True)
```

Also clear the log at the start of a run — in `start_run`, alongside `feed.controls.clear()`:

```python
        log.controls.clear()
```

- [ ] **Step 2: Manual verify**

Run the GUI, start a pass. Expected: the run view is uncluttered with the log collapsed; expanding
"Log (verbose)" shows every engine line live (progress echoes, per-file rows, model/server notices),
auto-scrolling; it clears on each new run.

- [ ] **Step 3: Suite green**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add docsort/gui.py
git commit -m "feat(gui): verbose collapsible live-log pane (full parity)"
```

---

## Phase D — Packaging, version, changelog

### Task D1: Optional `[gui]` dependency + version bump + changelog

**Files:**
- Modify: `pyproject.toml`, `docsort/__init__.py`, `CHANGELOG.md`

- [ ] **Step 1: Edit `pyproject.toml`**

Set `version = "0.11.0"` and add to `[project.optional-dependencies]`:

```toml
gui = ["flet>=0.21"]
all = ["python-docx>=1.1", "python-pptx>=0.6", "pywin32>=306; sys_platform=='win32'", "flet>=0.21"]
```

- [ ] **Step 2: Bump `docsort/__init__.py`**

```python
__version__ = "0.11.0"
```

- [ ] **Step 3: Add the CHANGELOG entry (top, above 0.10.2)**

```markdown
## [0.11.0] — 2026-06-XX
### Changed
- **GUI rebuilt on Flet** (Python) — modern Discord-like dark UI with a left nav rail
  (Run / Tags / Folders / Reports / Stats), minimal animations, and a run view that
  foregrounds progress %, elapsed + ETA, throughput, done/skipped/failed counters, a
  live per-file feed with each file's tier and `[STREAM-SUBJECT]` tag, and a verbose
  collapsible live-log pane. Replaces the Tkinter front end. **No engine or behaviour
  change** — the UI still drives the existing `docsort` CLI as a subprocess.
- GUI is now an optional extra: `pip install "docsort[gui]"` (the `flet` dependency).
### Added
- `docsort/runcore.py` — UI-agnostic run core (PROGRESS/result-row parsing, command
  builder, threaded `RunController`); fully unit-tested.
- `docsort/tagsio.py` — TAGS.md block read/rewrite, decoupled from any UI.
```

- [ ] **Step 4: Verify install + smoke test**

Run: `.venv\Scripts\python.exe -m pip install -e ".[gui]" --no-deps && .venv\Scripts\python.exe -c "import docsort; print(docsort.__version__)"`
Expected: prints `0.11.0`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml docsort/__init__.py CHANGELOG.md
git commit -m "build: v0.11.0 — flet [gui] extra, version bump, changelog"
```

---

### Task D2: Release workflow builds the Flet exe

The current `release.yml` builds the GUI with PyInstaller (`pyinstaller --onefile --windowed --name
docsort-gui ...`). Flet apps package with `flet pack`, which wraps PyInstaller with the right Flutter
assets. Update the GUI build step; leave the CLI exe step as-is.

**Files:**
- Modify: `.github/workflows/release.yml`

- [ ] **Step 1: Inspect the current GUI build step**

Run: `grep -n "docsort-gui\|pyinstaller\|flet" .github/workflows/release.yml`
Expected: shows the existing `pyinstaller ... docsort-gui` line.

- [ ] **Step 2: Replace the GUI build step**

Install the gui extra before packing, and pack with flet:

```yaml
      - name: Install deps
        run: pip install ".[gui]" pyinstaller flet

      - name: Build GUI exe (Flet)
        run: flet pack scripts/run_gui.py --name docsort-gui --product-name docsort
```

Keep the existing CLI `pyinstaller ... docsort.exe` step and the release-upload step unchanged.

- [ ] **Step 3: Verify the build locally (mirrors the runner)**

Run: `.venv\Scripts\python.exe -m flet pack scripts/run_gui.py --name docsort-gui`
Expected: `dist/docsort-gui.exe` is produced and launches the Flet GUI on double-click.

> NOTE: confirm `scripts/run_gui.py` still imports `docsort.gui:main` (it should — the entry
> point is unchanged). If `flet pack` flags missing Flutter assets, add `--add-data` per the
> Flet packaging docs; do not change the engine.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: build the GUI exe with flet pack for v0.11.0"
```

---

## Final verification (before tagging the release)

- [ ] Full suite: `.venv\Scripts\python.exe -m pytest -q` → all pass (existing + new `test_runcore.py`).
- [ ] CLI unchanged: `.venv\Scripts\python.exe -m docsort.cli --help` runs; a dry-run on a test folder
      behaves exactly as in v0.10.2 (the engine wasn't touched).
- [ ] GUI parity walk-through: Run (dry-run + apply on a throwaway copy), Tags (add/save/delete), Folders
      (add/save), Reports (load), Stats (totals) — each works.
- [ ] CLI-only install still works without flet: in a clean venv, `pip install .` then
      `docsort --help` succeeds; `docsort-gui` prints the "install docsort[gui]" message.

When green, the user tags `v0.11.0` (the release workflow builds both exes).

## Out of scope (tracked in docs/ROADMAP.md — do NOT build here)
- Background processing + system tray (and any "now reading <file>" engine event the live tray/run
  indicator would want). The run view shows *completed* files only, by design.
- Single unified Windows package (beyond the two exes).
- Taxonomy Generator dialog, transient single-retry, in-process engine boundary.
