"""Materialize missing ASE modules from Python 3.11 bytecode.

This is a recovery utility for incomplete workspaces where source files are
missing but matching `__pycache__` artifacts still exist. It writes a separate
overlay tree containing source-less `.pyc` modules so ASE can run in a clean
Python 3.11 environment while source restoration continues.
"""

from __future__ import annotations

import sys
from pathlib import Path

PYTHON_TAG = "cpython-311"
INIT_TEMPLATE = "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"


def main(argv: list[str]) -> int:
    """Create a recovery overlay containing source-less modules from bytecode."""
    if len(argv) != 2:
        print("usage: python scripts/materialize_recovery_pyc.py <overlay-dir>")
        return 1
    root = Path(__file__).resolve().parents[1]
    src_root = root / "src" / "ase"
    overlay_root = Path(argv[1]).resolve()
    written = materialize_overlay(src_root, overlay_root)
    print(f"materialized {written} modules into {overlay_root}")
    return 0


def materialize_overlay(src_root: Path, overlay_root: Path) -> int:
    """Copy missing modules from `__pycache__` into a separate import overlay."""
    count = 0
    for pyc_path in sorted(src_root.rglob(f"*.{PYTHON_TAG}.pyc")):
        if "__pycache__" not in pyc_path.parts:
            continue
        module_name = pyc_path.name.split(f".{PYTHON_TAG}.pyc")[0]
        rel_parent = pyc_path.parent.parent.relative_to(src_root)
        source_path = src_root / rel_parent / f"{module_name}.py"
        if source_path.exists():
            continue
        target_dir = overlay_root / "ase" / rel_parent
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{module_name}.pyc"
        target_path.write_bytes(pyc_path.read_bytes())
        _ensure_package_chain(overlay_root / "ase", rel_parent)
        count += 1
    return count


def _ensure_package_chain(base_package: Path, rel_parent: Path) -> None:
    """Ensure each overlay directory is importable as a Python package."""
    current = base_package
    current.mkdir(parents=True, exist_ok=True)
    _write_init(current / "__init__.py")
    for part in rel_parent.parts:
        current = current / part
        current.mkdir(parents=True, exist_ok=True)
        _write_init(current / "__init__.py")


def _write_init(path: Path) -> None:
    """Write a package initializer that lets overlay and source trees compose."""
    if path.exists():
        return
    path.write_text(INIT_TEMPLATE, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
