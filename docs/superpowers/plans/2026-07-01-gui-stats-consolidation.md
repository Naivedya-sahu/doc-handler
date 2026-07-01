# v0.12.3 GUI Tab Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shrink the Flet GUI's nav rail from 5 tabs to 3 (Run/Tags/Stats), move the 5 run-option
switches from Run to Tags, fold Folders+Reports into Stats as sub-sections, and flip the
Skip-unknown/Misc defaults (skip becomes default-on, misc-quarantine becomes opt-in).

**Architecture:** Lift the 5 `ft.Switch` controls out of `_run_view`'s closure into a new
`_build_toggles()` helper called once in `_build()`. Pass the same dict of switch objects into both
`_run_view(page, toggles)` (reads `.value` to build CLI opts) and `_tags_view(page, toggles)`
(renders them). `_stats_view` gains a `folder_getter` param and embeds `_folders_view`/
`_reports_view`'s existing output as sub-sections — those two functions are unchanged. `_build()`'s
nav rail drops to 3 destinations and `_make_view`'s index mapping updates accordingly.

**Tech Stack:** Python, Flet 0.85.3 (GUI), pytest (existing `.venv`). No new dependencies, no
`cli.py`/`runcore.py` changes — this is `gui.py` + a new `tests/test_gui.py` + docs.

---

## Before you start

Source file under change: [`docsort/gui.py`](../../../docsort/gui.py) (609 lines). Read it once before
starting — every task below quotes the exact current text it replaces.

Run tests with: `.venv\Scripts\python.exe -m pytest -q` (Windows venv path, matches HANDOFF.md §2).
Flet is installed in this dev venv, so `tests/test_gui.py` will actually run here — but CI
(`.github/workflows/ci.yml`) does `pip install .` with no `[gui]` extra, so flet is **not** installed
there. Every test in the new file must be skippable when flet is absent — handled by
`pytest.importorskip("flet")` at the top of the file (Task 1, Step 1).

Constructing Flet controls (`ft.Switch`, `ft.Column`, etc.) standalone — without a live
`ft.Page`/session — works fine; only `ft.Page()` itself requires a `Session` you don't have in
tests. Confirmed by hand before writing this plan. Functions under test take a `page` argument they
only use for `page.services.append(...)` (FilePicker registration) — a duck-typed stub covers that.
The stub used throughout:

```python
import types

def _stub_page():
    p = types.SimpleNamespace()
    p.services = []
    p.window = types.SimpleNamespace()
    p.added = []
    p.add = lambda *a, **k: p.added.append(a)
    p.update = lambda *a, **k: None
    p.run_task = lambda *a, **k: None
    p.run_thread = lambda *a, **k: None
    return p
```

A second helper recursively walks a control tree (Flet controls expose children via `.controls`
(list-valued, e.g. `Column`/`Row`/`ListView`) or `.content` (single control, e.g. `Container` — or
occasionally a raw string, e.g. `FilledButton.content`)):

```python
def _walk(control):
    yield control
    for attr in ("controls", "content"):
        val = getattr(control, attr, None)
        if val is None:
            continue
        if isinstance(val, (list, tuple)):
            for c in val:
                yield from _walk(c)
        else:
            yield from _walk(val)
```

Both helpers go at the top of the new `tests/test_gui.py`, written once in Task 1.

---

### Task 1: `_build_toggles()` + `_build_opts()` helpers, with the default flip

**Files:**
- Create: `tests/test_gui.py`
- Modify: `docsort/gui.py:84` (insert new functions between `_metric` and `_run_view`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gui.py`:

```python
import types

import pytest

flet = pytest.importorskip("flet")
import flet as ft  # noqa: E402

from docsort import gui  # noqa: E402


def _stub_page():
    p = types.SimpleNamespace()
    p.services = []
    p.window = types.SimpleNamespace()
    p.added = []
    p.add = lambda *a, **k: p.added.append(a)
    p.update = lambda *a, **k: None
    p.run_task = lambda *a, **k: None
    p.run_thread = lambda *a, **k: None
    return p


def _walk(control):
    yield control
    for attr in ("controls", "content"):
        val = getattr(control, attr, None)
        if val is None:
            continue
        if isinstance(val, (list, tuple)):
            for c in val:
                yield from _walk(c)
        else:
            yield from _walk(val)


def test_build_toggles_keys_and_defaults():
    toggles = gui._build_toggles()
    assert set(toggles) == {"vision", "apply", "copy", "misc", "skip"}
    assert all(isinstance(s, ft.Switch) for s in toggles.values())
    assert toggles["vision"].value is False
    assert toggles["apply"].value is False
    assert toggles["copy"].value is False
    assert toggles["misc"].value is False   # flipped: misc-quarantine now opt-in
    assert toggles["skip"].value is True    # flipped: skip-unknown now default


def test_build_opts_reads_toggle_values():
    toggles = gui._build_toggles()
    toggles["vision"].value = True
    toggles["skip"].value = False
    host = types.SimpleNamespace(value="  myhost  ")
    model = types.SimpleNamespace(value="auto")
    frontier = types.SimpleNamespace(value="claude")
    opts = gui._build_opts(host, model, toggles, frontier)
    assert opts == {
        "host": "myhost",
        "model": "auto",
        "vision": True,
        "apply": False,
        "copy": False,
        "misc": False,
        "skip_unknown": False,
        "frontier": "claude",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py -v`
Expected: both tests FAIL with `AttributeError: module 'docsort.gui' has no attribute '_build_toggles'`

- [ ] **Step 3: Implement `_build_toggles()` and `_build_opts()`**

In `docsort/gui.py`, find this existing text (the end of `_metric`, just before `_run_view`):

```python
def _metric(label: str, value_ctrl: "ft.Text") -> "ft.Container":
    return ft.Container(
        bgcolor=PANEL, border_radius=8, padding=10, expand=True,
        content=ft.Column([ft.Text(label, size=11, color=MUTED), value_ctrl], spacing=2),
    )


def _run_view(page: "ft.Page") -> "ft.Control":
```

Replace it with:

```python
def _metric(label: str, value_ctrl: "ft.Text") -> "ft.Container":
    return ft.Container(
        bgcolor=PANEL, border_radius=8, padding=10, expand=True,
        content=ft.Column([ft.Text(label, size=11, color=MUTED), value_ctrl], spacing=2),
    )


def _build_toggles() -> dict:
    """The 5 run-option switches, built once and shared between the Run view
    (reads .value to build CLI opts) and the Tags view (renders them) so a
    toggle flipped in Tags affects the very next Run."""
    return {
        "vision": ft.Switch(label="Vision", value=False),
        "apply": ft.Switch(label="Apply (rename)", value=False),
        "copy": ft.Switch(label="Work on a copy", value=False),
        "misc": ft.Switch(label="Move 99UNS → misc", value=False),
        "skip": ft.Switch(label="Skip unknown", value=True),
    }


def _build_opts(host, model, toggles: dict, frontier) -> dict:
    """Assemble the docsort CLI opts dict from the Run/Tags controls."""
    return {
        "host": host.value.strip(),
        "model": model.value,
        "vision": toggles["vision"].value,
        "apply": toggles["apply"].value,
        "copy": toggles["copy"].value,
        "misc": toggles["misc"].value,
        "skip_unknown": toggles["skip"].value,
        "frontier": frontier.value,
    }


def _run_view(page: "ft.Page") -> "ft.Control":
```

(`_run_view`'s signature changes in Task 2 — leave it as `_run_view(page)` for now so this task's
diff is isolated to the new functions only.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py -v`
Expected: `test_build_toggles_keys_and_defaults PASSED`, `test_build_opts_reads_toggle_values PASSED`

- [ ] **Step 5: Commit**

```bash
git add docsort/gui.py tests/test_gui.py
git commit -m "feat(gui): add _build_toggles/_build_opts helpers, flip 99UNS defaults

skip-unknown now defaults on, misc-quarantine now defaults off.
Helpers not yet wired into _run_view/_tags_view (next commits)."
```

---

### Task 2: Move the 5 switches out of `_run_view`

**Files:**
- Modify: `docsort/gui.py` (`_run_view` function — signature, switch creation, opts-building, layout)
- Test: `tests/test_gui.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gui.py`:

```python
def test_run_view_takes_shared_toggles_and_has_no_inline_switches():
    page = _stub_page()
    toggles = gui._build_toggles()
    view = gui._run_view(page, toggles)
    found_switches = [c for c in _walk(view) if isinstance(c, ft.Switch)]
    assert found_switches == [], (
        "Run view should no longer render the 5 toggle switches inline — "
        "they moved to the Tags view"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py::test_run_view_takes_shared_toggles_and_has_no_inline_switches -v`
Expected: FAIL with `TypeError: _run_view() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Update `_run_view`'s signature, switch creation, and opts-building**

Find this text in `docsort/gui.py` (current `_run_view` opening):

```python
def _run_view(page: "ft.Page") -> "ft.Control":
    """Build the Run view: controls, progress hero, counters, live feed."""
    streams, subjects, _types = load_tags(config.tags_path())
    cfg = config.load_config()
```

Replace with:

```python
def _run_view(page: "ft.Page", toggles: dict) -> "ft.Control":
    """Build the Run view: controls, progress hero, counters, live feed.

    `toggles` is the shared dict from `_build_toggles()` — same objects the
    Tags view renders, so this just reads `.value` off them."""
    streams, subjects, _types = load_tags(config.tags_path())
    cfg = config.load_config()
```

Find this text (the 5 switch constructions, currently right after the `frontier` dropdown):

```python
    t_vision = ft.Switch(label="Vision", value=False)
    t_apply = ft.Switch(label="Apply (rename)", value=False)
    t_copy = ft.Switch(label="Work on a copy", value=False)
    t_misc = ft.Switch(label="Move 99UNS → misc", value=True)
    t_skip = ft.Switch(label="Skip unknown", value=False)
```

Replace with:

```python
    t_vision = toggles["vision"]
    t_apply = toggles["apply"]
    t_copy = toggles["copy"]
    t_misc = toggles["misc"]
    t_skip = toggles["skip"]
```

(Every later reference to `t_vision`/`t_apply`/`t_copy`/`t_misc`/`t_skip` in this function —
`apply_audited`'s `--no-misc`/`--skip-unknown` checks, the layout row — keeps working unchanged
since the local names still exist, now aliasing the shared objects instead of owning new ones.)

Find this text inside `start_run`:

```python
        opts = {"host": host.value.strip(), "model": model.value, "vision": t_vision.value,
                "apply": t_apply.value, "copy": t_copy.value, "misc": t_misc.value,
                "skip_unknown": t_skip.value, "frontier": frontier.value}
```

Replace with:

```python
        opts = _build_opts(host, model, toggles, frontier)
```

Find this text in the `controls` layout `Column` near the bottom of `_run_view`:

```python
    controls = ft.Column(
        [
            ft.Row([folder, browse]),
            ft.Row([host, model, refresh, frontier], wrap=True, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([t_vision, t_apply, t_copy, t_misc, t_skip], wrap=True),
            ft.Row([run_btn, apply_btn, stop_btn, status]),
        ],
        spacing=10,
    )
```

Replace with:

```python
    controls = ft.Column(
        [
            ft.Row([folder, browse]),
            ft.Row([host, model, refresh, frontier], wrap=True, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([run_btn, apply_btn, stop_btn, status]),
        ],
        spacing=10,
    )
```

(The toggle row is gone — those controls render in Tags now, Task 3.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py -v`
Expected: all 3 tests so far PASS

- [ ] **Step 5: Commit**

```bash
git add docsort/gui.py tests/test_gui.py
git commit -m "refactor(gui): _run_view reads shared toggles instead of owning them

Run view no longer renders the 5 switches inline. _build() (Task 5)
still calls the old _run_view(page) signature for one more commit —
that's fixed next."
```

---

### Task 3: Render the toggles in `_tags_view`

**Files:**
- Modify: `docsort/gui.py` (`_tags_view` function — signature, return layout)
- Test: `tests/test_gui.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gui.py`:

```python
def test_tags_view_renders_the_shared_toggle_objects():
    page = _stub_page()
    toggles = gui._build_toggles()
    view = gui._tags_view(page, toggles)
    found = list(_walk(view))
    for key, switch in toggles.items():
        assert any(c is switch for c in found), f"toggle '{key}' not found in Tags view tree"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py::test_tags_view_renders_the_shared_toggle_objects -v`
Expected: FAIL with `TypeError: _tags_view() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Update `_tags_view`'s signature and return layout**

Find this text in `docsort/gui.py`:

```python
def _tags_view(page: "ft.Page") -> "ft.Control":
    path = config.tags_path()
```

Replace with:

```python
def _tags_view(page: "ft.Page", toggles: dict) -> "ft.Control":
    path = config.tags_path()
```

Find this text (the function's `return` at the end of `_tags_view`):

```python
    return ft.Column(
        [ft.Text("First token on each line = the code.", color=MUTED, size=12),
         col_row,
         ft.Row([ft.FilledButton("Save", on_click=save, style=ft.ButtonStyle(bgcolor=ACCENT)), status])],
        spacing=12, expand=True)
```

Replace with:

```python
    toggle_row = ft.Row(
        [toggles["vision"], toggles["apply"], toggles["copy"], toggles["misc"], toggles["skip"]],
        wrap=True,
    )
    return ft.Column(
        [ft.Text("First token on each line = the code.", color=MUTED, size=12),
         col_row,
         ft.Text("Run options", color=MUTED, size=12),
         toggle_row,
         ft.Row([ft.FilledButton("Save", on_click=save, style=ft.ButtonStyle(bgcolor=ACCENT)), status])],
        spacing=12, expand=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py -v`
Expected: all 4 tests so far PASS

- [ ] **Step 5: Commit**

```bash
git add docsort/gui.py tests/test_gui.py
git commit -m "feat(gui): render run-option toggles in the Tags tab"
```

---

### Task 4: Fold Folders + Reports into Stats

**Files:**
- Modify: `docsort/gui.py` (`_stats_view` function — signature, return layout)
- Test: `tests/test_gui.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gui.py`:

```python
def test_stats_view_embeds_folders_and_reports_sections():
    page = _stub_page()
    folder_getter = lambda: ""
    view = gui._stats_view(page, folder_getter)
    found = list(_walk(view))
    texts = [c.value for c in found if isinstance(c, ft.Text) and c.value]
    assert "Folders" in texts
    assert "Reports" in texts
    assert "Exclude" in texts   # from _folders_view
    buttons = [c.content for c in found if isinstance(c, ft.FilledButton)]
    assert "Load report" in buttons   # from _reports_view
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py::test_stats_view_embeds_folders_and_reports_sections -v`
Expected: FAIL with `TypeError: _stats_view() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Update `_stats_view`'s signature and return layout**

Find this text in `docsort/gui.py`:

```python
def _stats_view(page: "ft.Page") -> "ft.Control":
    import json
    import collections
    idx = os.path.join(config.user_dir(), "index.jsonl")
```

Replace with:

```python
def _stats_view(page: "ft.Page", folder_getter) -> "ft.Control":
    import json
    import collections
    idx = os.path.join(config.user_dir(), "index.jsonl")
```

Find this text (the function's `return` at the end of `_stats_view`):

```python
    return ft.Column([ft.Text("Lifetime stats", color=MUTED, size=12), lines],
                     spacing=12, expand=True)
```

Replace with:

```python
    return ft.Column(
        [ft.Text("Lifetime stats", color=MUTED, size=12), lines,
         ft.Divider(color=PANEL2),
         ft.Text("Folders", color=MUTED, size=12), _folders_view(page),
         ft.Divider(color=PANEL2),
         ft.Text("Reports", color=MUTED, size=12), _reports_view(page, folder_getter)],
        spacing=12, expand=True, scroll=ft.ScrollMode.AUTO)
```

`_folders_view` and `_reports_view` themselves are unchanged — only where they're mounted moves.
Note for the human visual smoke-test (HANDOFF.md §9 — this composition can't be checked headlessly):
both sub-views were built as standalone `expand=True` columns; nested inside Stats' own scrolling
column they may need a fixed-height wrapper if the layout looks squashed. Flag it, don't guess a fix
blind — confirm on screen first.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py -v`
Expected: all 5 tests so far PASS

- [ ] **Step 5: Commit**

```bash
git add docsort/gui.py tests/test_gui.py
git commit -m "feat(gui): fold Folders + Reports into Stats as sub-sections"
```

---

### Task 5: Wire it together in `_build()` — 3-tab nav rail

**Files:**
- Modify: `docsort/gui.py` (`_build` function, `_SECTION_NAMES` constant)
- Test: `tests/test_gui.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gui.py`:

```python
def test_build_produces_three_tab_nav_rail():
    page = _stub_page()
    gui._build(page)
    assert page.added, "page.add was never called"
    row = page.added[0][0]
    rail = row.controls[0]
    assert [d.label for d in rail.destinations] == ["Run", "Tags", "Stats"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py::test_build_produces_three_tab_nav_rail -v`
Expected: FAIL — `_build` still calls `_run_view(page)` (missing `toggles` arg, Task 2 changed the
signature) → `TypeError: _run_view() missing 1 required positional argument: 'toggles'`

- [ ] **Step 3: Update `_build()`**

Find this text in `docsort/gui.py`:

```python
    # Build the Run view once; other views are built lazily on first visit.
    run_view = _run_view(page)
    content = ft.Container(expand=True, padding=18, content=run_view)
    cache: dict = {0: run_view}

    def _folder_value() -> str:
        fld = getattr(run_view, "data", None)
        return fld.value if fld is not None else ""

    def _make_view(idx: int) -> "ft.Control":
        if idx == 1:
            return _tags_view(page)
        if idx == 2:
            return _folders_view(page)
        if idx == 3:
            return _reports_view(page, _folder_value)
        if idx == 4:
            return _stats_view(page)
        return run_view
```

Replace with:

```python
    # Run-option switches, built once and shared between Run (reads .value)
    # and Tags (renders them) so toggling in Tags affects the next Run.
    toggles = _build_toggles()

    # Build the Run view once; other views are built lazily on first visit.
    run_view = _run_view(page, toggles)
    content = ft.Container(expand=True, padding=18, content=run_view)
    cache: dict = {0: run_view}

    def _folder_value() -> str:
        fld = getattr(run_view, "data", None)
        return fld.value if fld is not None else ""

    def _make_view(idx: int) -> "ft.Control":
        if idx == 1:
            return _tags_view(page, toggles)
        if idx == 2:
            return _stats_view(page, _folder_value)
        return run_view
```

Find this text:

```python
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.PLAY_ARROW, label="Run"),
            ft.NavigationRailDestination(icon=ft.Icons.LABEL, label="Tags"),
            ft.NavigationRailDestination(icon=ft.Icons.FOLDER_OPEN, label="Folders"),
            ft.NavigationRailDestination(icon=ft.Icons.DESCRIPTION, label="Reports"),
            ft.NavigationRailDestination(icon=ft.Icons.BAR_CHART, label="Stats"),
        ],
```

Replace with:

```python
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.PLAY_ARROW, label="Run"),
            ft.NavigationRailDestination(icon=ft.Icons.LABEL, label="Tags"),
            ft.NavigationRailDestination(icon=ft.Icons.BAR_CHART, label="Stats"),
        ],
```

Find this text near the top of the file:

```python
_SECTION_NAMES = ["Run", "Tags", "Folders", "Reports", "Stats"]
```

Replace with:

```python
_SECTION_NAMES = ["Run", "Tags", "Stats"]
```

- [ ] **Step 4: Run the full test file to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gui.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add docsort/gui.py tests/test_gui.py
git commit -m "feat(gui): wire 3-tab nav rail (Run/Tags/Stats) into _build()

App is internally consistent again as of this commit — every prior
commit in this series left _build() calling stale signatures."
```

---

### Task 6: Version bump + docs sync

**Files:**
- Modify: `docsort/__init__.py`
- Modify: `pyproject.toml`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/HANDOFF.md`
- Modify: `docs/GUIDE.md`

- [ ] **Step 1: Bump the version**

In `docsort/__init__.py`, find:

```python
__version__ = "0.12.1"
```

Replace with:

```python
__version__ = "0.12.3"
```

In `pyproject.toml`, find:

```
version = "0.12.1"
```

Replace with:

```
version = "0.12.3"
```

- [ ] **Step 2: Add a CHANGELOG entry**

In `docs/CHANGELOG.md`, find the top of the file:

```
# Changelog — docsort

All notable changes. Newest on top.

## [0.12.1] — 2026-06-30
```

Replace with (adjust the date if you're running this on a different day):

```
# Changelog — docsort

All notable changes. Newest on top.

## [0.12.3] — 2026-07-01
### Changed
- **GUI nav rail: 5 tabs → 3** (Run / Tags / Stats). Folders and Reports are no longer standalone
  tabs — their content now renders as sub-sections inside Stats.
- **Run-option toggles moved from Run to Tags.** Vision / Apply(rename) / Work-on-a-copy / Misc→ /
  Skip-unknown now render on the Tags tab, below the tag-vocabulary editor. Run keeps just the
  folder picker, host/model/frontier, and the Run/Apply-audited/Stop buttons.
- **`99UNS` (unknown) defaults flipped.** Skip-unknown now defaults **on** (unsure files are left
  untouched by default); Misc-quarantine now defaults **off** (opt-in). Previously the reverse.

## [0.12.1] — 2026-06-30
```

- [ ] **Step 3: Update HANDOFF.md**

In `docs/HANDOFF.md`, find:

```
> Single-file, self-contained handoff for the next session. Date: **2026-06-30**.
> Current version: **v0.12.0** (released — `v0.12.0` tag pushed; GitHub release published with
> `docsort-gui.exe` + `docsort.exe`).
```

Replace with:

```
> Single-file, self-contained handoff for the next session. Date: **2026-07-01**.
> Current version: **v0.12.3** (GUI tab consolidation — see CHANGELOG; tag/release this once the
> human visual smoke-test in §9 has passed).
```

Find:

```
Two surfaces: **CLI** (`docsort`) and a modern Flet GUI (`docsort-gui`) — as of v0.11.0 a Flet
(Python/Flutter) app, Discord-like dark, nav rail: Run / Tags / Folders / Reports / Stats.
```

Replace with:

```
Two surfaces: **CLI** (`docsort`) and a modern Flet GUI (`docsort-gui`) — as of v0.11.0 a Flet
(Python/Flutter) app, Discord-like dark, nav rail: Run / Tags / Stats (Folders + Reports live inside
Stats as sub-sections since v0.12.3; the 5 run-option toggles live on the Tags tab).
```

Find:

```
**GUI (Flet):** folder picker, host + live model picker (+ refresh), toggles (copy/misc/vision/apply/
skip-unknown), frontier dropdown, **Run / Apply audited / Stop**, progress hero (% · file i/N · elapsed ·
ETA), counters (done/skipped/failed/tok-s), live per-file feed (tier + `[STREAM-SUBJECT]` tag), **verbose
collapsible log**, Tags editor, Folders (exclude/include) dialog, Reports viewer, Stats (lifetime).
```

Replace with:

```
**GUI (Flet):** folder picker, host + live model picker (+ refresh), frontier dropdown,
**Run / Apply audited / Stop**, progress hero (% · file i/N · elapsed · ETA), counters
(done/skipped/failed/tok-s), live per-file feed (tier + `[STREAM-SUBJECT]` tag), **verbose
collapsible log** — all on Run. Tags tab: tag-vocabulary editor + the 5 run-option toggles
(vision/apply/copy/misc/skip-unknown — skip-unknown defaults **on**, misc defaults **off** as of
v0.12.3). Stats tab: lifetime counts + embedded Folders (exclude/include) + embedded Reports viewer.
```

- [ ] **Step 4: Update GUIDE.md**

In `docs/GUIDE.md`, find:

```
GUI equivalent: `docsort-gui` — a Flet app with a nav rail (Run / Tags / Folders / Reports / Stats),
the same toggles, live progress + per-file feed + verbose log, and an **Apply audited** button that runs
`--apply-journal` (rename the reviewed dry-run results without re-classifying).
```

Replace with:

```
GUI equivalent: `docsort-gui` — a Flet app with a nav rail (Run / Tags / Stats — Folders and Reports
live inside Stats as of v0.12.3, the run-option toggles live on Tags), live progress + per-file feed
+ verbose log, and an **Apply audited** button that runs `--apply-journal` (rename the reviewed
dry-run results without re-classifying).
```

- [ ] **Step 5: Commit**

```bash
git add docsort/__init__.py pyproject.toml docs/CHANGELOG.md docs/HANDOFF.md docs/GUIDE.md
git commit -m "build: v0.12.3 — version bump + docs sync for GUI tab consolidation"
```

---

### Task 7: Full verification pass

**Files:** none modified — this task only runs checks.

- [ ] **Step 1: Syntax check (mirrors CI)**

Run: `.venv\Scripts\python.exe -m py_compile docsort/cli.py docsort/config.py docsort/gui.py`
Expected: no output, exit code 0

- [ ] **Step 2: Full test suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: `26 passed` (the existing 20 from `test_core.py`/`test_runcore.py` + the 6 new ones in
`test_gui.py`). If the count differs, something in this plan's tests collided with an existing test
name — check for duplicates before assuming it's fine.

- [ ] **Step 3: CLI smoke test (mirrors CI)**

Run: `.venv\Scripts\python.exe -m docsort.cli --help`
Expected: the CLI help text prints, exit code 0 (confirms nothing in `gui.py`'s edits broke the
package import graph — `cli.py` doesn't import `gui.py`, but this is a 2-second sanity check matching
what CI runs).

- [ ] **Step 4: Human visual smoke-test (cannot be automated — flag for the user)**

This plan's tests are all headless control-tree assertions (per HANDOFF.md §9, the Flet GUI "is
headless-unverifiable by an agent" — a real window can't be opened in this environment). Before
tagging `v0.12.3` or merging to `main`, launch `docsort-gui` for real and check:
- Nav rail shows exactly 3 destinations, no leftover Folders/Reports icons.
- Tags tab shows the 5 toggles below the STREAMS/SUBJECTS/TYPES columns and they're functional
  (clicking one and switching to Run, then starting a run, actually uses the new value).
- Stats tab's embedded Folders/Reports sections render without visual squashing (the `expand=True`
  nesting flagged in Task 4 — fix with a fixed-height `ft.Container` wrapper if it looks wrong, but
  only after confirming visually, not blind).
- Skip-unknown shows as ON and Misc→ shows as OFF on first launch (default flip).

Do **not** push a `v0.12.3` tag (which triggers `release.yml` and publishes exes) until this manual
pass is done — matches the project's existing "human visual smoke-test is the gate before merge/tag"
convention.

- [ ] **Step 5: Report**

Summarize to the user: tests passing count, confirm Tasks 1–6 commits exist (`git log --oneline -8`),
and hand off the manual smoke-test checklist from Step 4.
