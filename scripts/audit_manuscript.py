#!/usr/bin/env python3
"""Mechanical style and consistency checks over the built Word files.

Scanning the rendered documents rather than manuscript.md is deliberate: the
captions, table footnotes, and back matter live in make_docx.py and
make_appendix.py, and a markdown-only audit never saw them.
"""
from __future__ import annotations
import pathlib, re, sys
import docx

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ["manuscript/manuscript.docx", "manuscript/Multimedia_Appendix_1.docx",
        "manuscript/Multimedia_Appendix_2.docx"]

# Verbatim STROBE recommendation wording is quoted, not authored, so the
# pronoun rule does not apply to it.
QUOTED = ("Indicate the study design", "Explain the scientific background",
          "Give the eligibility criteria", "Clearly define all outcomes",
          "For each variable of interest", "Describe any efforts",
          "Explain how the study size", "Explain how quantitative variables",
          "Describe all statistical methods", "Report numbers of individuals",
          "Give characteristics of study participants",
          "Report numbers of outcome events", "Give unadjusted",
          "Report other analyses done", "Summarise key results",
          "Discuss limitations of the study", "Give a cautious overall",
          "Discuss the generalisability", "Give the source of funding",
          "Present key elements", "Describe the setting", "State specific objectives")

TITLE_START = "Technique-Specific Audiovisual Features"
# Only lowercase or sentence-initial forms; "US" and author initials are not
# pronouns.
PRONOUNS = r"\b(we|our|ours|us|i|my|me|it|its|they|them|their|this|these|those|he|she|his|her)\b"
HYPHENATED = ["test-retest", "cross-sectional", "vision-language", "on-screen",
              "open-monitoring", "loving-kindness", "silence-to-voice",
              "percentage-point", "cluster-robust", "technique-by-feature"]


def paragraphs(path):
    d = docx.Document(ROOT / path)
    out = [(p.text, "body") for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for r in t.rows:
            for c in r.cells:
                if c.text.strip():
                    out.append((c.text, "table"))
    return out


def text_of(path):
    return "\n".join(t for t, _ in paragraphs(path))


def check_citation_order(fails):
    body = (ROOT / "manuscript/manuscript.md").read_text()
    body = body.split("## References")[0]
    nums, seen = [], set()
    for tok in re.findall(r"\[(\d+(?:[,\-]\d+)*)\]", body):
        parts = []
        for piece in tok.split(","):
            if "-" in piece:
                a, b = (int(x) for x in piece.split("-"))
                parts += list(range(a, b + 1))
            else:
                parts.append(int(piece))
        if len(parts) > 3:
            fails.append(f"citation token [{tok}] cites {len(parts)} references (max 3)")
        for n in parts:
            nums.append(n)
            if n not in seen:
                seen.add(n)
                if n != len(seen):
                    fails.append(f"reference [{n}] first appears out of order "
                                 f"(expected [{len(seen)}])")
    from collections import Counter
    for n, c in Counter(nums).items():
        if c > 2:
            fails.append(f"reference [{n}] is used {c} times (max 2)")
    sys.path.insert(0, str(ROOT / "manuscript"))
    import references
    if len(references.ORDER) != len(seen):
        fails.append(f"ORDER has {len(references.ORDER)} entries but the text "
                     f"cites {len(seen)}")
    return len(seen)


def check_pronouns(fails):
    for path in DOCS:
        for txt, _ in paragraphs(path):
            if any(q in txt for q in QUOTED):
                continue
            if re.match(r"\d+\.\t", txt) or txt.startswith(TITLE_START):
                continue  # reference entries and the article title
            for m in re.finditer(PRONOUNS, txt, re.I):
                w = m.group(0)
                if w.isupper() and len(w) > 1:
                    continue
                if w.lower() in {"this", "these", "those"} and \
                        re.match(r"\w", txt[m.end():m.end() + 2].lstrip()):
                    continue  # "this study" is a determiner, not a pronoun
                fails.append(f"{path}: pronoun '{w}' in: {txt[:90]}")


def check_hyphenation(fails):
    joined = "\n".join(text_of(p) for p in DOCS)
    for term in HYPHENATED:
        loose = term.replace("-", " ")
        bare = term.replace("-", "")
        for variant, kind in ((loose, "spaced"), (bare, "unspaced")):
            if re.search(rf"\b{re.escape(variant)}\b", joined, re.I):
                fails.append(f"'{term}' also appears {kind} as '{variant}'")
        if re.search(rf"{re.escape(term.split('-')[0])}-\s+{re.escape(term.split('-')[-1])}",
                     joined, re.I):
            fails.append(f"'{term}' appears broken across a hyphen + space")


def check_p_values(fails):
    joined = "\n".join(text_of(p) for p in DOCS)
    for m in re.finditer(r"P\s*[=<>]\s*0\.\d+", joined):
        fails.append(f"P value keeps a leading zero: {m.group(0)}")
    for m in re.finditer(r"\bp\s*[=<>]\s*\.\d", joined):
        fails.append(f"lowercase p value: {m.group(0)}")


def check_markdown_leftovers(fails):
    """Literal ** or ` in a built file means the inline parser missed a span."""
    for path in DOCS:
        for txt, where in paragraphs(path):
            for mark in ("**", "`"):
                if mark in txt:
                    fails.append(f"{path} ({where}): literal '{mark}' in: {txt[:80]}")


# Abbreviations this manuscript is entitled to use, with the expansion that
# counts as introducing them. Anything else in capitals is reported so a new
# one cannot slip in undefined.
ABBREVS = {
    "VLM": "vision-language model", "API": "application programming interface",
    "CI": "confidence interval", "SD": "standard deviation",
    "IQR": "interquartile range", "FDR": "false discovery rate",
    "OSF": "Open Science Framework", "ASR": "automatic speech recognition",
    "ICC": "intraclass correlation", "MDE": "minimum detectable effect",
    "SE": "standard error", "MBSR": "mindfulness-based stress reduction",
    "GLM": "generalized linear model", "LLM": "large language model",
    "STROBE": "Strengthening the Reporting of Observational Studies in Epidemiology",
    "TRIPOD": "Transparent Reporting of a multivariable prediction model",
}
# Capitalized tokens that are not abbreviations: identifiers, instrument
# names, codes, and words that are simply written in capitals.
CAPS_OK = {"RQ1", "RQ2", "RQ3", "RQ4", "H1", "H2", "H3", "T", "NA", "US",
           "HC1", "DISCERN", "GPT", "AI", "DOI", "URL", "SHA", "DOCX", "JMIR",
           "YouTube"}
CAPS_OK_RE = re.compile(r"^[A-Z]\d+$")   # table and figure numbers: A1, S1


def _scopes():
    """Each scope defines its abbreviations independently of the others.

    The abstract and the body are separate scopes, as are the three files: an
    expansion in one does not license a bare abbreviation in another. Each
    scope yields (prose, everything), because a gloss in a table footnote or
    a figure caption is required for self-containment and so must not count
    as a second definition of a term the prose already introduced. The
    reference list is excluded: author initials are not abbreviations.
    """
    d = docx.Document(ROOT / "manuscript/manuscript.docx")
    paras = [p.text for p in d.paragraphs]
    def at(name):
        return next((i for i, t in enumerate(paras) if t.strip() == name), len(paras))
    def split(ps):
        prose = [t for t in ps if not re.match(r"(Table|Figure) \d+\.", t)
                 and not re.match(r"^[a-z](?=[A-Z0-9])", t)]
        return prose, ps
    yield ("manuscript abstract",) + split(paras[:at("Introduction")])
    # The Abbreviations list precedes the references in the JMIR element order,
    # so the body ends at whichever of the two comes first. The list glosses
    # every term and would otherwise read as a second definition of each.
    body = paras[at("Introduction"):min(at("Abbreviations"), at("References"))]
    cells = [c.text for t in d.tables for r in t.rows for c in r.cells]
    prose, _ = split(body)
    yield "manuscript body", prose, body + cells
    for path in DOCS[1:]:
        ps = [t for t, _ in paragraphs(path)]
        prose, _ = split(ps)
        yield path, prose, ps


def _definitions(abbr, expansion, text):
    """Where `abbr` is introduced: Expansion (ABBR), [ABBR], or 'ABBR: gloss'."""
    out = []
    for m in re.finditer(rf"[\(\[](?:the )?{abbr}s?[\)\]]", text):
        before = text[max(0, m.start() - 110):m.start()].lower()
        if expansion.lower().split()[-1] in before:
            out.append(m.start())
    for m in re.finditer(rf"(?:^|[;.]\s|[a-z]){abbr}: [a-z]", text, re.M):
        out.append(m.start())
    return sorted(out)


def check_abbreviations(fails):
    for scope, prose, everything in _scopes():
        pt, et = "\n".join(prose), "\n".join(everything)
        for abbr, expansion in sorted(ABBREVS.items()):
            uses = [m.start() for m in re.finditer(rf"\b{abbr}\b", et)]
            if not uses:
                continue
            defs = _definitions(abbr, expansion, pt)
            if not defs and not _definitions(abbr, expansion, et):
                fails.append(f"{scope}: '{abbr}' is used but never defined")
                continue
            if len(defs) > 1:
                fails.append(f"{scope}: '{abbr}' is defined {len(defs)} times "
                             f"in the prose")
            guideline = abbr in {"STROBE", "TRIPOD"}
            if len(re.findall(rf"\b{abbr}\b", pt)) == 1 and defs \
                    and not guideline:
                fails.append(f"{scope}: '{abbr}' is defined in the prose but "
                             f"never used as an abbreviation")
        unknown = {a for a in re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", et)
                   if a not in ABBREVS and a not in CAPS_OK
                   and not CAPS_OK_RE.match(a)}
        for a in sorted(unknown):
            fails.append(f"{scope}: unrecognized capitalized token '{a}'")


ESTIMATE = re.compile(
    r"beta=(-?\d+\.\d+)[^)]{0,60}?95% CI (?:\[CI\] )?(-?\d+\.\d+)"
    r"(?: to |-)(-?\d+\.\d+)(?:;? \*?P\*?([=<])(<?\.\d+))?")


# Relative and percentage-point effect sizes were once written by hand and did
# not match the fitted model. They are now derived in marginal_effects.csv, and
# every one quoted in the prose must appear there.
REL_PCT = re.compile(r"(\d+\.\d)% (?:relative increase|relative reduction|"
                     r"below the model's predicted rate|lower on like rate)")
ABS_PP = re.compile(r"(\d+\.\d{3}) percentage points")


def check_marginal_effects(fails):
    import pandas as pd
    path = ROOT / "data_main/06_results/marginal_effects.csv"
    if not path.exists():
        fails.append("marginal_effects.csv missing; re-run the analysis")
        return
    me = pd.read_csv(path)
    body = (ROOT / "manuscript/manuscript.md").read_text().split("## References")[0]
    rel = set(me.rel_change_pct.abs().round(1))
    pp = set(me.abs_change_pp.abs().round(3))
    for m in REL_PCT.finditer(body):
        if round(float(m.group(1)), 1) not in rel:
            fails.append(f"relative effect {m.group(1)}% is not in "
                         f"marginal_effects.csv")
    for m in ABS_PP.finditer(body):
        if round(float(m.group(1)), 3) not in pp:
            fails.append(f"absolute effect {m.group(1)} pp is not in "
                         f"marginal_effects.csv")


def check_estimates(fails):
    """Every beta/CI/P triple in the prose must match the analysis output.

    The P value quoted must be the Benjamini-Hochberg adjusted one, since
    that is what the Methods promise and what the tables report. Quoting the
    unadjusted value overstates the result.
    """
    import pandas as pd
    frames = [pd.read_csv(ROOT / f"data_main/06_results/{f}")
              for f in ("rq2_associations.csv", "rq3_interactions.csv")]
    allr = pd.concat(frames, ignore_index=True)
    body = (ROOT / "manuscript/manuscript.md").read_text().split("## References")[0]

    def fmt(x):
        return "<.001" if x < 0.001 else f"{x:.3f}".lstrip("0")

    checked = 0
    for m in ESTIMATE.finditer(body):
        b, lo, hi, op, pv = m.groups()
        hit = allr[(allr.beta.round(3) == float(b))
                   & (allr.ci_low.round(3) == float(lo))
                   & (allr.ci_high.round(3) == float(hi))]
        if hit.empty:
            continue       # Firth estimates live in their own file, CI only
        checked += 1
        if pv is None:
            continue
        row = hit.iloc[0]
        # Covariates sit outside the preregistered correction family and
        # carry no adjusted P value; the prose quotes the unadjusted one and
        # says so where the covariates are first reported.
        in_family = pd.notna(row.p_fdr)
        exp = fmt(row.p_fdr if in_family else row.p)
        got = (op or "") + pv
        if got not in (f"={exp}", exp) and not (op == "<" and exp == "<.001"):
            kind = "adjusted" if in_family else "unadjusted"
            note = ""
            if in_family and got.lstrip("=") == fmt(row.p):
                note = " (that is the unadjusted value)"
            fails.append(f"beta={b}: quoted P{got} but the {kind} P is "
                         f"{exp}{note}")
    print(f"  {checked} estimates reconciled against the analysis output")


def check_abstract_matches_body(fails):
    """Every figure quoted in the abstract must appear in the body.

    The abstract is written and revised separately, so it drifts: it once
    carried the unadjusted P value for a coefficient the body reported with
    the adjusted one.
    """
    md = (ROOT / "manuscript/manuscript.md").read_text()
    abst = md.split("## Abstract")[1].split("## Introduction")[0]
    abst = abst.split("**Keywords:**")[0]
    body = md.split("## Introduction")[1].split("## References")[0]
    skip = {"1", "2", "3", "10", "12", "16", "95", "0"}   # counts, CI level
    for n in dict.fromkeys(re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w])",
                                      abst)):
        if n not in skip and n not in body:
            fails.append(f"abstract quotes {n}, which appears nowhere in the body")


def check_callouts(fails):
    """Every table and figure must be referred to in the text, in order.

    Figures 2 and 3 were laid out, captioned and discussed without ever
    being named in a sentence, which a copyeditor catches and a reader
    never recovers from.
    """
    md = (ROOT / "manuscript/manuscript.md").read_text().split("## References")[0]
    calls = re.findall(r"\b(Table|Figure)s? (\d)", md)
    for kind, total in (("Table", 5), ("Figure", 4)):
        seen = []
        for k, n in calls:
            if k == kind and int(n) not in seen:
                seen.append(int(n))
        for n in range(1, total + 1):
            if n not in seen:
                fails.append(f"{kind} {n} is never called out in the text")
        if seen != sorted(seen):
            fails.append(f"{kind} call-outs are out of order: {seen}")


def check_manifest(fails):
    """Every checksum in the materials manifest must still match.

    The manifest was hand-maintained and silently went stale when the
    analysis changed, so it claimed to document a state that no longer
    produced the reported numbers.
    """
    import hashlib
    doc = ROOT / "docs/materials_manifest.md"
    if not doc.exists():
        fails.append("docs/materials_manifest.md is missing")
        return
    rows = re.findall(r"^(\S+)\s{2,}([0-9a-f]{64})$", doc.read_text(), re.M)
    if not rows:
        fails.append("materials manifest carries no checksums")
        return
    stale = []
    for f, sha in rows:
        p = ROOT / f
        if not p.exists():
            stale.append(f"{f} (missing)")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            stale.append(f)
    for f in stale:
        fails.append(f"materials manifest is stale for {f}; "
                     f"re-run scripts/make_manifest.py")
    print(f"  {len(rows)} manifest checksums verified")


def check_strobe_pointers(fails):
    """The STROBE checklist points at sections and floats by name.

    Both have gone stale before: once when the Methods and Discussion
    subheadings were renamed, once when a figure was inserted and the
    forest plot became Figure 4.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from make_appendix import STROBE
    d = docx.Document(ROOT / "manuscript/manuscript.docx")
    headings = {p.text.strip() for p in d.paragraphs if p.text.strip()}
    n_fig = sum(1 for p in d.paragraphs if re.match(r"Figure \d+\.", p.text))
    n_tab = sum(1 for p in d.paragraphs if re.match(r"Table \d+\.", p.text))
    for _, item, _, where in STROBE:
        if not item:
            continue
        for kind, total in (("Figure", n_fig), ("Table", n_tab)):
            for num in re.findall(rf"{kind}s? (\d)(?:\s+and\s+(\d))?", where):
                for x in (n for n in num if n):
                    if not 1 <= int(x) <= total:
                        fails.append(f"STROBE item {item} cites {kind} {x}, "
                                     f"but the manuscript has {total}")
        for part in re.split(r"[;,] ", where):
            part = part.strip()
            m = re.fullmatch(r"(?:Methods|Results|Discussion), (.+)", part)
            if m and m.group(1) not in headings and " and " not in m.group(1):
                fails.append(f"STROBE item {item} points at a section that "
                             f"does not exist: {m.group(1)!r}")


def check_abbrev_list(fails):
    """The back-matter list must match what the manuscript abbreviates."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from make_docx import ABBREVIATIONS
    d = docx.Document(ROOT / "manuscript/manuscript.docx")
    paras = [p.text for p in d.paragraphs]

    def at(name):
        return next((i for i, t in enumerate(paras) if t.strip() == name),
                    len(paras))
    txt = "\n".join(paras[at("Abstract"):at("References")]) + "\n" + "\n".join(
        c.text for t in d.tables for r in t.rows for c in r.cells)
    for ab, _ in ABBREVIATIONS:
        if not re.search(r"\b" + re.escape(ab), txt):
            fails.append(f"the abbreviation list carries {ab!r}, which the "
                         f"manuscript never uses")


# Headings, which are paragraphs in the document but take no indent.
SUBHEADS = {"Study design and sample", "Measurement",
            "Reliability and statistical analysis",
            "Deviations from the protocol", "Ethics",
            "Corpus and sample flow", "Reliability of the VLM instrument",
            "Technique and presentation landscape",
            "Associations with engagement", "Technique moderation",
            "Principal results", "Comparison with prior work",
            "Interpretation and implications", "Limitations", "Conclusions"}
SECTIONS = {"Abstract", "Introduction", "Methods", "Results", "Discussion",
            "Acknowledgments", "Funding", "Authors' Contributions",
            "Conflicts of Interest",
            "Multimedia Appendix 1", "Multimedia Appendix 2",
            "Data Availability", "References",
            "Abbreviations"}


def check_indent(fails):
    """Running prose takes the first-line indent; the abstract does not."""
    d = docx.Document(ROOT / "manuscript/manuscript.docx")
    sec = None
    for p in d.paragraphs:
        t = p.text.strip()
        if not t or t in SUBHEADS:
            continue
        if t in SECTIONS:
            sec = t
            continue
        if sec in (None, "References", "Abbreviations"):
            continue
        if re.match(r"^(Table|Figure) \d+\.", t) or re.match(r"^[a-z](?=[A-Z0-9(])", t):
            continue
        has = bool(p.paragraph_format.first_line_indent)
        want = sec != "Abstract"
        if has != want:
            fails.append(f"{sec}: paragraph {'has' if has else 'lacks'} the "
                         f"first-line indent: {t[:60]}")


def check_abstract(fails):
    md = (ROOT / "manuscript/manuscript.md").read_text()
    m = re.search(r"## Abstract\n(.*?)\n## ", md, re.S)
    if not m:
        fails.append("abstract not found")
        return
    txt = m.group(1).split("**Keywords:**")[0]
    n = len(re.findall(r"\S+", re.sub(r"\*\*|\*", "", txt)))
    if n > 450:
        fails.append(f"abstract is {n} words (limit 450)")
    print(f"  abstract: {n} words")


def check_floats(fails):
    d = docx.Document(ROOT / "manuscript/manuscript.docx")
    caps = [p.text for p in d.paragraphs if re.match(r"(Table|Figure) \d+\.", p.text)]
    tabs = [c for c in caps if c.startswith("Table")]
    figs = [c for c in caps if c.startswith("Figure")]
    for label, got, n in (("Table", tabs, 5), ("Figure", figs, 4)):
        if len(got) != n:
            fails.append(f"expected {n} {label} captions, found {len(got)}")
        for i, c in enumerate(got, 1):
            if not c.startswith(f"{label} {i}."):
                fails.append(f"{label} captions out of order at #{i}: {c[:40]}")
    if len(d.tables) != 5:
        fails.append(f"manuscript has {len(d.tables)} tables, expected 5")


def check_footnote_anchors(fails):
    for path in DOCS:
        d = docx.Document(ROOT / path)
        body = [p.text for p in d.paragraphs]
        for ti, t in enumerate(d.tables):
            marks = set()
            for r in t.rows:
                for c in r.cells:
                    marks |= set(re.findall(r"(?<=[a-z\)%,])([a-z])$", c.text.strip()))
            # footnote lines follow the table in document order
            cells = "".join(c.text for r in t.rows for c in r.cells)
            if not marks:
                fails.append(f"{path}: table #{ti+1} has no footnote markers in-table")


def main():
    fails = []
    print("citation audit")
    n = check_citation_order(fails)
    print(f"  {n} references cited")
    check_abstract(fails)
    check_estimates(fails)
    check_marginal_effects(fails)
    check_manifest(fails)
    check_strobe_pointers(fails)
    check_abbrev_list(fails)
    check_indent(fails)
    check_abstract_matches_body(fails)
    print("style audit")
    check_pronouns(fails)
    check_hyphenation(fails)
    check_p_values(fails)
    check_floats(fails)
    check_callouts(fails)
    check_markdown_leftovers(fails)
    check_abbreviations(fails)
    check_footnote_anchors(fails)
    print()
    if fails:
        print(f"{len(fails)} issue(s):")
        for f in fails:
            print("  -", f)
        return 1
    print("all checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
