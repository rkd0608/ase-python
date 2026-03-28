"""Execute the upstream OpenAI Agents JS harness with stable repo-local paths."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / ".upstream" / "openai-agents-js"
HARNESS = ROOT / "validation" / "upstream" / "openai-agents-js" / "ase_agent.ts"


def main() -> int:
    """Run the checked-in harness against the fetched upstream workspace."""
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm is required to run the openai-agents-js upstream harness")
    if not UPSTREAM.exists():
        raise SystemExit(f"upstream workspace not found: {UPSTREAM}")
    env = os.environ.copy()
    env["NODE_PATH"] = str(UPSTREAM / "node_modules")
    command = [pnpm, "--dir", str(UPSTREAM), "exec", "tsx", str(HARNESS)]
    completed = subprocess.run(command, env=env, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
