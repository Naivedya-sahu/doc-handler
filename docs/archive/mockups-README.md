# GUI mockups — v0.11.0 visual overhaul

Static, throwaway HTML design references for the v0.11.0 Flet GUI overhaul. They are **not** the app —
they exist to pin down the visual target (Discord-like dark layout, the run view's information hierarchy,
and the future system-tray presence). Open them in any browser.

| File | What it shows |
|---|---|
| `run-view.html` | The Run view — left nav rail + main panel. Progress %, elapsed/ETA, done/skipped/failed + tok/s, current-file tier indicator, and the live per-file feed with `[STREAM-SUBJECT]` tags. |
| `system-tray.html` | The future background-processing concept — a Windows tray flyout with live progress + quick Open/Pause/Stop, and the completion toast. (Roadmap item, not v0.11.0.) |

The colours/fonts here are standalone fallbacks for browser viewing; the real app uses the Flet dark theme
defined in `docsort/gui.py`. Design intent lives in [`gui-vision.md`](gui-vision.md); the build plan
is [`gui-visual-overhaul-plan.md`](gui-visual-overhaul-plan.md).
