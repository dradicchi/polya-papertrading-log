#!/usr/bin/env python3
"""
audit_append_only.py — check whether a source-of-truth stream was only appended to.

For every commit that touched a file, git records how many lines it added and how
many it deleted. A purely append-only file has **zero deletions across its entire
history**: past events were never edited or removed, only new ones appended. Any
retroactive edit shows up as a deletion (and a matching re-addition) on the commit
that made it.

Deletions are not automatically fraud. The trio `partial_clean` / `partial_k2_2pct`
/ `partial_k2_5pct` was reset once to a synchronized clean start (session 90,
2026-06-09) — a disclosed operation (see `DISCLOSURES.md`). When this script finds
deletions, it lists the exact commits that made them so the auditor can cross-check
each against `DISCLOSURES.md`; the commit subjects are self-describing.

This reads only per-commit line counts (`--numstat`), a lighter alternative to a
full `git log -p` patch traversal. Runtime still scales with a stream's history —
the large `canonical` stream (~300k events over ~1000 commits) takes ~1–2 minutes.

Usage:
    python3 tools/audit_append_only.py instances/canonical/events.jsonl
    python3 tools/audit_append_only.py --all      # every instance + legacy root (slow)

Exit code: 0 if every audited file is purely append-only, 1 if any has deletions
(disclosed or not — the operator confirms disclosed resets against DISCLOSURES.md).
No external dependencies beyond the Python 3 standard library and `git`.
"""

import subprocess
import sys
import glob
import os


def audit(path):
    """Print the append-only verdict for one file; return True if 0 deletions."""
    result = subprocess.run(
        ['git', 'log', '--numstat', '--no-renames', '--format=%H|%ad|%s',
         '--date=short', '--', path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"{path}: ERROR — git log failed ({result.stderr.strip()})")
        return False

    commits = additions = deletions = 0
    current = None                 # last-seen 'hash|date|subject' header line
    deletion_commits = []          # headers of commits that deleted lines
    for line in result.stdout.splitlines():
        if '\t' not in line:
            if line.strip():
                current = line     # commit header (hash|date|subject)
            continue
        added, deleted, _ = line.split('\t')
        if added == '-' or deleted == '-':
            continue               # binary file (no line counts)
        added, deleted = int(added), int(deleted)
        additions += added
        deletions += deleted
        commits += 1
        if deleted > 0:
            deletion_commits.append((current, deleted))

    ok = deletions == 0
    verdict = 'APPEND-ONLY' if ok else 'DELETIONS PRESENT'
    print(
        f"{path}: {verdict} — {commits} commits touched file, "
        f"{additions} additions, {deletions} deletions"
    )
    if deletion_commits:
        print("    deletions occurred in these commit(s) — cross-check "
              "DISCLOSURES.md:")
        for header, n in deletion_commits:
            print(f"      -{n:<4} {header}")
    return ok


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 tools/audit_append_only.py <file> | --all")
        sys.exit(1)

    if args[0] == '--all':
        paths = sorted(glob.glob('instances/*/events.jsonl'))
        if os.path.exists('events.jsonl'):
            paths.append('events.jsonl')  # legacy root stream
        if not paths:
            print("No event streams found (run from the repository root).")
            sys.exit(1)
    else:
        paths = args

    all_ok = True
    for path in paths:
        all_ok = audit(path) and all_ok

    print()
    if all_ok:
        print("ALL APPEND-ONLY")
    else:
        print("DELETIONS PRESENT in one or more streams — confirm each listed "
              "commit against DISCLOSURES.md (e.g. the session-90 synchronized "
              "reset of the K2 trio).")
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
