# v0.12.3 — GUI tab consolidation + toggle relocation

> Design spec. Current version: 0.12.1. Target: 0.12.3 (patch — no new CLI flags, pure GUI
> reorg + a default-value change).

## Problem

Today's GUI (`docsort/gui.py`) has 5 NavigationRail tabs: Run / Tags / Folders / Reports / Stats.
Run carries 5 toggle switches (Vision, Apply, Work-on-copy, Misc→, Skip-unknown) inline, crowding
the screen that should just be "point at a folder and go." Folders and Reports are each one-purpose
screens that don't need their own permanent rail slot.

Separately: `99UNS` (unsure) files currently default to misc-quarantine (`t_misc=True`,
`t_skip=False`). Decision from this session: default behavior should be **skip** (leave untouched)
not quarantine — quarantine becomes opt-in.

## Scope

1. **Nav rail: 5 → 3 tabs.** `Run / Tags / Stats`.
2. **Folders + Reports fold into Stats** as sub-sections. Their existing view-builder logic
   (`_folders_view`, `_reports_view`) is reused as-is, just mounted under Stats instead of
   standalone rail destinations.
3. **5 switches move from Run to Tags tab.** Vision / Apply(rename) / Work-on-a-copy / Misc→ /
   Skip-unknown render in the Tags view, below the STREAMS/SUBJECTS/TYPES columns, above Save.
   Host/Model/Frontier stay on Run (needed immediately pre-click).
4. **Default flip:** `t_skip` (Skip-unknown) default `False → True`. `t_misc` (Misc→) default
   `True → False`.

## Architecture change

`_run_view(page)` and `_tags_view(page)` are currently independent closures. Run is built eagerly
in `_build()`; Tags is built lazily on first nav visit (`cache` dict in `_build`). `start_run` /
`apply_audited` (defined inside `_run_view`) read switch `.value` directly via closure.

If the 5 switches move into `_tags_view`'s closure, `_run_view` can no longer see them, and if Tags
hasn't been visited yet when Run is built, the switches wouldn't exist at all.

**Fix:** construct the 5 `ft.Switch` controls once in `_build()`, before either view is built. Pass
the same control objects into both `_run_view(page, toggles)` and `_tags_view(page, toggles)`. Run
reads `.value` off them for `opts`; Tags lays them out visually. Same live objects — toggling in
Tags affects the very next Run, no sync code needed.

`_make_view`/`_on_nav_change` index mapping updates: `0=Run, 1=Tags, 2=Stats` (was
`0=Run,1=Tags,2=Folders,3=Reports,4=Stats`). `_stats_view` becomes a `Column` that mounts: existing
lifetime-stats list, then a Folders sub-section (reusing `_folders_view`'s list-building closures),
then a Reports sub-section (reusing `_reports_view`'s load/render closures, still needs the
`folder_getter` callback wired to the Run folder field, same as today).

## Out of scope (stays on the v0.13.x/v0.14 track, not touched here)

Node-graph, treemap, dedupe report surfacing, settings-as-separate-window (superseded — toggles go
to Tags tab per this session's decision, not a modal).

## Testing

No live Flet window (headless-unverifiable per HANDOFF §9). Same pattern as existing GUI
validation: construct the control tree against a stub `page` object, assert structurally:

- `rail.destinations` has exactly 3 entries, labels `["Run", "Tags", "Stats"]` in order.
- The 5 switch controls built in `_build()` are the *same objects* (`is`) reachable from both
  `_run_view`'s closure (via `start_run`'s opts-building) and `_tags_view`'s control tree.
- `t_skip.value is True`, `t_misc.value is False` immediately after construction (default flip).
- `start_run`'s `opts` dict still populates `vision`/`apply`/`copy`/`misc`/`skip_unknown` correctly
  reading off the relocated switches (regression check — behavior must be identical to today, only
  the controls' visual location changed).
- Stats view control tree contains the Folders and Reports sub-section containers.

## Non-goals

No change to `runcore.build_run_cmd`, no new CLI flags, no change to `classify()`/`cli.py` engine
behavior beyond the two default values already wired through `gui.py` → `build_run_cmd`'s `opts`
dict (the engine itself just receives `--skip-unknown` more often / `--no-misc` more often now,
same flags as today).
