#!/usr/bin/env python3
"""Resolve [[key;key]] citation placeholders into numbered JMIR citations.

Numbers are assigned by order of first appearance and ORDER is rewritten to
match, so the ordering requirement cannot be broken by editing the prose.
Also enforces the house limits: at most 3 references in one citation token and
at most 2 uses of any single reference across the manuscript.
"""
from __future__ import annotations
import collections, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "manuscript"))
import references as R

MD = ROOT / "manuscript/manuscript.md"
KEYCITE = re.compile(r"\[\[([a-z0-9_;]+)\]\]")
MAX_PER_TOKEN, MAX_USES = 3, 2


def collapse(nums):
    nums = sorted(set(nums))
    runs, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n; continue
        runs.append((start, prev)); start = prev = n
    runs.append((start, prev))
    return "[" + ",".join(f"{a}-{b}" if b - a >= 2 else
                          ",".join(str(x) for x in range(a, b + 1))
                          for a, b in runs) + "]"


def main() -> int:
    md = MD.read_text()
    b0, b1 = md.index("## Abstract"), md.index("## Data and code availability")
    body = md[b0:b1]
    toks = KEYCITE.findall(body)
    if not toks:
        print("no [[key]] placeholders found")
        return 0
    # A half-converted file would silently renumber only the placeholders and
    # drop every reference still written as a number, so refuse that state.
    stray = re.findall(r"(?<!\[)\[\d+(?:[,\-]\d+)*\](?!\])", body)
    if stray:
        print(f"REFUSING TO WRITE: {len(stray)} numeric citations remain "
              f"alongside placeholders (e.g. {stray[:4]}). Convert the whole "
              f"body to [[key]] form first.")
        return 1

    errs, uses, order = [], collections.Counter(), []
    for tok in toks:
        keys = tok.split(";")
        if len(keys) > MAX_PER_TOKEN:
            errs.append(f"{len(keys)} refs in one token: {tok}")
        for k in keys:
            if k not in R.REFS:
                errs.append(f"unknown key: {k}")
                continue
            uses[k] += 1
            if k not in order:
                order.append(k)
    for k, n in uses.items():
        if n > MAX_USES:
            errs.append(f"{k} cited {n} times (limit {MAX_USES})")
    if errs:
        print("REFUSING TO WRITE:")
        for e in errs:
            print("  -", e)
        return 1

    num = {k: i + 1 for i, k in enumerate(order)}
    resolved = KEYCITE.sub(
        lambda m: collapse([num[k] for k in m.group(1).split(";")]), body)
    MD.write_text(md[:b0] + resolved + md[b1:])

    src = (ROOT / "manuscript/references.py").read_text()
    block = "ORDER = [\n" + "".join(f'    "{k}",\n' for k in order) + "]\n"
    src = re.sub(r"ORDER = \[.*?\n\]\n", block, src, count=1, flags=re.S)
    (ROOT / "manuscript/references.py").write_text(src)
    print(f"resolved {len(toks)} tokens -> {len(order)} references, in appearance order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
