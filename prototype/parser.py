"""PDF text extraction + question splitting for VTU-style question papers.

How a paper looks after text extraction (one item per line):

    Module – 1
    Q.1                      <- question number (also "Q.01", "Q.10")
    a. Explain the ...       <- sub-part (also "a.", "a" alone, "a Explain ...")
    ... continued text ...
    10                       <- marks: a bare number line (VTU papers put it
    L2 CO1                      before Bloom level/CO, the model paper after)
    b.
    ...
    OR

We read the text line by line and keep track of the current module, question
and sub-part. Each sub-part (Q1a, Q1b, ...) becomes one "question" row.
"""
import re

import pymupdf

PATTERNS = {
    # "Module – 1", "Module-1", "MODULE - 2" (any dash type)
    "module": re.compile(r"^\s*module\s*[-–—]?\s*(\d+)\s*$", re.I),
    # "Q.1", "Q.01", "Q.10" at the start of a line, optionally followed by text
    "question": re.compile(r"^\s*Q\.?\s*0*(\d{1,2})\b\s*(.*)$"),
    # Sub-part letter at the start of a line: "a.", "a", "a. Explain", "b  Elucidate".
    # Only accepted if it is the *next expected* letter (checked in code),
    # so a wrapped line like "a neat diagram." is not mistaken for part a.
    "subpart": re.compile(r"^\s*([a-e])(?:\.|\s|$)\s*(.*)$"),
    # Marks: a line that is only a 1-2 digit number, e.g. "10", "08", "6 "
    "marks": re.compile(r"^\s*(\d{1,2})\s*$"),
    # Bloom's level / course outcome columns: "L2", "CO1", "L2 CO1"
    "level_co": re.compile(r"^\s*(L\d)?\s*(CO\d)?\s*$"),
    # Lines that are page furniture, not question text
    "noise": re.compile(
        r"^\s*("
        r"OR"                                  # between the two choices of a module
        r"|[*\s]+"                             # "* * * * *" end marker
        r"|USN|BCS\d+\w*|M|L|C|COs|Marks"      # column headers / code
        r"|\*?Bloom.*|Taxonomy|Level"          # model paper column header/footer
        r"|VTU-.*|\d{2}-\d{2}-\d{4}.*"         # download watermark timestamps
        r"|(AD\s*-\s*)+AD"                     # watermark
        r"|Page\s+\d+\s+of\s+\d+|\d+\s+of\s+\d+"  # page numbers
        r")\s*$",
        re.I,
    ),
    # End of the paper: "* * * * *" (VTU papers) or the model paper's
    # footer "Bloom’s Taxonomy Level: Indicate as L1, L2 ..."
    "end": re.compile(r"^\s*(\*\s*\*\s*\*|Bloom.s Taxonomy Level\s*:)", re.I),
}


def extract_text(pdf_bytes_or_path):
    """Return all text of a PDF (path or raw bytes), pages joined by newlines."""
    if isinstance(pdf_bytes_or_path, (bytes, bytearray)):
        doc = pymupdf.open(stream=pdf_bytes_or_path, filetype="pdf")
    else:
        doc = pymupdf.open(pdf_bytes_or_path)
    with doc:
        return "\n".join(page.get_text() for page in doc)


def is_scanned(text, min_chars=200):
    """Very rough check: a scanned PDF gives (almost) no extractable text."""
    return len(text.strip()) < min_chars


def split_questions(text, paper="paper"):
    """Split paper text into a list of dicts, one per sub-part.

    Each dict: paper, module, q_no, part, qid, text, marks.
    """
    rows = []
    module = None
    q_no = None
    current = None  # the sub-part currently being filled

    def close():
        if current is not None:
            current["text"] = re.sub(r"\s+", " ", " ".join(current["lines"])).strip()
            del current["lines"]
            rows.append(current)

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if PATTERNS["end"].match(line) and q_no is not None:
            break  # end of paper: ignore footer text after "* * * * *"
        m = PATTERNS["module"].match(line)
        if m:
            module = int(m.group(1))
            continue
        if module is None:
            continue  # still in the header (title, instructions)
        m = PATTERNS["question"].match(line)
        if m:
            close()
            current = None
            q_no = int(m.group(1))
            rest = m.group(2).strip()
            # Questions without sub-parts: text starts right after "Q.3"
            if rest and not PATTERNS["subpart"].match(rest):
                current = _new_row(paper, module, q_no, "", rest)
            elif rest:
                sm = PATTERNS["subpart"].match(rest)
                current = _new_row(paper, module, q_no, sm.group(1), sm.group(2))
            continue
        if q_no is None:
            continue
        m = PATTERNS["subpart"].match(line)
        if m and m.group(1) == _next_letter(current, q_no):
            close()
            current = _new_row(paper, module, q_no, m.group(1), m.group(2))
            continue
        if current is None:
            continue
        m = PATTERNS["marks"].match(line)
        if m and current["marks"] is None:
            current["marks"] = int(m.group(1))
            continue
        if PATTERNS["level_co"].match(line) or PATTERNS["noise"].match(line):
            continue
        current["lines"].append(line)
    close()
    return rows


def _new_row(paper, module, q_no, part, first_text):
    lines = [first_text] if first_text.strip() else []
    return {"paper": paper, "module": module, "q_no": q_no, "part": part,
            "qid": f"Q{q_no}{part}", "lines": lines, "marks": None}


def _next_letter(current, q_no):
    """The sub-part letter we expect next ('a' for a fresh question)."""
    if current is None or current["q_no"] != q_no or not current["part"]:
        return "a"
    return chr(ord(current["part"]) + 1)


def parse_pdf(pdf_bytes_or_path, paper="paper"):
    """Convenience: extract text and split it. Returns (rows, raw_text)."""
    text = extract_text(pdf_bytes_or_path)
    return split_questions(text, paper=paper), text
