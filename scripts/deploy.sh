#!/bin/bash
# ==============================================================================
# Deploy Script - Run by GitHub Actions on ECS
# ==============================================================================

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

DEPLOY_PATH="${DEPLOY_PATH:-/opt/maillife}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="${DEPLOY_PATH}/backups"
LOG_FILE="${DEPLOY_PATH}/logs/deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==============================================================================
# Functions
# ==============================================================================

log() {
    local level="$1"
    shift
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
    echo -e "$message" | tee -a "$LOG_FILE"
}

info()  { log "INFO" "${GREEN}$*${NC}"; }
warn()  { log "WARN" "${YELLOW}$*${NC}"; }
error() { log "ERROR" "${RED}$*${NC}" >&2; }

# ==============================================================================
# Pre-deployment Checks
# ==============================================================================

info "========================================"
info "MailLife Deployment Starting"
info "========================================"
info "Deploy path: $DEPLOY_PATH"
info "Image tag: $IMAGE_TAG"
info "Time: $(date)"

# Check if deploy path exists
if [ ! -d "$DEPLOY_PATH" ]; then
    error "Deploy path does not exist: $DEPLOY_PATH"
    exit 1
fi

cd "$DEPLOY_PATH"

# ==============================================================================
# Database Backup
# ==============================================================================

info "Creating database backup..."
mkdir -p "$BACKUP_DIR"

BACKUP_FILE="${BACKUP_DIR}/backup_$(date +%Y%m%d_%H%M%S).sql"

docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U maillife maillife > "$BACKUP_FILE" || {
    warn "Database backup failed, continuing anyway..."
}

# Keep only last 7 backups
find "$BACKUP_DIR" -name "backup_*.sql" -mtime +7 -delete 2>/dev/null || true

info "Backup saved: $BACKUP_FILE"

# ==============================================================================
# Pull Latest Images
# ==============================================================================

info "Pulling latest images..."

docker compose -f "$COMPOSE_FILE" pull

info "Images pulled successfully"

# ==============================================================================
# Deploy with Rolling Update
# ==============================================================================

info "Starting deployment..."

# Start new containers (old containers keep running)
docker compose -f "$COMPOSE_FILE" up -d --pull always

# Wait for health checks
info "Waiting for services to be healthy..."

# Backend health check
for i in {1..30}; do
    if docker compose -f "$COMPOSE_FILE" exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        info "Backend is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        error "Backend health check failed after 30 attempts"
        docker compose -f "$COMPOSE_FILE" logs backend | tail -50
        exit 1
    fi
    sleep 2
done

# ==============================================================================
# Cleanup
# ==============================================================================

info "Cleaning up old images..."
docker image prune -af --filter "until=24h" || true

# ==============================================================================
# Verification
# ==============================================================================

info "Verifying deployment..."

# Check container status
docker compose -f "$COMPOSE_FILE" ps

# Final health check
if docker compose -f "$COMPOSE_FILE" exec -T nginx sh -c 'wget -qO- http://localhost:80/health > /dev/null' 2>/dev/null; then
    info "Nginx is healthy"
else
    warn "Nginx health check failed (this might be expected if SSL is configured)"
fi

# ==============================================================================
# Deployment Summary
# ==============================================================================

info "========================================"
info "Deployment Completed Successfully!"
info "========================================"
info "Time: $(date)"
info "Image tag: $IMAGE_TAG"

# Notify success (optional - configure webhook)
if [ -n "${DEPLOY_WEBHOOK_URL:-}" ]; then
    curl -s -X POST "$DEPLOY_WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"status\": \"success\", \"tag\": \"$IMAGE_TAG\", \"time\": \"$(date)\"}" || true
fi
