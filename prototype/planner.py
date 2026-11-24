"""Simple day-by-day study plan.

priority(unit) = marks_share x frequency x (1 - confidence)
  marks_share : unit's share of all marks in the uploaded papers (0..1)
  frequency   : average number of questions per paper from that unit
  confidence  : the user's 1-5 slider, normalised to 0..1 as (c - 1) / 4

Steps:
  * The day before the exam is kept for PYQ practice.
  * Study hours are shared between units in proportion to priority.
  * Each day: first put any revision slots that are due, then fill the rest of
    the hours budget with the highest-priority unit that still has hours left.
  * When a unit is first studied, a revision slot is booked 1, 3 and 7 days later
    (only if that day is still before the PYQ day).
"""
import math
from datetime import timedelta

SLOT = 0.5               # smallest block of time, in hours
REVISION_HOURS = 0.5     # length of one revision slot
REVISION_OFFSETS = (1, 3, 7)


def confidence_norm(c):
    """1..5 slider -> 0..1."""
    return (min(max(c, 1), 5) - 1) / 4


def priority(marks_share, frequency, confidence):
    return marks_share * frequency * (1 - confidence_norm(confidence))


def _floor_slot(x):
    return math.floor(x / SLOT + 1e-9) * SLOT


def make_plan(units, confidence, start_date, exam_date, hours_per_day, n_papers=None):
    """units: list of dicts with unit, title, marks_share, frequency.
    confidence: {unit: 1..5}. Returns (plan_rows, notes).
    plan_rows: list of dicts date, unit, activity, hours, reason.
    """
    days = [start_date + timedelta(days=i) for i in range((exam_date - start_date).days)]
    if not days:
        raise ValueError("Exam date must be after the start date.")
    if hours_per_day < SLOT:
        raise ValueError(f"Hours per day must be at least {SLOT}.")
    hours_per_day = _floor_slot(hours_per_day)
    papers_txt = f"the last {n_papers} papers" if n_papers else "the uploaded papers"
    notes = []

    info = {}
    for u in units:
        c = confidence.get(u["unit"], 1)
        info[u["unit"]] = {**u, "conf": c,
                           "priority": priority(u["marks_share"], u["frequency"], c)}
    ranked = sorted(info.values(), key=lambda u: -u["priority"])
    to_study = [u for u in ranked if u["priority"] > 0]
    for u in ranked:
        if u["priority"] == 0:
            notes.append(f"Unit {u['unit']} skipped: confidence {u['conf']}/5 "
                         "(or it never appeared in the papers).")

    study_days, pyq_day = days[:-1], days[-1]
    budget = len(study_days) * hours_per_day
    reserve = len(to_study) * len(REVISION_OFFSETS) * REVISION_HOURS
    pool = max(budget - reserve, budget * 0.5)
    total_p = sum(u["priority"] for u in to_study)
    queue = []
    for u in to_study:
        hrs = max(SLOT, _floor_slot(pool * u["priority"] / total_p))
        queue.append([u["unit"], hrs])

    def study_reason(u):
        return (f"Unit {u['unit']}: {u['marks_share']:.0%} of marks in {papers_txt}, "
                f"~{u['frequency']:.1f} questions per paper, your confidence {u['conf']}/5")

    plan = []
    revisions = {}  # day index -> list of (unit, offset, first_day)
    carry = []
    for i, day in enumerate(study_days):
        cap = hours_per_day
        due, carry = carry + revisions.pop(i, []), []
        for unit, offset, first in due:
            if cap >= REVISION_HOURS:
                plan.append({"date": day, "unit": unit, "activity": "Revision",
                             "hours": REVISION_HOURS,
                             "reason": f"Unit {unit}: revision {offset} day(s) after first "
                                       f"study on {first:%d %b}"})
                cap -= REVISION_HOURS
            else:
                carry.append((unit, offset, first))
        while cap >= SLOT and queue:
            unit, remaining = queue[0]
            take = min(remaining, _floor_slot(cap))
            u = info[unit]
            if "first" not in u:
                u["first"] = day
                for off in REVISION_OFFSETS:
                    if i + off < len(study_days):
                        revisions.setdefault(i + off, []).append((unit, off, day))
            if plan and plan[-1]["date"] == day and plan[-1]["unit"] == unit \
                    and plan[-1]["activity"] == "Study":
                plan[-1]["hours"] += take
            else:
                plan.append({"date": day, "unit": unit, "activity": "Study",
                             "hours": take, "reason": study_reason(u)})
            cap -= take
            queue[0][1] -= take
            if queue[0][1] <= 1e-9:
                queue.pop(0)

    left = sum(r for _, r in queue)
    if left:
        notes.append(f"Not enough days: {left:g} study hours could not be scheduled "
                     f"(units {', '.join(str(u) for u, _ in queue)}).")
    if carry or revisions:
        notes.append("Some revision slots did not fit before the PYQ day.")
    plan.append({"date": pyq_day, "unit": None, "activity": "PYQ practice",
                 "hours": hours_per_day,
                 "reason": "Last day before the exam: solve full past papers under exam timing"})
    return plan, notes
