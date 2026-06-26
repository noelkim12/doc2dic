#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    printf 'warning: python was not found; falling back to python3\n' >&2
    PYTHON_BIN="python3"
  else
    printf 'error: python is required; set PYTHON or install a python shim\n' >&2
    exit 127
  fi
fi

check_optional_capabilities() {
  if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("sqlite_vec") else 1)
PY
  then
    printf 'warning: optional sqlite-vec is unavailable; vector search smoke is skipped\n' >&2
  fi

  if ! command -v graphify >/dev/null 2>&1; then
    printf 'warning: optional Graphify binary is unavailable; graph export smoke is skipped\n' >&2
  fi
}

cd "${ROOT_DIR}"
printf 'Installing doc2dic in editable dev mode with %s\n' "${PYTHON_BIN}"
"${PYTHON_BIN}" -m pip install -e ".[dev]"
check_optional_capabilities

if (($# > 0)); then
  exec doc2dic "$@"
fi

printf 'Running CLI help smoke\n'
doc2dic --help
doc2dic init --help
doc2dic status --help
