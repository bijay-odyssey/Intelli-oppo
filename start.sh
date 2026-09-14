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

usable() {
  "$@" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)' \
    >/dev/null 2>&1
}

find_python() {
  # `py -3.12` matters on Windows: the launcher routinely knows about an
  # interpreter that is not on PATH under any name, which is exactly the case
  # when `python` is an older system install.
  for candidate in \
    "py -3.12" "py -3.13" "py -3.11" \
    python3.12 python3.13 python3.11 python3 python
  do
    # Intentionally unquoted: candidates may be two words.
    # shellcheck disable=SC2086
    if usable $candidate; then
      echo "$candidate"
      return 0
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
  # Intentionally unquoted: a candidate may be two words, e.g. `py -3.12`.
  # shellcheck disable=SC2086
  $BASE_PY -m venv "$VENV"

  PY="$VENV/bin/python"
  [ -x "$VENV/Scripts/python.exe" ] && PY="$VENV/Scripts/python.exe"
  [ -x "$PY" ] || fail "virtual environment was created but has no interpreter at $PY"
fi

# ── dependencies ──────────────────────────────────────────────────────
# Probe a third-party dependency, not our own package: `import intelli_oppo`
# succeeds from the source tree even in an empty venv, because Python puts the
# working directory on sys.path. That false positive skipped installation
# entirely and surfaced later as ModuleNotFoundError at runtime.
if ! "$PY" -c 'import groq, rich, pydantic, dotenv' >/dev/null 2>&1; then
  say "installing dependencies (first run only)"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -e ".[dev]"
fi

MODE="${1:-run}"
shift || true

# ── key ───────────────────────────────────────────────────────────────
# Only the modes that actually talk to the API. The whole test suite is
# offline, and `check` exists precisely to diagnose a missing key, so
# demanding one from either would be backwards.
case "$MODE" in
  run|demo|ask)
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
    ;;
esac

# ── run ───────────────────────────────────────────────────────────────
case "$MODE" in
  run)   exec "$PY" -m intelli_oppo "$@" ;;
  demo)  exec "$PY" -m intelli_oppo --demo "$@" ;;
  check) exec "$PY" -m intelli_oppo --check "$@" ;;
  ask)   exec "$PY" -m intelli_oppo --ask "$@" ;;
  test)  exec "$PY" -m pytest -q "$@" ;;
  setup) say "ready — ./start.sh demo to see it work"; exit 0 ;;
  *)     fail "unknown mode '$MODE'. Use: run, demo, check, ask, test, setup" ;;
esac
