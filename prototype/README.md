# Study Planner — prototype

Throwaway demo: upload past question papers for one subject, see which syllabus
units come up most, and get a day-by-day study plan. Built and tested with
5 VTU papers for **BCS501 Software Engineering & Project Management**.

## How to run

```bash
cd prototype
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

In the sidebar, click **Load all papers from papers/** (or upload PDFs).

Run the tests:

```bash
python -m pytest
```

## What each file does

| File | What it does |
|---|---|
| `app.py` | Streamlit UI: four tabs (Questions, Topic heatmap, Study plan, Raw text). |
| `parser.py` | Gets text out of a PDF with PyMuPDF and splits it into questions. Reads line by line and tracks the current `Module – N`, question `Q.N` and sub-part `a/b/c`. A line that is only a number is the marks. All regexes are in the `PATTERNS` dict at the top. |
| `tagger.py` | Tags each question to a unit/topic. Step 1 is keyword matching against syllabus topics plus `EXTRA_KEYWORDS`. If that finds nothing or ends in a tie, step 2 uses TF-IDF similarity to every topic. A question with similarity under 0.20 is **Unclassified**. |
| `analysis.py` | pandas tables: per-unit appearances, total/avg marks, share of marks, and unit × paper heatmap. |
| `planner.py` | Builds the plan. `priority = marks_share × frequency × (1 − confidence)`. The day before the exam is kept for PYQ practice. Each unit gets revision slots 1, 3 and 7 days after it is first studied. |
| `syllabus.json` | The syllabus as `[{"unit", "title", "topics"}]`, typed from `syllabus_source/BCS501-syllabus.pdf`. |
| `papers/` | The 5 past papers. |
| `tests/` | pytest tests for the parser (sample text + the 5 real papers) and the planner. |

## Results on the 5 BCS501 papers

- Parser: 109 sub-questions found. Every one has marks, and every main question adds up to 20.
- Tagger: 0 Unclassified. The tagged unit matches the paper's own module heading for 107 of 109 questions (98%). Both mismatches are cases where the paper doesn't follow the syllabus: flow/behavioural modelling sits in Module 2 of the syllabus, and "nature of software" sits in Module 1.

## Known limitations

- **Format-specific parser.** It assumes the VTU layout (`Module – N`, `Q.N`, `a.`, marks on their own line). Other universities' papers will need new `PATTERNS`.
- **No OCR.** A scanned PDF is detected and skipped.
- **Tagger was tuned on these same 5 papers.** The `EXTRA_KEYWORDS` (SCRUM, COCOMO, McCall…) were added after looking at them, so 98% is optimistic. A new subject needs its own keywords.
- **Unit weightage is almost flat** (about 20% per unit) because VTU papers always have 2 questions × 20 marks per module. So the plan is mostly driven by the confidence sliders. The topic-level table is more useful than the unit totals.
- Marks include both sides of every "OR" choice, so each paper counts as 200 marks.
- Study hours are split by priority, not by how big a unit actually is.
- If revisions use less time than reserved, a day can end up under the hours budget. A 7-day revision that would land on the PYQ day is dropped.
- Nothing is saved: no persistence, login or multi-subject support.
