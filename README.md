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
git clone https://github.com/USER/doc-handler.git
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

## Files
| File | What |
|---|---|
| `doc_handler.py` | the tagger + mover |
| `system_prompt.md` | the LLM vocabulary + rules (edit to tune) |
| `requirements.txt` | software needed for independent use |
| `GUIDE.md` | detailed runbook, tiers, escalation, troubleshooting |
| `CHANGELOG.md` | version history |

See `GUIDE.md` for the full workflow and how the prompt/escalation work.
