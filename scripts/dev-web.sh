#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${ROOT_DIR}/web"

if [[ ! -f "${WEB_DIR}/package.json" ]]; then
  printf 'warning: web/package.json is not present; local web dev server is not available yet\n' >&2
  exit 0
fi

cd "${WEB_DIR}"

if command -v bun >/dev/null 2>&1; then
  exec bun run dev
fi

if command -v npm >/dev/null 2>&1; then
  exec npm run dev
fi

printf 'error: no supported web package runner found; install bun or npm\n' >&2
exit 127
