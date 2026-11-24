"""Tag each question to a syllabus unit/topic. No LLM.

1. Keyword matching: every syllabus topic (plus a few extra textbook terms
   below) is a "phrase". A unit's score = total words of its phrases found in
   the question. The highest-scoring unit wins if it beats the runner-up.
2. TF-IDF fallback: if no keyword hits (or a tie), compare the question with
   every topic using TF-IDF cosine similarity. Accept the best topic only if
   the similarity is >= TFIDF_THRESHOLD.
3. Otherwise the question is "Unclassified" (we don't guess).
"""
import json
import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TFIDF_THRESHOLD = 0.20
UNCLASSIFIED = "Unclassified"

# Terms the papers use that the syllabus text doesn't spell out
# (e.g. SCRUM is one of the "Other Agile Process Models").
# Subject-specific: for a new subject, edit or empty this dict.
EXTRA_KEYWORDS = {
    1: ["spiral", "process framework", "application domain", "webapp", "myth",
        "hooker", "evolutionary process", "software process"],
    2: ["use case", "crc", "class responsibility collaborator", "qfd",
        "quality function deployment", "elicitation", "elicit",
        "analysis model", "analysis class", "requirement modeling",
        "activity diagram", "groundwork", "validate requirement",
        "behavioral model", "scenario based model", "requirement engineering"],
    3: ["agile", "agility", "scrum", "xp", "extreme programming",
        "extremes programming", "adaptive software development",
        "planning principle", "communication principle", "principle that guide",
        "design modeling principle", "principle in coding"],
    4: ["project management", "iso 12207", "iso12207", "smart objective",
        "categories of software project", "activity planning", "outsourced",
        "cost benefit", "risk evaluation", "individual project",
        "software development life cycle", "contrast of software project",
        "management involve"],
    5: ["quality", "quality management", "iso 9001", "bseniso9001", "bseniso",
        "iso 9126", "mccall", "garvin", "dromey", "boehms model", "cmm",
        "seicmm", "capability process", "cocomo", "estimation",
        "estimation technique", "automated estimation", "decomposition technique",
        "software reliability", "sizing", "siting",
        "place of software quality"],
}

STOPWORDS = {"the", "a", "an", "of", "and", "is", "what", "some", "ways", "each",
             "to", "for", "with", "in", "on", "its", "that", "versus"}


def normalize(text):
    """Lowercase, drop punctuation/apostrophes, crude singularisation."""
    text = text.lower().replace("’", "").replace("'", "")
    text = text.replace("modelling", "modeling").replace("-", " ")
    words = re.findall(r"[a-z0-9]+", text)
    out = []
    for w in words:
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]  # requirements -> requirement, models -> model
        out.append(w)
    return " ".join(out)


def _phrase(text):
    """Normalized phrase with leading/trailing stopwords removed."""
    words = normalize(text).split()
    while words and words[0] in STOPWORDS:
        words.pop(0)
    while words and words[-1] in STOPWORDS:
        words.pop()
    return " ".join(words)


def load_syllabus(path="syllabus.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Tagger:
    def __init__(self, syllabus, extra_keywords=None):
        extra = EXTRA_KEYWORDS if extra_keywords is None else extra_keywords
        self.syllabus = syllabus
        # (unit, phrase, topic or None)
        self.phrases = []
        self.topic_docs = []  # (unit, topic)
        for u in syllabus:
            for t in u["topics"]:
                p = _phrase(t)
                if p:
                    self.phrases.append((u["unit"], p, t))
                self.topic_docs.append((u["unit"], t))
            for k in extra.get(u["unit"], []):
                self.phrases.append((u["unit"], _phrase(k), None))
        docs = [f"{t} {self._unit_title(u)}" for u, t in self.topic_docs]
        self.vectorizer = TfidfVectorizer(preprocessor=normalize, ngram_range=(1, 2),
                                          stop_words=sorted({normalize(w) for w in ENGLISH_STOP_WORDS}),
                                          sublinear_tf=True)
        self.topic_matrix = self.vectorizer.fit_transform(docs)

    def _unit_title(self, unit):
        return next(u["title"] for u in self.syllabus if u["unit"] == unit)

    def _tfidf(self, text, unit=None):
        """Best (unit, topic, similarity), optionally limited to one unit."""
        sims = cosine_similarity(self.vectorizer.transform([text]), self.topic_matrix)[0]
        best = None
        for i, (u, t) in enumerate(self.topic_docs):
            if unit is not None and u != unit:
                continue
            if best is None or sims[i] > best[2]:
                best = (u, t, float(sims[i]))
        return best

    def tag(self, text):
        """Return dict: unit, topic, method, score, matched."""
        padded = f" {normalize(text)} "
        scores, matched, topic_hits = {}, {}, {}
        for unit, phrase, topic in self.phrases:
            if f" {phrase} " in padded:
                n = len(phrase.split())
                scores[unit] = scores.get(unit, 0) + n
                matched.setdefault(unit, []).append(phrase)
                if topic and n > topic_hits.get(unit, ("", 0))[1]:
                    topic_hits[unit] = (topic, n)
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
            unit = ranked[0][0]
            if unit in topic_hits:
                topic = topic_hits[unit][0]
            else:  # only extra keywords matched: pick closest topic in that unit
                _, topic, sim = self._tfidf(text, unit)
                topic = topic if sim > 0 else "(general)"
            return {"unit": unit, "topic": topic, "method": "keyword",
                    "score": float(ranked[0][1]), "matched": ", ".join(matched[unit])}
        unit, topic, sim = self._tfidf(text)
        if sim >= TFIDF_THRESHOLD:
            return {"unit": unit, "topic": topic, "method": "tfidf",
                    "score": round(sim, 3), "matched": ""}
        return {"unit": None, "topic": UNCLASSIFIED, "method": "unclassified",
                "score": round(sim, 3), "matched": ""}


def tag_questions(rows, tagger):
    """Add unit/topic/method/score/matched to each question dict (copies)."""
    return [{**r, **tagger.tag(r["text"])} for r in rows]
