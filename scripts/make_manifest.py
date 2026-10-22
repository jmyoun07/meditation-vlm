#!/usr/bin/env python3
"""Regenerate the SHA-256 block of docs/materials_manifest.md.

The manifest was hand-maintained and drifted: after the false discovery
rate family was corrected, four of its forty checksums no longer matched
the files that produce the reported results, including the analysis module
and both result files. A manifest that does not match is worse than none,
so it is generated from the file list rather than edited.
"""
from __future__ import annotations
import hashlib, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/materials_manifest.md"

GROUPS = [
    ("", ["codebook/codebook.md", "codebook/schema.json",
          "codebook/prompts/coding_v1.md", "codebook/prompts/coding_v2.md",
          "codebook/prompts/eligibility_v1.md", "config/config.example.yaml", "config/config.reported.yaml",
          "config/eligibility.yaml", "config/seed_queries.yaml",
          "ANALYSIS_PLAN.md", "docs/power_analysis.md",
          "유튜브_meditation_vlm_protocol.docx"]),
    ("# Pipeline source",
     sorted([str(p.relative_to(ROOT)) for p in (ROOT / "scripts").glob("*.py")
             if re.match(r"\d", p.name)]
            + [str(p.relative_to(ROOT)) for p in (ROOT / "scripts").glob("*.sh")]
            + [str(p.relative_to(ROOT)) for p in (ROOT / "scripts").glob("session_*.py")]
            + [str(p.relative_to(ROOT))
               for p in (ROOT / "src/meditation_vlm").glob("*.py")])),
    ("# Manuscript build",
     sorted(str(p.relative_to(ROOT)) for p in (ROOT / "scripts").glob("make_*.py"))
     + ["scripts/audit_manuscript.py", "scripts/verify_references.py",
        "manuscript/manuscript.md", "manuscript/references.py"]),
    ("# Main-run outputs (reliability + results)",
     ["data_main/07_share/analytic_dataset.csv",
      "data_main/05_reliability/reliability_report.json",
      "data_main/06_results/corpus_characteristics.json",
      "data_main/06_results/analysis_summary.json",
      "data_main/06_results/h1_firth.csv",
      "data_main/06_results/rq1_descriptives.json",
      "data_main/06_results/rq2_associations.csv",
      "data_main/06_results/rq3_interactions.csv"]),
]


def main() -> int:
    lines, missing = ["```", f"{'FILE':<76}SHA-256"], []
    for header, files in GROUPS:
        if header:
            lines += ["", header]
        for f in files:
            p = ROOT / f
            if not p.exists():
                missing.append(f)
                continue
            lines.append(f"{f:<76}{hashlib.sha256(p.read_bytes()).hexdigest()}")
    lines.append("```")
    if missing:
        print("missing, not listed:", missing)

    txt = DOC.read_text()
    if not re.search(r"```\nFILE.*?\n```", txt, flags=re.S):
        print(f"no checksum block found in {DOC}; nothing written")
        return 1
    new = re.sub(r"```\nFILE.*?\n```", "\n".join(lines), txt, flags=re.S)
    if new == txt:
        print(f"{DOC} already current — no checksum changed")
        return 0
    DOC.write_text(new)
    n = sum(len(f) for _, f in GROUPS) - len(missing)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    print(f"wrote {DOC} — {n} files, at {head[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
