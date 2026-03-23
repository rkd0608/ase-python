"""Generate a Markdown compatibility matrix from certification artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

from ase.conformance.matrix import build_rows, load_results, to_markdown


def main(argv: list[str]) -> int:
    """Generate a matrix from certification result JSON files."""
    if len(argv) < 3:
        print("usage: python scripts/generate_compatibility_matrix.py <out.md> <result-or-dir>...")
        return 1
    out_path = Path(argv[1])
    result_paths = [Path(item) for item in argv[2:]]
    rows = build_rows(load_results(result_paths))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_markdown(rows) + "\n", encoding="utf-8")
    print(f"wrote compatibility matrix to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
