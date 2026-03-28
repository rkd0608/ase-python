"""Wrapper around the upstream LangGraph validation harness."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_PYTHON = ROOT / ".upstream" / "langgraph" / ".venv" / "bin" / "python"
HARNESS = ROOT / "validation" / "upstream" / "langgraph-python" / "ase_agent.py"


def main() -> int:
    """Reuse the upstream LangGraph harness as the public repo example."""
    completed = subprocess.run(
        [str(UPSTREAM_PYTHON), str(HARNESS), *sys.argv[1:]],
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
