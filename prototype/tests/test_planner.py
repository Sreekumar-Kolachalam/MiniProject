import os
import sys
from collections import defaultdict
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from planner import confidence_norm, make_plan, priority  # noqa: E402

UNITS = [
    {"unit": 1, "title": "A", "marks_share": 0.30, "frequency": 5.0},
    {"unit": 2, "title": "B", "marks_share": 0.20, "frequency": 4.0},
    {"unit": 3, "title": "C", "marks_share": 0.10, "frequency": 2.0},
]
START = date(2026, 12, 1)


def test_confidence_and_priority():
    assert confidence_norm(1) == 0
    assert confidence_norm(5) == 1
    assert priority(0.3, 5, 1) == pytest.approx(1.5)
    assert priority(0.3, 5, 5) == 0


def test_last_day_is_pyq_and_budget_respected():
    plan, _ = make_plan(UNITS, {}, START, START + timedelta(days=14), 3)
    assert plan[-1]["activity"] == "PYQ practice"
    assert plan[-1]["date"] == START + timedelta(days=13)
    per_day = defaultdict(float)
    for p in plan:
        per_day[p["date"]] += p["hours"]
    assert all(h <= 3 for h in per_day.values())
    assert all(p["date"] < START + timedelta(days=14) for p in plan)


def test_highest_priority_first_and_reason():
    plan, _ = make_plan(UNITS, {}, START, START + timedelta(days=14), 3)
    first = plan[0]
    assert first["activity"] == "Study" and first["unit"] == 1
    assert first["reason"].startswith("Unit 1: 30% of marks")


def test_revisions_after_1_3_7_days():
    plan, _ = make_plan(UNITS, {}, START, START + timedelta(days=20), 2)
    first = min(p["date"] for p in plan if p["unit"] == 1 and p["activity"] == "Study")
    revs = sorted(p["date"] for p in plan if p["unit"] == 1 and p["activity"] == "Revision")
    assert revs == [first + timedelta(days=d) for d in (1, 3, 7)]


def test_confident_unit_is_skipped():
    plan, notes = make_plan(UNITS, {1: 5}, START, START + timedelta(days=10), 3)
    assert not any(p["unit"] == 1 for p in plan)
    assert any("Unit 1 skipped" in n for n in notes)


def test_too_little_time_gives_note():
    plan, notes = make_plan(UNITS, {}, START, START + timedelta(days=1), 2)
    assert [p["activity"] for p in plan] == ["PYQ practice"]
    assert any("could not be scheduled" in n for n in notes)


def test_exam_in_past_raises():
    with pytest.raises(ValueError):
        make_plan(UNITS, {}, START, START, 2)
