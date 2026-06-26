#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_PATH="${ROOT_DIR}/.omo/evidence/task-24-parallel-implementation.md"
DEFAULT_PYTHON="/home/noel/.local/bin/python"
PYTHON_BIN="${PYTHON:-${DEFAULT_PYTHON}}"
MODE="${1:-}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    printf 'warning: %s was not found; falling back to python\n' "${PYTHON_BIN}" >&2
    PYTHON_BIN="python"
  elif command -v python3 >/dev/null 2>&1; then
    printf 'warning: %s was not found; falling back to python3\n' "${PYTHON_BIN}" >&2
    PYTHON_BIN="python3"
  else
    printf 'error: python is required; set PYTHON or install a python shim\n' >&2
    exit 127
  fi
fi

if [[ -n "${MODE}" && "${MODE}" != "--smoke" ]]; then
  printf 'error: unsupported mode %s; use --smoke or no argument\n' "${MODE}" >&2
  exit 2
fi

mkdir -p "$(dirname -- "${EVIDENCE_PATH}")"
cat >"${EVIDENCE_PATH}" <<EOF
# T24 Unified QA Evidence

- Script: scripts/test.sh ${MODE}
- Project root: ${ROOT_DIR}
- Python: ${PYTHON_BIN}

EOF

log_section() {
  printf '\n## %s\n\n' "$1" >>"${EVIDENCE_PATH}"
  printf '%s\n' "$1"
}

run_capture() {
  local description="$1"
  shift
  local output_file
  output_file="$(mktemp)"

  log_section "${description}"
  printf 'Command: `%s`\n\n' "$*" >>"${EVIDENCE_PATH}"
  printf 'Running: %s\n' "$*"

  if "$@" >"${output_file}" 2>&1; then
    printf 'Result: pass\n\n' >>"${EVIDENCE_PATH}"
  else
    local status=$?
    printf 'Result: fail (%s)\n\n' "${status}" >>"${EVIDENCE_PATH}"
    printf '```text\n' >>"${EVIDENCE_PATH}"
    tail -n 120 "${output_file}" >>"${EVIDENCE_PATH}"
    printf '\n```\n' >>"${EVIDENCE_PATH}"
    tail -n 120 "${output_file}" >&2
    rm -f "${output_file}"
    return "${status}"
  fi

  printf '```text\n' >>"${EVIDENCE_PATH}"
  tail -n 80 "${output_file}" >>"${EVIDENCE_PATH}"
  printf '\n```\n' >>"${EVIDENCE_PATH}"
  tail -n 20 "${output_file}"
  rm -f "${output_file}"
}

run_optional_capture() {
  local description="$1"
  shift
  local output_file
  output_file="$(mktemp)"

  log_section "${description}"
  printf 'Command: `%s`\n\n' "$*" >>"${EVIDENCE_PATH}"
  printf 'Running optional: %s\n' "$*"

  if "$@" >"${output_file}" 2>&1; then
    printf 'Result: pass\n\n' >>"${EVIDENCE_PATH}"
  else
    local status=$?
    printf 'Result: optional warning (%s)\n\n' "${status}" >>"${EVIDENCE_PATH}"
    printf 'warning: optional command failed: %s\n' "$*" >&2
  fi

  printf '```text\n' >>"${EVIDENCE_PATH}"
  tail -n 80 "${output_file}" >>"${EVIDENCE_PATH}"
  printf '\n```\n' >>"${EVIDENCE_PATH}"
  tail -n 20 "${output_file}"
  rm -f "${output_file}"
}

warn_optional_capabilities() {
  log_section "Optional capability checks"

  if "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("sqlite_vec") else 1)
PY
  then
    printf -- '- sqlite-vec: available\n' | tee -a "${EVIDENCE_PATH}"
  else
    printf -- '- sqlite-vec: unavailable, vector smoke skipped\n' | tee -a "${EVIDENCE_PATH}"
  fi

  if command -v graphify >/dev/null 2>&1; then
    printf -- '- Graphify: available\n' | tee -a "${EVIDENCE_PATH}"
  else
    printf -- '- Graphify: unavailable, graph smoke skipped\n' | tee -a "${EVIDENCE_PATH}"
  fi
}

run_cli_smoke() {
  local temp_dir
  local sample_doc
  temp_dir="$(mktemp -d)"
  sample_doc="${ROOT_DIR}/samples/docs/dungeon_draft.md"

  log_section "Temporary project smoke directory"
  printf -- '- Created: %s\n' "${temp_dir}" | tee -a "${EVIDENCE_PATH}"

  run_capture "doc2dic root help" doc2dic --help
  run_capture "doc2dic init help" doc2dic init --help
  run_capture "doc2dic status help" doc2dic status --help
  run_capture "doc2dic check help" doc2dic check --help
  run_capture "doc2dic analyze help" doc2dic analyze --help
  run_capture "doc2dic review help" doc2dic review --help
  run_capture "doc2dic graph help" doc2dic graph --help

  run_capture "doc2dic init" bash -c 'cd "$1" && doc2dic init' bash "${temp_dir}"
  run_capture "doc2dic status" bash -c 'cd "$1" && doc2dic status' bash "${temp_dir}"
  run_capture "doc2dic check sample" env DOC2DIC_LLM_PROVIDER=mock DOC2DIC_EMBEDDING_PROVIDER=mock bash -c 'cd "$1" && doc2dic check "$2" --write-issues' bash "${temp_dir}" "${sample_doc}"
  run_capture "doc2dic analyze sample" env DOC2DIC_LLM_PROVIDER=mock DOC2DIC_EMBEDDING_PROVIDER=mock bash -c 'cd "$1" && doc2dic analyze "$2"' bash "${temp_dir}" "${sample_doc}"
  run_capture "doc2dic review list" bash -c 'cd "$1" && doc2dic review list' bash "${temp_dir}"
  run_capture "doc2dic graph current" bash -c 'cd "$1" && doc2dic graph current --json' bash "${temp_dir}"
  run_capture "doc2dic graph export graphify" bash -c 'cd "$1" && doc2dic graph export --format graphify' bash "${temp_dir}"

  rm -rf "${temp_dir}"
  printf -- '- Cleanup: temp directory removed\n' | tee -a "${EVIDENCE_PATH}"
}

run_python_quality_gates() {
  run_capture "ruff check" "${PYTHON_BIN}" -m ruff check .
  run_capture "basedpyright" "${PYTHON_BIN}" -m basedpyright
  run_capture "provider offline tests" "${PYTHON_BIN}" -m pytest tests/unit/services/test_llm_service.py tests/unit/services/test_embedding_service.py -q
  run_capture "API contract tests" "${PYTHON_BIN}" -m pytest tests/integration/server -q
  run_capture "graph snapshot and export tests" "${PYTHON_BIN}" -m pytest tests/snapshots/test_app_graph_snapshot.py tests/snapshots/test_graphify_projection_snapshot.py tests/integration/cli/test_graph_current.py tests/integration/cli/test_graph_export.py tests/unit/services/test_graph_projection_service.py tests/unit/services/test_graphify_adapter.py -q
  run_capture "Python pytest" "${PYTHON_BIN}" -m pytest -q
}

run_web_quality_gates() {
  if [[ ! -f "${ROOT_DIR}/web/package.json" ]]; then
    log_section "web quality gates"
    printf -- '- skipped: web/package.json is not present\n' | tee -a "${EVIDENCE_PATH}"
    return
  fi
  if ! command -v npm >/dev/null 2>&1; then
    log_section "web quality gates"
    printf -- '- skipped: npm runner not found\n' | tee -a "${EVIDENCE_PATH}"
    return
  fi

  run_capture "web typecheck" npm --prefix web run typecheck
  run_capture "web tests" npm --prefix web run test
  run_optional_capture "web lint optional" npm --prefix web run lint
}

write_summary() {
  log_section "Summary"
  printf -- '- Unified QA gate completed.\n' | tee -a "${EVIDENCE_PATH}"
  printf -- '- Evidence: %s\n' "${EVIDENCE_PATH}" | tee -a "${EVIDENCE_PATH}"
}

cd "${ROOT_DIR}"
run_capture "Editable dev install" "${PYTHON_BIN}" -m pip install -e ".[dev]"
warn_optional_capabilities
run_cli_smoke

if [[ "${MODE}" == "--smoke" ]]; then
  log_section "Smoke mode complete"
  printf -- '- Full ruff, basedpyright, pytest, and web suites were not requested in --smoke mode.\n' | tee -a "${EVIDENCE_PATH}"
  write_summary
  exit 0
fi

run_python_quality_gates
run_web_quality_gates
write_summary
