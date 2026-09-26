#!/usr/bin/env bash
#
# Digital Brain — one-command local demo.
#
# Starts everything the demo needs, verifies it is actually healthy, runs the
# scenario, prints the URLs, and shuts down cleanly on Ctrl-C. No JDK is
# required: Fly is started when it can be, and honestly reported as skipped when
# it cannot.
#
#   ./scripts/demo.sh                     start, seed, and stay up
#   ./scripts/demo.sh --setup             create the Python venv first if missing
#   ./scripts/demo.sh --check             preflight only, start nothing
#   ./scripts/demo.sh --env path/to/.env point the Brain at its own .env
#   ./scripts/demo.sh --stop              stop anything this script left running
#
# --env names the *Brain's* credentials file. Product keeps reading the
# repository .env, because the two hold different settings: provider keys on one
# side, service token and owner id on the other. The file is never printed.
#
# No secret is ever printed. The service token is passed to services through the
# environment, never echoed.

set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/logs"
RUN_DIR="$REPO_ROOT/.demo"
BRAIN_PORT="${BRAIN_PORT:-8765}"
PRODUCT_PORT="${PRODUCT_PORT:-3000}"
FLY_PY_PORT="${FLY_PY_PORT:-8601}"
FLY_HTTP_PORT="${FLY_HTTP_PORT:-8080}"

# The demo gets its own Product database. Seeding a demo into the checkout's
# real database would mix synthetic people and memories into whatever the
# developer keeps there, and would make the counts differ on every run, which is
# exactly what a demo must not do. Set DEMO_DATABASE_URL to point elsewhere.
DEMO_DATABASE_URL="${DEMO_DATABASE_URL:-file:$RUN_DIR/product.db}"
export DATABASE_URL="$DEMO_DATABASE_URL"

SETUP=0
CHECK_ONLY=0
STOP_ONLY=0
ENV_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --setup) SETUP=1 ;;
    --check) CHECK_ONLY=1 ;;
    --stop) STOP_ONLY=1 ;;
    --env)
      [ $# -ge 2 ] || { echo "--env needs a path" >&2; exit 2; }
      ENV_FILE="$2"; shift ;;
    -h|--help) sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# Point the services at one .env. Useful when a checkout keeps its credentials
# in a worktree of its own; the file is never printed or copied.
if [ -n "$ENV_FILE" ]; then
  [ -f "$ENV_FILE" ] || { echo "no such env file: $ENV_FILE" >&2; exit 2; }
  ENV_FILE="$(cd "$(dirname "$ENV_FILE")" && pwd)/$(basename "$ENV_FILE")"
  export BRAIN_ENV_FILE="$ENV_FILE"
fi

mkdir -p "$LOG_DIR" "$RUN_DIR"

# --- output helpers ---------------------------------------------------------
if [ -t 1 ]; then
  B=$'\033[1m'; D=$'\033[2m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; C=$'\033[36m'; N=$'\033[0m'
else
  B=""; D=""; G=""; Y=""; R=""; C=""; N=""
fi
say()  { printf '%s\n' "$*"; }
head1() { printf '\n%s%s%s\n' "$B$C" "$*" "$N"; }
ok()   { printf '   %s✓%s %s\n' "$G" "$N" "$*"; }
warn() { printf '   %s!%s %s\n' "$Y" "$N" "$*"; }
bad()  { printf '   %s✗%s %s\n' "$R" "$N" "$*"; }
dim()  { printf '   %s%s%s\n' "$D" "$*" "$N"; }

# --- child process management ----------------------------------------------
# Only processes this script started are ever signalled, so a developer's own
# server on the same port is never killed by accident.
declare -a STARTED_PIDS=()

track() { STARTED_PIDS+=("$1"); }

stop_all() {
  local code=$?
  if [ "${#STARTED_PIDS[@]}" -gt 0 ]; then
    printf '\n%sStopping demo services%s\n' "$B" "$N"
    for pid in "${STARTED_PIDS[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        printf '   %s·%s pid %s\n' "$D" "$N" "$pid"
      fi
    done
    sleep 1
    for pid in "${STARTED_PIDS[@]}"; do
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    done
  fi
  rm -f "$RUN_DIR"/*.pid 2>/dev/null || true
  return $code
}

# --stop reaps the pids a previous run wrote down, so a demo that was started
# in one shell can be shut down from another. It runs before any preflight:
# asking for a stop must never fail because a port is busy or a tool is
# missing, which is exactly when a stop is most likely to be needed.
stop_recorded() {
  local found=0 pid
  shopt -s nullglob
  for pidfile in "$RUN_DIR"/*.pid; do
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    case "$pid" in ''|*[!0-9]*) continue ;; esac
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      found=1
      printf '   %s·%s stopped %s (%s)\n' "$D" "$N" "$pid" "$(basename "$pidfile" .pid)"
    fi
  done
  shopt -u nullglob
  if [ "$found" -eq 0 ]; then
    say "   no recorded demo processes were running"
  else
    sleep 1
    for pidfile in "$RUN_DIR"/*.pid; do
      pid="$(cat "$pidfile" 2>/dev/null || true)"
      case "$pid" in ''|*[!0-9]*) continue ;; esac
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    done
  fi
  rm -f "$RUN_DIR"/*.pid 2>/dev/null || true
}

if [ "$STOP_ONLY" -eq 1 ]; then
  head1 "Stopping demo services"
  stop_recorded
  exit 0
fi

trap 'stop_all' EXIT INT TERM


# --- preflight --------------------------------------------------------------
port_busy() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -q ":${port} " && return 0
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  fi
  return 1
}

find_python() {
  # An explicit override wins, then a local venv, then any usable interpreter.
  if [ -n "${BRAIN_PYTHON:-}" ] && "$BRAIN_PYTHON" -c "import pydantic" 2>/dev/null; then
    echo "$BRAIN_PYTHON"; return 0
  fi
  for candidate in "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/venv/bin/python"; do
    [ -x "$candidate" ] && "$candidate" -c "import pydantic" 2>/dev/null && { echo "$candidate"; return 0; }
  done
  for candidate in python3 python; do
    command -v "$candidate" >/dev/null 2>&1 \
      && "$candidate" -c "import pydantic" 2>/dev/null && { command -v "$candidate"; return 0; }
  done
  return 1
}

head1 "Preflight"

MISSING=0

command -v node >/dev/null 2>&1 && ok "node $(node --version)" || { bad "node is required"; MISSING=1; }
command -v npm  >/dev/null 2>&1 && ok "npm $(npm --version)"  || { bad "npm is required"; MISSING=1; }

PYTHON_BIN="$(find_python || true)"
if [ -n "$PYTHON_BIN" ]; then
  ok "python with pydantic ($PYTHON_BIN)"
else
  bad "no Python with pydantic found"
  if [ "$SETUP" -eq 1 ]; then
    say "   creating .venv ..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet pydantic websockets python-dotenv
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
    ok "created .venv"
  else
    dim "run ./scripts/demo.sh --setup, or: python3 -m venv .venv &&"
    dim "  .venv/bin/pip install pydantic websockets python-dotenv"
    MISSING=1
  fi
fi

if [ ! -d node_modules ]; then
  say "   installing node dependencies (npm ci) ..."
  npm ci --no-audit --no-fund >/dev/null
  ok "node_modules ready"
else
  ok "node_modules present"
fi

EFFECTIVE_ENV="${BRAIN_ENV_FILE:-$REPO_ROOT/.env}"
if [ -f "$EFFECTIVE_ENV" ]; then
  ok ".env present (never printed)"
  [ -n "${BRAIN_ENV_FILE:-}" ] && dim "using $EFFECTIVE_ENV"
else
  warn ".env not found — the Brain will run on its heuristic provider"
  dim "cp .env.example .env to enable Gemini and name the local owner"
fi

dim "Product database: $DEMO_DATABASE_URL"
dim "  (the checkout's own database is not touched; delete .demo/ to reset)"

for port in "$BRAIN_PORT" "$PRODUCT_PORT"; do
  if port_busy "$port"; then
    bad "port $port is already in use — stop that process first"
    MISSING=1
  else
    ok "port $port free"
  fi
done

# Fly: report honestly rather than pretending.
FLY_PY_OK=0
if [ -f connectome/connectome/server.py ]; then
  FLY_PY_OK=1
  ok "Fly connectome (Python) available"
else
  warn "Fly connectome not found — skipping"
fi
FLY_JAVA_OK=0
if command -v java >/dev/null 2>&1 && (command -v mvn >/dev/null 2>&1 || [ -x backend/mvnw ]) \
   && (command -v javac >/dev/null 2>&1 || [ -x backend/mvnw ]); then
  FLY_JAVA_OK=1
  ok "Fly backend (Java) toolchain available"
else
  warn "Fly backend needs a JDK + Maven — it will be skipped, not faked"
  dim "install a JDK and Maven, then re-run to include Fly in the demo"
fi

if [ "$MISSING" -ne 0 ]; then
  say ""
  bad "preflight failed — fix the items above, or re-run with --setup"
  exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  head1 "Preflight passed"
  say "   re-run without --check to start the demo"
  exit 0
fi

# --- start ------------------------------------------------------------------
head1 "Starting services"

start_bg() { # name, logfile, command...
  local name="$1" log="$2"; shift 2
  "$@" >>"$log" 2>&1 &
  local pid=$!
  track "$pid"
  echo "$pid" > "$RUN_DIR/$name.pid"
  printf '   %s·%s %-18s pid %s  %s(logs/%s)%s\n' "$D" "$N" "$name" "$pid" "$D" "$(basename "$log")" "$N"
}

wait_for() { # label, url, tries
  local label="$1" url="$2" tries="${3:-60}"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS -m 2 "$url" >/dev/null 2>&1; then ok "$label is healthy"; return 0; fi
    sleep 1
  done
  bad "$label did not become healthy in time"
  return 1
}

# BRAIN_ENV_FILE lets a checkout keep credentials in another worktree's .env
# without the runner having to read, copy or print it. Logging is switched on for
# the demo because a presenter needs to see which provider answered; the events
# carry counts and ids, never the message or the answer.
start_bg brain "$LOG_DIR/brain.log" \
  env BRAIN_LOG_ENABLED="${BRAIN_LOG_ENABLED:-1}" \
      BRAIN_LOG_FORMAT="${BRAIN_LOG_FORMAT:-text}" \
      ${BRAIN_ENV_FILE:+BRAIN_ENV_FILE="$BRAIN_ENV_FILE"} \
  "$PYTHON_BIN" -m core.transport.http --host 127.0.0.1 --port "$BRAIN_PORT" \
  --db "${BRAIN_DB:-$RUN_DIR/brain.sqlite3}"
wait_for "brain" "http://127.0.0.1:$BRAIN_PORT/health" 60

# Migrations run before Product starts, because Product answers its health
# endpoint from the database and would report a confusing failure on a fresh
# checkout. db:deploy uses the local prisma from node_modules; npx --yes
# would reach out to the network on a machine that has it installed already.
if npm run db:deploy >"$LOG_DIR/prisma.log" 2>&1; then
  ok "database migrations applied"
else
  warn "migrate deploy reported a problem (see logs/prisma.log)"
fi

start_bg product "$LOG_DIR/product.log" npm run dev -- --port "$PRODUCT_PORT"
wait_for "product" "http://127.0.0.1:$PRODUCT_PORT/api/health" 90

start_bg worker "$LOG_DIR/worker.log" npm run worker
if [ "$FLY_PY_OK" -eq 1 ]; then
  # The connectome package lives in connectome/, so it must run from there. It
  # binds loopback only and takes no --host flag.
  start_bg fly-connectome "$LOG_DIR/fly-connectome.log" \
    env -C connectome "$PYTHON_BIN" -m connectome.server \
      --port "$FLY_PY_PORT" --db "$RUN_DIR/fly.sqlite3"
  if wait_for "fly-connectome" "http://127.0.0.1:$FLY_PY_PORT/health" 20; then :; else
    warn "fly connectome did not start (see logs/fly-connectome.log)"
  fi
fi
if [ "$FLY_JAVA_OK" -eq 1 ]; then
  start_bg fly-backend "$LOG_DIR/fly-backend.log" \
    ./backend/mvnw -q -f backend/pom.xml spring-boot:run
  if wait_for "fly-backend" "http://127.0.0.1:$FLY_HTTP_PORT/api/v1/health" 120; then :; else
    warn "fly backend did not start (see logs/fly-backend.log)"
  fi
else
  dim "fly backend skipped: no JDK. The demo continues with Brain + Product."
fi

# --- scenario ---------------------------------------------------------------
head1 "Running the demo scenario"
SCENARIO_ENV=()
[ -n "${BRAIN_ENV_FILE:-}" ] && SCENARIO_ENV=(--env "$BRAIN_ENV_FILE")
if node scripts/demo-scenario.mjs --base "http://127.0.0.1:$PRODUCT_PORT" "${SCENARIO_ENV[@]}"; then
  ok "scenario completed"
else
  warn "the scenario reported a problem — see the output above"
fi

# --- hand over --------------------------------------------------------------
head1 "Demo is running"
say "   Product        http://127.0.0.1:$PRODUCT_PORT/dashboard"
say "   Brain health   http://127.0.0.1:$BRAIN_PORT/health"
if [ "$FLY_PY_OK" -eq 1 ]; then
  say "   Fly connectome http://127.0.0.1:$FLY_PY_PORT/health"
fi
say ""
say "   Memory         http://127.0.0.1:$PRODUCT_PORT/memory"
say "   People         http://127.0.0.1:$PRODUCT_PORT/people"
say "   Developer      http://127.0.0.1:$PRODUCT_PORT/developer"
say "   Timeline       http://127.0.0.1:$PRODUCT_PORT/timeline"
say ""
dim "   logs           logs/brain.log  logs/product.log  logs/worker.log"
dim "   re-run story   node scripts/demo-scenario.mjs"
say ""
say "   Press Ctrl-C to stop everything this script started."
say ""

# Stay up until interrupted.
wait
