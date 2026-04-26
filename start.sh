#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── Colors ────────────────────────────────────────────────────────────────────
RESET='\033[0m'
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'

log()  { echo -e "${BOLD}[start]${RESET} $*"; }
ok()   { echo -e "${GREEN}[start]${RESET} $*"; }
warn() { echo -e "${YELLOW}[start]${RESET} $*"; }
err()  { echo -e "${RED}[start]${RESET} $*"; }

# ── Cleanup on exit ───────────────────────────────────────────────────────────
PIDS=()
cleanup() {
  echo ""
  log "Shutting down…"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  ok "All services stopped."
}
trap cleanup INT TERM EXIT

# ── 1. PostgreSQL ─────────────────────────────────────────────────────────────
log "Checking PostgreSQL…"
if pg_isready -q 2>/dev/null; then
  ok "PostgreSQL already running"
else
  warn "Starting PostgreSQL…"
  sudo pg_ctlcluster 16 main start
  sleep 1
  pg_isready -q && ok "PostgreSQL started" || { err "PostgreSQL failed to start"; exit 1; }
fi

# ── 2. Backend ────────────────────────────────────────────────────────────────
log "Starting backend on http://localhost:8000"
(
  cd "$BACKEND"
  while IFS= read -r line; do
    echo -e "${BLUE}[backend]${RESET} $line"
  done < <(uvicorn main:app --reload --host 0.0.0.0 --port 8000 2>&1)
) &
PIDS+=($!)

# Wait for backend to be ready
for i in $(seq 1 20); do
  sleep 0.5
  curl -sf http://localhost:8000/health >/dev/null 2>&1 && ok "Backend ready" && break
  [ "$i" -eq 20 ] && warn "Backend taking longer than expected…"
done

# ── 3. Frontend ───────────────────────────────────────────────────────────────
log "Starting frontend on http://localhost:5173"
(
  cd "$FRONTEND"
  while IFS= read -r line; do
    echo -e "${CYAN}[frontend]${RESET} $line"
  done < <(npm run dev 2>&1)
) &
PIDS+=($!)

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  ${GREEN}${BOLD}Portfolio running locally${RESET}"
echo -e "  Frontend  →  ${CYAN}http://localhost:5173${RESET}"
echo -e "  Backend   →  ${BLUE}http://localhost:8000${RESET}"
echo -e "  Database  →  ${YELLOW}postgresql://localhost/portfolio${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop everything"
echo ""

# Keep running, tailing all output
wait
