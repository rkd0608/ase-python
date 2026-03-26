#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
WHEEL_PATH=""
WORK_DIR=""

cleanup() {
  if [[ -n "${WORK_DIR}" && -d "${WORK_DIR}" ]]; then
    rm -rf "${WORK_DIR}"
  fi
}
trap cleanup EXIT

if ! ls "$DIST_DIR"/*.whl >/dev/null 2>&1; then
  echo "No wheel found in $DIST_DIR. Build one first (for example: python -m build)." >&2
  exit 1
fi

WHEEL_PATH="$(ls -1t "$DIST_DIR"/*.whl | head -n1)"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ase-prerelease-check.XXXXXX")"

python3 -m venv "$WORK_DIR/.venv"
# shellcheck disable=SC1091
source "$WORK_DIR/.venv/bin/activate"

python -m pip install --upgrade pip
python -m pip install "$WHEEL_PATH"

ase --help >/dev/null

cd "$WORK_DIR"
ase init test-scenario

if [[ ! -f "$WORK_DIR/test-scenario.yaml" ]]; then
  echo "Expected scenario file $WORK_DIR/test-scenario.yaml to be created." >&2
  exit 1
fi

cd "$ROOT_DIR"
set +e
ase test examples/customer-support/scenarios/refund-happy-path.yaml
ASE_TEST_EXIT_CODE=$?
set -e

if [[ $ASE_TEST_EXIT_CODE -ne 0 ]]; then
  echo "ase test failed with exit code $ASE_TEST_EXIT_CODE" >&2
  exit $ASE_TEST_EXIT_CODE
fi

echo "Prerelease check passed using wheel: $WHEEL_PATH"
