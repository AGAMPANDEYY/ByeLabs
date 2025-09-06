#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting HiLabs Roster Processing System..."

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
print_status(){ echo -e "${BLUE}[INFO]${NC} $1"; }
print_success(){ echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning(){ echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error(){ echo -e "${RED}[ERROR]${NC} $1"; }

# -----------------------------
# Detect docker / docker compose
# -----------------------------
DOCKER_CMD="docker"
if ! command -v docker >/dev/null 2>&1; then
  # Try common Windows path (Git Bash/MSYS)
  if [ -x "/c/Program Files/Docker/Docker/resources/bin/docker.exe" ]; then
    DOCKER_CMD="/c/Program Files/Docker/Docker/resources/bin/docker.exe"
  elif [ -x "C:/Program Files/Docker/Docker/resources/bin/docker.exe" ]; then
    DOCKER_CMD="C:/Program Files/Docker/Docker/resources/bin/docker.exe"
  else
    print_error "Docker not found on PATH. Install Docker Desktop and re-open your terminal."
    exit 1
  fi
fi

if ! "$DOCKER_CMD" info >/dev/null 2>&1; then
  print_error "Docker is not running. Start Docker Desktop and try again."
  exit 1
fi

if ! "$DOCKER_CMD" compose version >/dev/null 2>&1; then
  print_error "Docker Compose v2 plugin not available. Update Docker Desktop."
  exit 1
fi

# -----------------------------
# Env + directories
# -----------------------------
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    print_status "Creating .env from .env.example ..."
    cp .env.example .env
  else
    print_error ".env.example not found."
    exit 1
  fi
else
  print_status ".env already exists"
fi

# shellcheck disable=SC1091
set +u
source .env || true
set -u

print_status "Ensuring directories exist ..."
mkdir -p api vlm samples logs
: > api/.keep; : > vlm/.keep; : > samples/.keep

# -----------------------------
# Modes: infra-only vs all
# -----------------------------
MODE="${1:-all}"   # usage: ./run.sh [infra|all]
if [ "$MODE" = "infra" ]; then
  print_status "Starting INFRA services only (db, mq, minio, mailpit) ..."
  "$DOCKER_CMD" compose up -d db mq minio mailpit
else
  print_status "Pulling base images (ignore failures if first run) ..."
  "$DOCKER_CMD" compose pull --ignore-pull-failures || true
  print_status "Building and starting ALL services ..."
  # If you add healthchecks in compose, you can switch to: up --build -d --wait
  "$DOCKER_CMD" compose up --build -d
fi

# -----------------------------
# Health checks (infra first)
# -----------------------------
if ! command -v curl >/dev/null 2>&1; then
  print_warning "curl not found; skipping HTTP health checks."
else
  check_service() {
    local name="$1" url="$2" max_attempts="${3:-30}" sleep_sec="${4:-2}"
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
      if curl -fsS "$url" >/dev/null 2>&1; then
        print_success "$name is ready"
        return 0
      fi
      printf "."
      sleep "$sleep_sec"
      attempt=$((attempt+1))
    done
    echo ""
    print_warning "$name did not respond after $((max_attempts*sleep_sec))s"
    return 1
  }

  print_status "Checking INFRA endpoints ..."
  check_service "RabbitMQ Management" "http://localhost:15672" || true
  check_service "Mailpit UI"          "http://localhost:8025"  || true
  check_service "MinIO Console"       "http://localhost:9001"  || true

  # Optional checks (only if API/VLM containers exist)
  if [ "$MODE" = "all" ]; then
    print_status "Checking APP endpoints (may be unavailable in Phase 0) ..."
    check_service "API Docs"           "http://localhost:8000/docs"  || true
    check_service "VLM Health"         "http://localhost:8080/health"|| true
  fi
fi

# -----------------------------
# Summary
# -----------------------------
MINIO_USER="${S3_ACCESS_KEY:-minioadmin}"
MINIO_PASS="${S3_SECRET_KEY:-minioadmin}"

echo ""
print_success "🎉 HiLabs Roster System is up (${MODE^^} mode)"
echo ""
echo "📋 Service URLs:"
echo "  • RabbitMQ Management:  http://localhost:15672 (guest/guest)"
echo "  • Mailpit (Email Test): http://localhost:8025"
echo "  • MinIO Console:        http://localhost:9001 (${MINIO_USER}/${MINIO_PASS})"
if [ "$MODE" = "all" ]; then
  echo "  • API Documentation:    http://localhost:8000/docs"
  echo "  • Review UI:            http://localhost:8000/ui/jobs"
  echo "  • Metrics:              http://localhost:8000/metrics"
  echo "  • VLM Health:           http://localhost:8080/health"
fi
echo ""
echo "🔧 Common Commands:"
echo "  • View logs:            $DOCKER_CMD compose logs -f"
echo "  • Stop:                 $DOCKER_CMD compose down"
echo "  • Restart:              $DOCKER_CMD compose restart"
echo "  • Status:               $DOCKER_CMD compose ps"
echo "  • Infra only:           ./run.sh infra"
if [ "$MODE" = "all" ]; then
  echo "  • Process sample:       curl -F \"eml=@./samples/Sample-1.eml\" http://localhost:8000/ingest"
fi
echo ""
"$DOCKER_CMD" compose ps
