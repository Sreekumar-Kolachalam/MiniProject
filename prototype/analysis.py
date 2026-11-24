"""Heatmap / weightage numbers from the tagged questions (pandas only)."""
import pandas as pd

from tagger import UNCLASSIFIED


def to_frame(tagged_rows):
    df = pd.DataFrame(tagged_rows)
    if df.empty:
        return df
    df["unit_label"] = df["unit"].apply(
        lambda u: UNCLASSIFIED if pd.isna(u) else f"Unit {int(u)}")
    return df


def unit_summary(df, syllabus):
    """One row per unit (+ Unclassified): appearances, total/avg marks, share.

    frequency = average number of questions per paper from that unit.
    marks_share = unit marks / all marks in the uploaded papers (0..1).
    Note: papers offer choices (OR), so a paper's printed marks add up to 200.
    """
    n_papers = df["paper"].nunique()
    total = df["marks"].fillna(0).sum()
    rows = []
    labels = [(u["unit"], f"Unit {u['unit']}", u["title"]) for u in syllabus]
    labels.append((None, UNCLASSIFIED, "Could not be tagged confidently"))
    for unit, label, title in labels:
        sub = df[df["unit_label"] == label]
        if unit is None and sub.empty:
            continue
        marks = sub["marks"].fillna(0)
        rows.append({
            "unit": unit, "label": label, "title": title,
            "appearances": len(sub),
            "papers_seen": sub["paper"].nunique(),
            "total_marks": int(marks.sum()),
            "avg_marks": round(marks.mean(), 1) if len(sub) else 0.0,
            "marks_share": (marks.sum() / total) if total else 0.0,
            "frequency": len(sub) / n_papers if n_papers else 0.0,
        })
    return pd.DataFrame(rows)


def heatmap_table(df, value="marks"):
    """Unit x paper table of total marks (value='marks') or question counts."""
    if value == "marks":
        t = df.pivot_table(index="unit_label", columns="paper", values="marks",
                           aggfunc="sum", fill_value=0)
    else:
        t = df.pivot_table(index="unit_label", columns="paper", values="qid",
                           aggfunc="count", fill_value=0)
    return t.sort_index()


def topic_table(df):
    """How often each (unit, topic) came up, most frequent first."""
    t = (df.groupby(["unit_label", "topic"])
           .agg(appearances=("qid", "count"), total_marks=("marks", "sum"))
           .reset_index()
           .sort_values(["appearances", "total_marks"], ascending=False))
    return t
