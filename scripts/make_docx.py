#!/usr/bin/env python3
"""Build the three submission Word files.

Formatting follows the JMIR profile in the project house rules: Times New
Roman throughout, body and headings 11pt, tables/captions/footnotes/references
10pt, double line spacing in the body, a one-character first-line indent on
body paragraphs only, justified text, headings in bold JMIR blue, three-line
tables with the caption above, figure captions below, and a numbered reference
list with a hanging indent.
"""
from __future__ import annotations

import pathlib
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "manuscript"))

BODY_PT, SMALL_PT = 11, 10
JMIR_BLUE = RGBColor(0x2E, 0x74, 0xB5)
INDENT = Pt(11)          # one character at 11pt == 220 twips
FONT = "Times New Roman"


# ------------------------------------------------------------------ helpers
def _set_font(run, size=BODY_PT, bold=False, italic=False, color=None):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rf.set(qn(a), FONT)
    rf.set(qn("w:eastAsia"), "Malgun Gothic")


def _para(doc, *, indent=False, spacing=2.0, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
          space_after=0):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.DOUBLE if spacing == 2.0 else None
    if spacing != 2.0:
        pf.line_spacing = spacing
    pf.space_before = Pt(0)
    pf.space_after = Pt(space_after)
    pf.alignment = align
    if indent:
        pf.first_line_indent = INDENT
    return p


INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|`[^`]+?`)")


def _runs(p, text, size=BODY_PT, bold=False, italic=False):
    """Render a markdown-ish inline string into runs.

    Emphasis nests: a bold span recurses so that code spans inside it are
    stripped too. A flat pass left the inner backticks printed literally.
    """
    for tok in INLINE.split(text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            _runs(p, tok[2:-2], size, bold=True, italic=italic)
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            _runs(p, tok[1:-1], size, bold=bold, italic=True)
        elif tok.startswith("`") and tok.endswith("`") and len(tok) > 2:
            _set_font(p.add_run(tok[1:-1]), size, bold=bold, italic=italic)
        elif italic:
            _set_font(p.add_run(tok), size, bold=bold, italic=True)
        else:
            _write_p(p, tok, size, bold=bold)


# JMIR sets the statistical P as an italic capital, in table headers and
# footnotes as well as in running text.
P_STAT = re.compile(r"\bP\b(?=\s*(?:values?\b|[=<>]))")


def _write_p(para, text, size, *, bold=False):
    """Write text into a paragraph, italicising the statistical P."""
    pos = 0
    for m in P_STAT.finditer(text):
        if m.start() > pos:
            _set_font(para.add_run(text[pos:m.start()]), size, bold=bold)
        _set_font(para.add_run("P"), size, bold=bold, italic=True)
        pos = m.end()
    if pos < len(text):
        _set_font(para.add_run(text[pos:]), size, bold=bold)


def heading(doc, text, level=1):
    p = _para(doc, spacing=2.0, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=0)
    _set_font(p.add_run(text), BODY_PT, bold=True, color=JMIR_BLUE)
    return p


def _cell_marker(cell, letters, size=SMALL_PT):
    """Append superscript footnote letters to a cell already written."""
    p = cell.paragraphs[0]
    run = p.add_run(",".join(letters))
    _set_font(run, size)
    run.font.superscript = True


def _cell_text(cell, text, *, bold=False, size=SMALL_PT, align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.alignment = align
    lead = len(text) - len(text.lstrip(" "))
    if lead:
        p.paragraph_format.left_indent = Pt(8)
    _write_p(p, text.strip(), size, bold=bold)


def _row_rules(table):
    """Repeat the header row on every page and never split a row across a
    page break. A table that runs over a page break otherwise shows four
    unlabelled columns of numbers on every continuation page."""
    for i, row in enumerate(table.rows):
        trPr = row._tr.get_or_add_trPr()
        for tag in ("w:tblHeader", "w:cantSplit"):
            for el in trPr.findall(qn(tag)):
                trPr.remove(el)
        el = OxmlElement("w:cantSplit")
        trPr.append(el)
        if i == 0:
            trPr.append(OxmlElement("w:tblHeader"))


def _cell_margins(table, top=70, bottom=70, left=90, right=90):
    """Vertical breathing room inside every cell. Word's default is zero top
    and bottom, which is what makes the header row look cramped."""
    tblPr = table._tbl.tblPr
    for el in tblPr.findall(qn("w:tblCellMar")):
        tblPr.remove(el)
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", top), ("left", left),
                      ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def _borders(table, n_rows):
    """Three-line rule: line above header, below header, below last row."""
    tbl = table._tbl
    for prop in tbl.iter(qn("w:tblBorders")):
        prop.getparent().remove(prop)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        borders.append(el)
    tbl.tblPr.append(borders)

    def rule(row, where):
        for cell in row.cells:
            tcpr = cell._tc.get_or_add_tcPr()
            tcb = tcpr.find(qn("w:tcBorders"))
            if tcb is None:
                tcb = OxmlElement("w:tcBorders")
                tcpr.append(tcb)
            el = OxmlElement(f"w:{where}")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "8")      # 1pt
            el.set(qn("w:color"), "000000")
            tcb.append(el)

    rule(table.rows[0], "top")
    rule(table.rows[0], "bottom")
    rule(table.rows[n_rows - 1], "bottom")


def _widths(table, inches):
    """Fixed column widths. Word honours cell widths only when the table
    layout is explicitly fixed, so the layout element is set as well."""
    from docx.shared import Inches as _In
    table.autofit = False
    tblPr = table._tbl.tblPr
    for el in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(el)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    for col, w in zip(table.columns, inches):
        col.width = _In(w)
    for row in table.rows:
        for cell, w in zip(row.cells, inches):
            cell.width = _In(w)


def add_table(doc, number, spec, widths=None):
    cap = _para(doc, spacing=1.0, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=4)
    _set_font(cap.add_run(f"Table {number}. "), SMALL_PT, bold=True)
    _set_font(cap.add_run(spec["caption"]), SMALL_PT)

    cols = spec["columns"]
    t = doc.add_table(rows=len(spec["rows"]) + 1, cols=len(cols))
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    t.autofit = True

    # A column is numeric when most of its non-empty cells start with a digit,
    # a minus, or "<". Header and body then share one alignment, so the column
    # does not read as two differently-aligned stacks.
    numeric = []
    for j in range(len(cols)):
        vals = [str(r[j]).strip() for r in spec["rows"] if str(r[j]).strip()]
        hits = sum(1 for v in vals if re.match(r"^[-<]?[\d.]", v))
        numeric.append(bool(vals) and hits >= max(1, int(0.6 * len(vals))))
    align = [WD_ALIGN_PARAGRAPH.RIGHT if n else WD_ALIGN_PARAGRAPH.LEFT
             for n in numeric]

    for j, c in enumerate(cols):
        _cell_text(t.rows[0].cells[j], c, bold=True, align=align[j])
    bold_rows = set(spec.get("bold_rows") or ())
    for i, row in enumerate(spec["rows"], start=1):
        for j, v in enumerate(row):
            _cell_text(t.rows[i].cells[j], str(v), align=align[j],
                       bold=(i - 1) in bold_rows)
    # Anchor each footnote letter inside the table. A letter printed only
    # below the table refers to nothing, which is what the tables did before.
    # Footnotes are relabelled in reading order of their anchors, so the
    # letters run a, b, c down and across the table rather than arbitrarily.
    anchors = list(spec.get("anchors") or [])
    anchors += [None] * (len(spec["footnotes"]) - len(anchors))
    def _rc(target):
        if target is None:
            return None
        return (0, target[1]) if target[0] == "header" else (target[1], target[2])
    pos = [_rc(a) for a in anchors]
    order = sorted(range(len(spec["footnotes"])),
                   key=lambda i: pos[i] if pos[i] else (10**6, 10**6))
    footnotes = [spec["footnotes"][i] for i in order]
    at = {}
    for k, i in enumerate(order):
        if pos[i] is not None:
            at.setdefault(pos[i], []).append(chr(ord("a") + k))
    for rc, letters in at.items():
        _cell_marker(t.rows[rc[0]].cells[rc[1]], letters)

    if widths or spec.get("widths"):
        _widths(t, widths or spec["widths"])
    _cell_margins(t)
    _row_rules(t)
    _borders(t, len(spec["rows"]) + 1)

    for k, fn in enumerate(footnotes):
        p = _para(doc, spacing=1.0, align=WD_ALIGN_PARAGRAPH.LEFT,
                  space_after=2 if k < len(spec["footnotes"]) - 1 else 6)
        sup = p.add_run(chr(ord("a") + k))
        _set_font(sup, SMALL_PT)
        sup.font.superscript = True
        _write_p(p, fn, SMALL_PT)


def add_figure(doc, number, path, caption, width=6.3):
    # The manuscript embeds the draft JPG, capped at 1200 px on the longer
    # side; the full-resolution PNG beside it is what gets uploaded with the
    # submission.
    from PIL import Image
    if not path.exists():
        raise SystemExit(f"figure missing: {path}")
    w, h = Image.open(path).size
    if path.suffix.lower() in (".jpg", ".jpeg") and max(w, h) > 1200:
        raise SystemExit(f"{path.name} is {w}x{h}; the draft JPG must be "
                         f"1200 px or less on the longer side")
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = _para(doc, spacing=1.0, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=6)
    _set_font(p.add_run(f"Figure {number}. "), SMALL_PT, bold=True)
    _set_font(p.add_run(caption), SMALL_PT)


def base_doc():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(BODY_PT)
    st.paragraph_format.space_before = Pt(0)
    st.paragraph_format.space_after = Pt(0)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(1)
        s.top_margin = s.bottom_margin = Inches(1)
    return doc


# ------------------------------------------------------- markdown -> blocks
SKIP_SECTIONS = {"Data and code availability", "Open items before submission"}


def parse_markdown(md: str):
    """Yield (kind, text) blocks for the manuscript body."""
    lines = md.split("\n")
    blocks, buf, skip = [], [], False
    def flush():
        if buf:
            blocks.append(("p", " ".join(x.strip() for x in buf).strip()))
            buf.clear()
    for ln in lines:
        if ln.startswith("## "):
            flush()
            name = ln[3:].strip()
            skip = name in SKIP_SECTIONS
            if not skip:
                blocks.append(("h1", name))
            continue
        if ln.startswith("### "):
            flush()
            if not skip:
                blocks.append(("h2", ln[4:].strip()))
            continue
        if skip:
            continue
        if ln.strip() in ("", "---"):
            flush()
            continue
        if re.match(r"^\d+\.\s", ln.strip()):
            flush()
            blocks.append(("li", re.sub(r"^\d+\.\s", "", ln.strip())))
            continue
        if ln.strip().startswith("- "):
            flush()
            blocks.append(("li", ln.strip()[2:]))
            continue
        # A 3-space-indented line continues the list item above it. The
        # guard used to require a non-empty buffer, which is the opposite
        # of the truth: right after a list item the buffer is always empty,
        # so the first continuation line fell through and was emitted as a
        # separate paragraph after the following item.
        if not buf and blocks and blocks[-1][0] == "li" and ln.startswith("   "):
            blocks[-1] = ("li", blocks[-1][1] + " " + ln.strip())
            continue
        buf.append(ln)
    flush()
    return blocks


# ------------------------------------------------------------- manuscript
TITLE = ("Technique-Specific Audiovisual Features of Guided Meditation Videos on "
         "YouTube and Their Association With Viewer Engagement: A Vision-Language "
         "Model-Based Content Analysis")

FIG_CAPTIONS = {
    1: ("Study flow from search hits to the dual-coded analytic corpus. "
        "Exclusion counts are shown to the right of each step."),
    2: ("Reliability of each coded variable across the three arms, against the "
        "inclusion threshold. Values are Krippendorff alpha; the "
        "shaded band marks the region below the 0.60 gate, and variable names in "
        "orange mark the variables falling below that gate. Inter-model values "
        "are labelled directly."),
    3: ("Presentation features by meditation technique, as percentages "
        "within technique: the presenter columns and the setting columns each "
        "sum to 100 across a row, while the three feature columns are "
        "independent. Bars give the number of videos per technique, and <1 "
        "marks a nonzero cell below 1%."),
    4: ("Adjusted associations between presentation features and each "
        "engagement outcome, with 95% confidence intervals. Panels carry "
        "separate horizontal scales. Continuous predictors are standardized, "
        "so the corresponding coefficients are per standard deviation (SD). "
        "CI: confidence interval."),
}

# Only abbreviations the manuscript actually uses in abbreviated form.
# ASR, GLM, LLM and OSF were spelled out when the one-off definitions were
# removed, and listing them here outlasted that change.
ABBREVIATIONS = [
    ("API", "application programming interface"),
    ("CI", "confidence interval"),
    ("HC1", "heteroskedasticity-consistent covariance estimator, type 1"),
    ("ICC", "intraclass correlation coefficient"),
    ("IQR", "interquartile range"),
    ("NA", "not applicable or not assessable"),
    ("RQ", "research question"),
    ("SD", "standard deviation"),
    ("STROBE", "Strengthening the Reporting of Observational Studies in Epidemiology"),
    ("VLM", "vision-language model"),
]

BACK_MATTER = [
    ("Acknowledgments",
     "Author and institutional details are withheld for peer review."),
    ("Funding", "No specific funding was received for this work."),
    ("Conflicts of Interest",
     "The authors declare no competing interests."),
    ("Data Availability",
     "The dataset supporting the conclusions reported here contains YouTube video "
     "identifiers and the derived codes only; no original video or audio is "
     "redistributed, in accordance with the YouTube API Services Terms of Service. "
     "That dataset, the analysis code, the frozen codebook, the output schema, the "
     "coding prompts, the study protocol, the analysis plan with eleven amendments "
     "and one correction, and a SHA-256 manifest of every frozen file are openly "
     "available at https://github.com/jmyoun07/meditation-vlm. The amendments are reproduced in full in Multimedia "
     "Appendix 1. The repository was published after the analysis was complete and "
     "the materials were never deposited in a study registry, so no date among "
     "the materials can be verified independently of the files themselves "
     "(Amendment 9)."),
    ("Authors' Contributions",
     "Author contributions are withheld for peer review and will be completed "
     "in the unblinded submission file."),
]

# Placed after the Abbreviations list, per the JMIR element order.
APPENDIX_BLOCK = [
    ("Multimedia Appendix 1",
     "Supplementary methods and results: the frozen codebook variables and coding "
     "prompts, the full technique-by-feature interaction table, the post-hoc "
     "precision analysis of the realized design, the attrition comparison between "
     "coded and uncoded eligible videos, and the eleven protocol amendments "
     "and one correction in full. DOCX file."),
    ("Multimedia Appendix 2",
     "Completed STROBE checklist for cross-sectional studies, locating each of "
     "the 22 items in this manuscript. DOCX file."),
]


def build_manuscript():
    import make_tables
    import references as R

    md = (ROOT / "manuscript/manuscript.md").read_text()
    body = md[md.index("## Abstract"):]
    tables = make_tables.build()
    doc = base_doc()

    p = _para(doc, spacing=2.0, align=WD_ALIGN_PARAGRAPH.LEFT)
    _set_font(p.add_run(TITLE), 13, bold=True, color=JMIR_BLUE)
    # Blinded for peer review, in the form this group's earlier JMIR
    # submission used; the unblinded file carries the real details.
    for line in ("Author information withheld for peer review",
                 "Affiliations withheld for peer review",
                 "Corresponding Author: Corresponding author information "
                 "withheld for peer review"):
        p = _para(doc, spacing=2.0, align=WD_ALIGN_PARAGRAPH.LEFT)
        _set_font(p.add_run(line), BODY_PT)

    # where each table and figure is placed, keyed on the heading that precedes it
    table_widths = {
        1: [3.45, 3.00],
        # Table 2 gains a column once the human arm exists.
        2: [2.10, 0.95, 0.95, 1.25, 1.45],
        "2+human": [1.90, 0.85, 0.85, 1.10, 0.85, 0.95],
        3: [3.85, 1.35, 1.25],
        4: [3.05, 1.10, 1.70, 0.85],
        5: [3.55, 1.00, 1.45, 0.70],
    }
    after_heading = {
        "Corpus and sample flow": [("fig", 1), ("tab", 1)],
        "Reliability of the VLM instrument": [("fig", 2), ("tab", 2)],
        "Technique and presentation landscape": [("fig", 3), ("tab", 3)],
        "Associations with engagement": [("fig", 4), ("tab", 4)],
        "Technique moderation": [("tab", 5)],
    }
    pending, first_para_of_section = [], False
    section = ""

    for kind, text in parse_markdown(body):
        if kind == "h1":
            heading(doc, text, 1)
            first_para_of_section = True
            section = text
        elif kind == "h2":
            heading(doc, text, 2)
            first_para_of_section = True
            pending = list(after_heading.get(text, []))
        elif kind == "li":
            p = _para(doc, spacing=2.0, space_after=0)
            p.paragraph_format.left_indent = Pt(18)
            p.paragraph_format.first_line_indent = Pt(-9)
            _runs(p, text)
        else:
            if text.startswith("**Keywords:**"):
                p = _para(doc, spacing=2.0)
                _runs(p, text)
                continue
            # Every paragraph of running prose takes the first-line indent,
            # including the one that opens a section: the heading above it
            # already separates it, and skipping it left the indent looking
            # applied at random. The abstract is a set of labelled blocks
            # rather than running prose and takes none.
            indent = section != "Abstract"
            p = _para(doc, indent=indent, spacing=2.0)
            _runs(p, text)
            first_para_of_section = False
            for what, num in pending:
                if what == "fig":
                    add_figure(doc, num, ROOT / f"manuscript/figures/figure{num}_"
                               f"{['flow','reliability','landscape','forest'][num-1]}.jpg",
                               FIG_CAPTIONS[num])
                else:
                    add_table(doc, num, tables[num - 1],
                              widths=table_widths.get(
                                  f"{num}+human"
                                  if num == 2 and len(tables[num - 1]["columns"]) == 6
                                  else num))
            pending = []

    placed = {w for v in after_heading.values() for w in v}
    expected = {("fig", i) for i in (1, 2, 3, 4)} | {("tab", i) for i in range(1, 6)}
    missing = expected - placed
    if missing or pending:
        raise SystemExit(
            f"build aborted: {sorted(missing)} never placed, {pending} left over. "
            f"A heading in after_heading no longer matches a heading in the text.")

    for title, text in BACK_MATTER:
        heading(doc, title, 1)
        p = _para(doc, indent=True, spacing=2.0)
        _runs(p, text)

    heading(doc, "Abbreviations", 1)
    for ab, full in ABBREVIATIONS:
        p = _para(doc, spacing=1.5, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=0)
        _set_font(p.add_run(ab), SMALL_PT, bold=True)
        _set_font(p.add_run(f": {full}"), SMALL_PT)

    for title, text in APPENDIX_BLOCK:
        heading(doc, title, 1)
        p = _para(doc, indent=True, spacing=2.0)
        _runs(p, text)

    heading(doc, "References", 1)
    for i, line in enumerate(R.reference_list(), 1):
        p = _para(doc, spacing=1.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=2)
        pf = p.paragraph_format
        pf.left_indent = Pt(32)
        pf.first_line_indent = Pt(-32)
        _set_font(p.add_run(f"{i}.\t"), SMALL_PT)
        _set_font(p.add_run(line), SMALL_PT)

    out = ROOT / "manuscript/manuscript.docx"
    doc.save(out)
    return out


if __name__ == "__main__":
    print("wrote", build_manuscript())
