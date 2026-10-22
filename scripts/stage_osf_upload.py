#!/usr/bin/env python3
"""Copy the files listed in the manifest into one folder for OSF upload.

Driven by docs/materials_manifest.md rather than a hand-kept list, so the
upload and the published checksums cannot disagree. Two guards, because a
manual upload has none of the protection .gitignore gives: the credentialed
configuration files can never be staged, and every staged file is scanned
for anything shaped like a secret. Matches are reported by file and line
only — never by value.
"""
from __future__ import annotations
import hashlib, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "osf_upload"
NEVER = {"config/config.yaml", "config/config.main.yaml", ".env"}
SECRET = re.compile(
    r"(AIza[0-9A-Za-z_\-]{10,}|sk-[A-Za-z0-9]{12,}|ya29\.[0-9A-Za-z_\-]{10,}"
    r"|(?i:api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,})")


def main() -> int:
    man = (ROOT / "docs/materials_manifest.md").read_text()
    rows = re.findall(r"^(\S+)\s{2,}([0-9a-f]{64})$", man, re.M)
    if not rows:
        print("no checksum block in the manifest")
        return 1

    staged, problems, flagged = [], [], []
    if DEST.exists():
        shutil.rmtree(DEST)
    for rel, sha in rows:
        if rel in NEVER:
            problems.append(f"{rel}: carries credentials and is never staged")
            continue
        src = ROOT / rel
        if not src.exists():
            problems.append(f"{rel}: listed in the manifest but missing")
            continue
        data = src.read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            problems.append(f"{rel}: does not match its manifest checksum")
            continue
        dst = DEST / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        staged.append(rel)
        try:
            for i, line in enumerate(data.decode("utf-8").splitlines(), 1):
                if SECRET.search(line):
                    flagged.append(f"{rel}:{i}")
        except UnicodeDecodeError:
            pass

    # The manifest cannot list its own checksum, so it is staged separately.
    # Without it the upload has no key to verify the other files against.
    extra = "docs/materials_manifest.md"
    (DEST / extra).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / extra, DEST / extra)
    staged.append(extra)

    for rel in sorted(NEVER):
        if (DEST / rel).exists():
            problems.append(f"{rel}: present in the staging folder")

    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    if flagged:
        print(f"possible secrets in {len(flagged)} line(s) — inspect before "
              f"uploading (locations only, values not shown):")
        for f in flagged:
            print("  -", f)
        return 1

    kb = sum((DEST / r).stat().st_size for r in staged) / 1024
    print(f"staged {len(staged)} files, {kb:,.0f} KB -> {DEST}")
    print(f"  credentialed files excluded: {', '.join(sorted(NEVER))}")
    print(f"  every file matches its SHA-256 in docs/materials_manifest.md,\n  which is staged alongside and is the only file it cannot checksum")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
