#!/usr/bin/env bash
# Set up and run Intelli-Oppo.
#
# There is no server here. This is a CLI that calls a remote API; the script
# exists so a fresh clone is one command away from working rather than six.
#
#   ./start.sh              argue with it
#   ./start.sh demo         watch a scripted debate
#   ./start.sh check        verify setup and reach the API
#   ./start.sh test         run the offline test suite
#   ./start.sh ask "..."    one turn, then exit
#   ./start.sh setup        bootstrap only, run nothing

set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"
[ -x "$VENV/Scripts/python.exe" ] && PY="$VENV/Scripts/python.exe"   # Git Bash

say()  { printf '  %s\n' "$*"; }
fail() { printf '\n  error: %s\n\n' "$*" >&2; exit 1; }

find_python() {
  for candidate in python3.12 python3.13 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)' 2>/dev/null; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

# ── venv ──────────────────────────────────────────────────────────────
if [ ! -x "$PY" ]; then
  BASE_PY="$(find_python)" || fail "need Python 3.11 or newer on PATH (3.12 recommended).
  onnxruntime requires 3.11+, so older versions cannot work.
  https://www.python.org/downloads/"

  say "creating virtual environment with $BASE_PY"
  "$BASE_PY" -m venv "$VENV"
  PY="$VENV/bin/python"
  [ -x "$VENV/Scripts/python.exe" ] && PY="$VENV/Scripts/python.exe"
fi

# ── dependencies ──────────────────────────────────────────────────────
if ! "$PY" -c 'import intelli_oppo' >/dev/null 2>&1; then
  say "installing dependencies (first run only)"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -e ".[dev]"
fi

# ── key ───────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  printf '\n  created .env — add your Groq key, then run this again\n'
  printf '  free key: https://console.groq.com/keys\n\n'
  exit 1
fi

if ! grep -qE '^GROQ_TOKEN=.+' .env; then
  printf '\n  .env has no GROQ_TOKEN — add one, then run this again\n'
  printf '  free key: https://console.groq.com/keys\n\n'
  exit 1
fi

# ── run ───────────────────────────────────────────────────────────────
MODE="${1:-run}"
shift || true

case "$MODE" in
  run)   exec "$PY" -m intelli_oppo "$@" ;;
  demo)  exec "$PY" -m intelli_oppo --demo "$@" ;;
  check) exec "$PY" -m intelli_oppo --check "$@" ;;
  ask)   exec "$PY" -m intelli_oppo --ask "$@" ;;
  test)  exec "$PY" -m pytest -q "$@" ;;
  setup) say "ready — ./start.sh demo to see it work"; exit 0 ;;
  *)     fail "unknown mode '$MODE'. Use: run, demo, check, ask, test, setup" ;;
esac
