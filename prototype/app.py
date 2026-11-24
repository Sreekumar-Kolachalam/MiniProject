"""Study-planner prototype. Run: streamlit run app.py"""
import glob
import os
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import heatmap_table, to_frame, topic_table, unit_summary
from parser import is_scanned, parse_pdf
from planner import make_plan
from tagger import Tagger, load_syllabus, tag_questions

HERE = os.path.dirname(os.path.abspath(__file__))
PAPERS_DIR = os.path.join(HERE, "papers")

st.set_page_config(page_title="Study Planner (prototype)", layout="wide")


@st.cache_resource
def get_tagger():
    syllabus = load_syllabus(os.path.join(HERE, "syllabus.json"))
    return syllabus, Tagger(syllabus)


@st.cache_data
def process_pdf(data: bytes, name: str):
    rows, text = parse_pdf(data, name)
    return rows, text


syllabus, tagger = get_tagger()
st.session_state.setdefault("papers", {})  # name -> bytes

# ---------- Sidebar: input papers ----------
with st.sidebar:
    st.header("1. Question papers")
    uploads = st.file_uploader("Upload past papers (PDF, one subject)",
                               type="pdf", accept_multiple_files=True)
    for f in uploads or []:
        st.session_state.papers[f.name] = f.getvalue()
    if st.button("Load all papers from papers/"):
        for path in sorted(glob.glob(os.path.join(PAPERS_DIR, "*.pdf"))):
            with open(path, "rb") as fh:
                st.session_state.papers[os.path.basename(path)] = fh.read()
    if st.button("Clear papers"):
        st.session_state.papers = {}
    st.caption(f"{len(st.session_state.papers)} paper(s) loaded")
    for name in st.session_state.papers:
        st.write("•", name)

st.title("📚 Study Planner — prototype")

if not st.session_state.papers:
    st.info("Upload question papers or click **Load all papers from papers/** in the sidebar.")
    st.stop()

# ---------- Parse + tag ----------
all_rows, raw_texts = [], {}
for name, data in st.session_state.papers.items():
    rows, text = process_pdf(data, name)
    raw_texts[name] = text
    if is_scanned(text):
        st.error(f"{name}: almost no text found — looks scanned, needs OCR. Skipped.")
        continue
    if not rows:
        st.warning(f"{name}: no questions found (format not recognised).")
    all_rows += rows

if not all_rows:
    st.stop()

df = to_frame(tag_questions(all_rows, tagger))
summary = unit_summary(df, syllabus)
n_papers = df["paper"].nunique()

tab_q, tab_heat, tab_plan, tab_raw = st.tabs(
    ["Questions", "Topic heatmap", "Study plan", "Raw text"])

# ---------- Questions ----------
with tab_q:
    c1, c2, c3 = st.columns(3)
    c1.metric("Papers", n_papers)
    c2.metric("Questions (sub-parts)", len(df))
    c3.metric("Unclassified", int(df["unit"].isna().sum()))
    st.caption("Tagging: **keyword** = syllabus/keyword match, **tfidf** = similarity "
               "fallback, **unclassified** = not confident, not guessed. "
               "'module' is the heading printed in the paper, shown for checking.")
    paper_filter = st.multiselect("Filter papers", sorted(df["paper"].unique()))
    view = df if not paper_filter else df[df["paper"].isin(paper_filter)]
    st.dataframe(
        view[["paper", "qid", "marks", "module", "unit_label", "topic", "method",
              "score", "text"]].rename(columns={"unit_label": "tagged unit"}),
        width="stretch", hide_index=True)
    agree = (df["unit"] == df["module"]).mean()
    st.caption(f"Tagged unit matches the paper's own module heading for {agree:.0%} "
               "of questions.")

# ---------- Heatmap ----------
with tab_heat:
    metric = st.radio("Show", ["Total marks", "Number of questions"], horizontal=True)
    table = heatmap_table(df, "marks" if metric == "Total marks" else "count")
    fig = px.imshow(table, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                    labels={"x": "Paper", "y": "Unit", "color": metric})
    fig.update_xaxes(tickangle=-30)
    st.plotly_chart(fig, width="stretch")

    show = summary.copy()
    show["marks_share"] = (show["marks_share"] * 100).round(1).astype(str) + "%"
    show["frequency"] = show["frequency"].round(2)
    st.subheader("Per unit, across all papers")
    st.dataframe(show.drop(columns=["unit"]).rename(columns={
        "label": "unit", "appearances": "times appeared", "papers_seen": "papers",
        "total_marks": "total marks", "avg_marks": "avg marks",
        "marks_share": "share of marks", "frequency": "questions / paper"}),
        width="stretch", hide_index=True)
    st.caption("Papers offer choices (OR), so each paper prints 200 marks of questions.")
    with st.expander("Most frequent topics"):
        st.dataframe(topic_table(df), width="stretch", hide_index=True)

# ---------- Plan ----------
with tab_plan:
    c1, c2, c3 = st.columns(3)
    start = c1.date_input("Start date", date.today())
    exam = c2.date_input("Exam date", date.today() + timedelta(days=21))
    hours = c3.number_input("Hours available per day", 0.5, 16.0, 3.0, step=0.5)

    st.markdown("**How confident are you in each unit?** (1 = not at all, 5 = fully)")
    units = summary[summary["unit"].notna()].to_dict("records")
    cols = st.columns(len(units))
    conf = {}
    for col, u in zip(cols, units):
        conf[int(u["unit"])] = col.slider(f"Unit {int(u['unit'])}", 1, 5, 1,
                                          help=u["title"], key=f"conf{int(u['unit'])}")

    for u in units:
        u["unit"] = int(u["unit"])
    try:
        plan, notes = make_plan(units, conf, start, exam, hours, n_papers=n_papers)
    except ValueError as e:
        st.error(str(e))
        st.stop()
    for n in notes:
        st.warning(n)

    plan_df = pd.DataFrame(plan)
    plan_df["unit"] = plan_df["unit"].apply(lambda u: "" if pd.isna(u) else f"Unit {int(u)}")
    plan_df["date"] = pd.to_datetime(plan_df["date"])
    by_day = plan_df.groupby("date")["hours"].sum()
    st.caption(f"{len(by_day)} day(s) planned, {plan_df['hours'].sum():g} hours total.")

    fig = px.bar(plan_df, x="date", y="hours", color="unit", pattern_shape="activity",
                 hover_data=["activity", "reason"])
    st.plotly_chart(fig, width="stretch")

    for day, items in plan_df.groupby("date"):
        with st.container(border=True):
            st.markdown(f"**{day:%a %d %b}** — {items['hours'].sum():g} h")
            for _, it in items.iterrows():
                label = it["unit"] or "All units"
                st.markdown(f"- {it['activity']} · {label} · {it['hours']:g} h  \n"
                            f"  <span style='color:gray'>{it['reason']}</span>",
                            unsafe_allow_html=True)
    st.download_button("Download plan as CSV", plan_df.to_csv(index=False),
                       "study_plan.csv", "text/csv")

# ---------- Raw text (Step 1) ----------
with tab_raw:
    name = st.selectbox("Paper", list(raw_texts))
    st.text(raw_texts[name])
