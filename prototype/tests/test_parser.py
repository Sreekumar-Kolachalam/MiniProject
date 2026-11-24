import glob
import os
import sys
from collections import defaultdict

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from parser import PATTERNS, split_questions  # noqa: E402

SAMPLE = """
Fifth Semester Degree Examination
Note: Answer any FIVE full questions.
Module – 1
M
L
C
Q.1
a. Explain the waterfall model.
10
L2 CO1
b.
Explain incremental process models with
a neat diagram.
10
L2
CO1
OR
Q.2
a. Explain software myths.
08
L2 CO1
b.
Explain the unified process.
08
L2 CO1
c. What is a WebApp?
04
L1 CO1
Module-2
Q.03
a
Explain CRC modeling.
L1
CO2
10
* * * * *
USN
BCS501
"""


def test_splits_subparts_and_marks():
    rows = split_questions(SAMPLE, "sample")
    assert [r["qid"] for r in rows] == ["Q1a", "Q1b", "Q2a", "Q2b", "Q2c", "Q3a"]
    assert [r["marks"] for r in rows] == [10, 10, 8, 8, 4, 10]
    assert [r["module"] for r in rows] == [1, 1, 1, 1, 1, 2]


def test_wrapped_line_starting_with_a_is_not_a_new_part():
    rows = split_questions(SAMPLE, "sample")
    q1b = rows[1]
    assert q1b["text"] == "Explain incremental process models with a neat diagram."


def test_marks_after_co_column_and_footer_ignored():
    rows = split_questions(SAMPLE, "sample")
    assert rows[-1]["text"] == "Explain CRC modeling."
    assert rows[-1]["marks"] == 10


def test_patterns():
    assert PATTERNS["module"].match("Module – 3").group(1) == "3"
    assert PATTERNS["question"].match("Q.10").group(1) == "10"
    assert PATTERNS["question"].match("Q.01").group(1) == "1"
    assert PATTERNS["marks"].match("08 ")
    assert not PATTERNS["marks"].match("2000.")
    assert PATTERNS["noise"].match("AD - AD - AD")


PAPERS = sorted(glob.glob(os.path.join(ROOT, "papers", "*.pdf")))


@pytest.mark.skipif(not PAPERS, reason="no papers/ folder")
@pytest.mark.parametrize("path", PAPERS, ids=os.path.basename)
def test_real_papers_have_10_questions_of_20_marks(path):
    from parser import parse_pdf
    rows, _ = parse_pdf(path, os.path.basename(path))
    per_q = defaultdict(int)
    for r in rows:
        assert r["marks"] is not None, r
        assert r["text"], r
        per_q[r["q_no"]] += r["marks"]
    assert sorted(per_q) == list(range(1, 11))
    assert all(m == 20 for m in per_q.values()), per_q
