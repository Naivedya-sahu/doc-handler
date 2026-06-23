# Changelog — Doc-handler

All notable changes. Newest on top.

## [0.4.0] — 2026-06-23
### Added
- **`TAGS.md` single source of truth** — STREAM/SUBJECT/TYPE/FACET lists live here; both the
  script (validation) and the injected system prompt read from it. `system_prompt.md` is now a
  template with `{{STREAMS}}/{{SUBJECTS}}/{{TYPES}}` placeholders filled at runtime.
- **Frontier fallback** for hard `99UNS` cases: `--frontier claude` (Claude Code CLI — uses the
  Claude subscription, text-only) or `--frontier openai` (needs `OPENAI_API_KEY`). `--backend openai`
  can also run the whole pass on a frontier model.
- **Animated TUI** (`tui.py`, Rich) — menu-driven tag/move with unicode spinners, live progress,
  and per-subject bar chart.
### Notes
- ChatGPT Plus/Go web subscription is NOT API-accessible; programmatic OpenAI use needs an API key.

## [0.3.0] — 2026-06-23
### Added
- **Page escalation**: when first-pass SUBJECT = `99UNS` on a PDF, re-read up to 5 pages
  (text) or page 3 (vision) and retry — fixes books/published PDFs whose page 1 is only
  cover / preface / copyright / table-of-contents.
- Packaged as self-contained **`Doc-handler/`** folder: README, GUIDE, CHANGELOG,
  requirements.txt, system_prompt.md.
- `requirements.txt` listing all software (pip + external apps) for independent use.
- Log `source` now distinguishes escalation tiers: `text5`, `vision3`.

## [0.2.0] — 2026-06-23
### Added
- **Two-axis tagging**: STREAM (CW/GATE/PROJ/RES/REC/REF) + SUBJECT (13 EE codes), so
  GATE/projects/research peel off while coursework unifies by subject.
- **Vision tier**: render page 1 → vision model for handwritten / scanned / vector PDFs.
- **`--move DEST`**: relocate `[STREAM-SUBJECT]` files into `DEST\STREAM\SUBJECT\`
  (replaces File Juggler), dry-run + reversible `_move_log.csv`.
- System prompt externalised to `system_prompt.md` (editable vocabulary).

## [0.1.0] — 2026-06-23
### Added
- Initial tagger: extract first pages → local LLM (LM Studio) → single SUBJECT code →
  `[CODE]` filename prefix. Dry-run by default, `--apply` to rename, CSV decision log.
- Cheap by design: classify by content, constrained to a fixed code list.

## Design notes
- Unifying axis = **SUBJECT** (reuses the GATE-EC KB's 13 categories) so the sorted
  archive mirrors the study KB.
- Decisive & mutually exclusive: one STREAM + one SUBJECT per file; uncertainty → 99UNS.
- Runs after dupeGuru hashed-dedup so duplicates aren't classified.
