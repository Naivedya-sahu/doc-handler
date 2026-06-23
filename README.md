# 📄 Doc-handler

![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![offline](https://img.shields.io/badge/runs-100%25%20offline-orange)

Local-LLM document tagger + sorter. Reads each academic document, classifies it into
a **STREAM** (CW / GATE / PROJ / RES / REC / REF) and a **SUBJECT** (13 EE topics),
stamps a `[STREAM-SUBJECT]` filename prefix, then moves files into a clean tree —
**fully offline, free, no cloud**.

Built for sorting a messy Academics archive into one mutually-exclusive structure
where GATE / projects / research peel off by stream and coursework unifies by subject.

## Why
- Many PDFs have **no extractable text** (handwritten notes, scanned pages, vector docs)
  → a **vision model** reads the rendered page.
- Books put cover/preface/TOC on page 1 → **escalation** re-reads up to 5 pages on `99UNS`.
- Off-the-shelf taggers can't use *your* taxonomy or keep streams separable → this does.

## Requirements
See `requirements.txt`. Minimum: **Python 3.9+ · pymupdf · LM Studio · one vision model**
(Qwen2-VL-7B-Instruct fits 8 GB and handles both text and images).

## Install
```bash
git clone https://github.com/Naivedya-sahu/doc-handler.git
cd doc-handler
pip install -r requirements.txt          # or: pip install .[office]
```
Run from the cloned folder with `python doc_handler.py ...`, or after `pip install .`
use the `doc-handler` command. Requires LM Studio running locally with a model loaded.

## Quickstart
```bat
pip install -r requirements.txt
:: 1) LM Studio: load a vision model, Start Server (localhost:1234)
:: 2) Backup first, then dry-run:
python doc_handler.py "D:\AcademicsCOPY" --vision --vision-model qwen2-vl-7b
:: 3) Review _doc_handler_log.csv (check conf=low, source=vision/filename)
:: 4) Apply the prefixes:
python doc_handler.py "D:\AcademicsCOPY" --apply --vision --vision-model qwen2-vl-7b
:: 5) Move by prefix into the archive tree (dry-run, then --apply):
python doc_handler.py "D:\AcademicsCOPY" --move "D:\Archive\Academics"
python doc_handler.py "D:\AcademicsCOPY" --move "D:\Archive\Academics" --apply
```

## Pipeline position
`dupeGuru hashed-dedup` → **Doc-handler tag** → **Doc-handler move** → handle GATE/PROJ/RES folders apart.
Run dedup FIRST so the LLM never reads duplicate copies.

## TUI
```bash
pip install rich
python tui.py        # menu: tag (dry/apply) · move · live progress + per-subject bars
```

## Frontier fallback (optional)
Local model handles everything; for stubborn `99UNS` files you can escalate to a frontier model:
- `--frontier claude` → shells out to **Claude Code CLI** (`claude -p`), using your Claude subscription (text-only).
- `--frontier openai` → OpenAI API (set `OPENAI_API_KEY`). `--backend openai` runs the whole pass on it.
- *Note:* a ChatGPT Plus/Go web subscription is **not** an API — programmatic OpenAI use needs an API key.

## Files
| File | What |
|---|---|
| `doc_handler.py` | the tagger + mover (CLI) |
| `tui.py` | animated Rich TUI front-end |
| `TAGS.md` | **single source of truth** for all tag lists (script + model read this) |
| `system_prompt.md` | rules/examples template (tags injected from `TAGS.md`) |
| `requirements.txt` | software needed for independent use |
| `GUIDE.md` | detailed runbook, tiers, escalation, troubleshooting |
| `CHANGELOG.md` | version history |

Edit tags in **`TAGS.md`** only — changes flow to both the script and the model.
See `GUIDE.md` for the full workflow and how the prompt/escalation/backends work.
