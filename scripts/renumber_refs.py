#!/usr/bin/env python3
"""Renumber citations into order of first appearance.

The reference numbers were previously fixed by hand in references.ORDER, so an
insertion anywhere in the text silently broke the ordering requirement. This
script derives the order from the manuscript itself and rewrites both the text
and ORDER, making the invariant enforceable rather than remembered.
"""
from __future__ import annotations
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "manuscript"))
import references as R

MD = ROOT / "manuscript/manuscript.md"
CITE = re.compile(r"\[(\d+(?:\s*[,\-]\s*\d+)*)\]")


def expand(tok: str) -> list[int]:
    out = []
    for part in tok.split(","):
        part = part.strip()
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
            out.extend(range(a, b + 1))
        else:
            out.append(int(part))
    return out


def collapse(nums: list[int]) -> str:
    """JMIR style: [1,2] with no space, ranges as [2-13]."""
    nums = sorted(set(nums))
    runs, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        runs.append((start, prev)); start = prev = n
    runs.append((start, prev))
    return "[" + ",".join(f"{a}-{b}" if b - a >= 2 else
                          ",".join(str(x) for x in range(a, b + 1))
                          for a, b in runs) + "]"


def main() -> int:
    md = MD.read_text()
    body_start = md.index("## Abstract")
    body_end = md.index("## Data and code availability")
    body = md[body_start:body_end]

    seen, appearance = set(), []
    for m in CITE.finditer(body):
        for n in expand(m.group(1)):
            if n not in seen:
                seen.add(n); appearance.append(n)

    uncited = sorted(set(range(1, len(R.ORDER) + 1)) - seen)
    if uncited:
        # An entry no longer cited is dropped rather than left as an orphan.
        print("dropping uncited references: "
              + ", ".join(f"[{n}] {R.ORDER[n - 1]}" for n in uncited))
    if appearance == sorted(appearance) and not uncited:
        print("already in order of first appearance; nothing to do")
        return 0

    old_to_new = {old: i + 1 for i, old in enumerate(appearance)}
    new_order = [R.ORDER[old - 1] for old in appearance]

    rewritten = CITE.sub(
        lambda m: collapse([old_to_new[n] for n in expand(m.group(1))]), body)
    MD.write_text(md[:body_start] + rewritten + md[body_end:])

    src = (ROOT / "manuscript/references.py").read_text()
    block = "ORDER = [\n" + "".join(
        f'    "{k}",\n' for k in new_order) + "]\n"
    src = re.sub(r"ORDER = \[.*?\n\]\n", block, src, count=1, flags=re.S)
    (ROOT / "manuscript/references.py").write_text(src)
    dropped = [R.ORDER[n - 1] for n in uncited]
    if dropped:
        print("note: REFS entries for " + ", ".join(dropped)
              + " remain defined but unused, and are no longer numbered.")
    print(f"renumbered {len(appearance)} references into order of appearance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
