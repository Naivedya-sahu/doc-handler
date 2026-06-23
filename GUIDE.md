# Doc-handler — Guide

## 1. What the LLM receives (per file)
Two messages:
- **SYSTEM** = the `<SYSTEM>` block of `system_prompt.md` (STREAM + SUBJECT + TYPE vocab, rules, examples). Same every call.
- **USER** = built per file:
  - *text tier:* `Filename / Folder / Text(<=4000 chars) / Answer (STREAM SUBJECT TYPE CONF):`
  - *vision tier:* same line **+ the page rendered to PNG** as an image.
  - *filename tier:* same with empty text.
Settings: `temperature=0`, `max_tokens=16`. The model replies one line, e.g. `CW 12EMAG notes high`.

## 2. Classification tiers (in order)
1. **TEXT** — extract first 2 pages. If ≥80 chars → text model.
2. **ESCALATE (the book fix)** — if the answer SUBJECT is `99UNS` and the file is a PDF,
   re-read **up to 5 pages** (skips past cover/preface/TOC) and retry once.
   Logged as `source=text5`.
3. **VISION** — if no extractable text → render page 1 to image → vision model.
   Still `99UNS`? render **page 3** and retry → `source=vision3`.
4. **FILENAME** — no text, no vision → classify from filename + folder path.

`source` in the log tells you which tier decided. Trust order: `text > text5 > vision > vision3 > filename`.

## 3. The tag scheme
- **Prefix = `[STREAM-SUBJECT]`** — the only thing added to the filename.
  - STREAM peels special cases: `GATE`, `PROJ`, `RES`, `REC` separate from `CW`.
  - SUBJECT unifies coursework: all EMF → `12EMAG`, regardless of source.
- **TYPE / CONF** go to the log only (not the name) — used to review, and later for Obsidian tags.
- **Mutual exclusivity**: model must pick ONE STREAM + ONE SUBJECT from the fixed lists;
  multi-subject or unsure → `99UNS` → stays for manual split (never mis-filed).

## 4. Full workflow
```
0. BACKUP        copy Academics -> AcademicsCOPY        (always work on the copy)
1. DEDUP         dupeGuru: Scan Type Folders, then Contents; Re-Prioritize (suffix down);
                 Move Marked to quarantine. Kill copies BEFORE tagging.
2. TAG dry-run   python doc_handler.py "AcademicsCOPY" --vision --vision-model qwen2-vl-7b
                 -> review _doc_handler_log.csv
3. TAG apply     python doc_handler.py "AcademicsCOPY" --apply --vision --vision-model qwen2-vl-7b
4. MOVE dry-run  python doc_handler.py "AcademicsCOPY" --move "D:\Archive\Academics"
5. MOVE apply    python doc_handler.py "AcademicsCOPY" --move "D:\Archive\Academics" --apply
6. SPECIAL       handle D:\Archive\Academics\{GATE,PROJ,RES,REC} folders separately
```

## 5. Reviewing the log
Sort `_doc_handler_log.csv` by:
- `conf=low` → eyeball, fix prefix by hand if wrong.
- `source=filename` → weakest signal; verify.
- `subject=99UNS` → multi-subject/unsure → split manually or leave.
Renames are reversible from the `old`/`new` columns; moves from `_move_log.csv` (`from`/`to`).

## 6. Tuning
- Edit `system_prompt.md` lists/examples to add subjects or sharpen rules. No code change needed.
- `MIN_TEXT` (80), `DEEP_PAGES` (5), `DEEP_CAP` (4000) are constants at the top of `doc_handler.py`.

## 7. Troubleshooting
| Symptom | Fix |
|---|---|
| Every file `99UNS` | model not following format — try a stronger model, lower file count, confirm Server running |
| `api-error` | LM Studio server not started, or wrong `--api` URL/port |
| PDFs skipped | `pip install pymupdf` |
| `.docx/.pptx` skipped | `pip install python-docx python-pptx` |
| Vision tier never fires | pass `--vision` and a loaded vision model name via `--vision-model` |
| Slow | vision is heavier; run text-only first, then a `--vision` pass on the remainder |
