#!/usr/bin/env python3
"""Check every reference against PubMed.

Author lists are the part that drifts silently: a truncated six-name list
reads plausibly whatever the names are, so five entries in this manuscript
carried names belonging to other papers until this script was written.
Run it before any submission; it needs network access.
"""
from __future__ import annotations
import pathlib, re, sys, urllib.request, xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "manuscript"))
import references as R

EUTILS = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
          "?db=pubmed&rettype=xml&id=")


def fetch(pmids):
    root = ET.fromstring(urllib.request.urlopen(EUTILS + ",".join(pmids),
                                                timeout=90).read())
    out = {}
    for art in root.iter("PubmedArticle"):
        au = []
        for a in art.iter("Author"):
            ln, ini = a.findtext("LastName"), a.findtext("Initials")
            if ln:
                au.append(f"{ln} {ini}" if ini else ln)
        issue = art.find(".//JournalIssue")
        out[art.findtext(".//PMID")] = {
            "authors": au,
            "journal": art.findtext(".//ISOAbbreviation"),
            "volume": issue.findtext("Volume") if issue is not None else None,
            "issue": issue.findtext("Issue") if issue is not None else None,
            "title": art.findtext(".//ArticleTitle"),
        }
    return out


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())


def main():
    pairs = [(k, R.REFS[k][8]) for k in R.ORDER if R.REFS[k][8]]
    no_pmid = [k for k in R.ORDER if not R.REFS[k][8]]
    got = fetch([p for _, p in pairs])
    fails = []
    for key, pmid in pairs:
        mine = R.REFS[key][0]
        rec = got.get(pmid)
        if rec is None:
            fails.append(f"{key} ({pmid}): not found in PubMed")
            continue
        trunc = mine[-1] == "et al"
        names = mine[:-1] if trunc else mine
        ref = rec["authors"][:len(names)]
        if names != ref:
            fails.append(f"{key} ({pmid}) authors\n     ours: {names}\n"
                         f"   pubmed: {ref}")
        if trunc and len(rec["authors"]) <= len(names):
            fails.append(f"{key}: 'et al' but PubMed lists "
                         f"{len(rec['authors'])} authors")
        if not trunc and len(rec["authors"]) > len(names):
            fails.append(f"{key}: {len(names)} authors listed but PubMed has "
                         f"{len(rec['authors'])}; needs 'et al'")
        # Titles are compared on letters and digits alone: the manuscript
        # sentence-cases them and restores proper nouns PubMed lowercases.
        ours, theirs = _norm(R.REFS[key][1]), _norm(rec["title"] or "")
        if ours and theirs and ours != theirs:
            fails.append(f"{key} ({pmid}) title\n     ours: {R.REFS[key][1]}\n"
                         f"   pubmed: {rec['title']}")
        for field, idx in (("journal", 2), ("volume", 4), ("issue", 5)):
            mine_v, their_v = R.REFS[key][idx], rec[field]
            if their_v and mine_v and str(their_v).lower() != str(mine_v).lower():
                fails.append(f"{key}: {field} ours={mine_v} pubmed={their_v}")
    print(f"{len(pairs)} references checked against PubMed")
    print(f"{len(no_pmid)} without a PMID (methodology originals): "
          f"{', '.join(no_pmid)}")
    if fails:
        print(f"\n{len(fails)} discrepancies:")
        for f in fails:
            print("  -", f)
        return 1
    print("\nall reference metadata matches PubMed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
