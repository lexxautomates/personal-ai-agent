#!/usr/bin/env bash
# deploy.sh - Jarvis personal agent OS deployment. IDEMPOTENT: safe to re-run.
#
# Run ON THE VPS as root from a clone of the repo:
#   git clone https://github.com/lexxautomates/personal-ai-agent /root/personal-ai-agent
#   cd /root/personal-ai-agent && bash deploy/deploy.sh
#
# What it does:
#   1. Creates /opt/jarvis/{app,venv,data,livekit,caddy}
#   2. rsyncs agent/ and web/ into /opt/jarvis/app (fresh code each run)
#   3. Creates/updates the venv and pip-installs agent/requirements.txt
#   4. Generates LiveKit keys + config on first run (never overwritten)
#   5. Creates /opt/jarvis/.env (600) on first run; fills in missing keys on re-runs
#   6. Installs + enables + restarts the jarvis-web / jarvis-agent systemd units
#   7. Brings up the LiveKit docker compose stack
#   8. Installs the Caddy snippet (you add the `import` line once, manually)
#   9. Prints ufw commands (NOT applied - the deployer runs them) and a verification checklist
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$REPO_ROOT/deploy"
APP_DIR=/opt/jarvis/app
VENV_DIR=/opt/jarvis/venv
DATA_DIR=/opt/jarvis/data
LK_DIR=/opt/jarvis/livekit
CADDY_SNIPPET_DIR=/opt/jarvis/caddy
ENV_FILE=/opt/jarvis/.env
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.livekit.yml"

log()  { echo "[jarvis-deploy] $*"; }
warn() { echo "[jarvis-deploy] WARNING: $*" >&2; }

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "run as root" >&2; exit 1
fi
command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync not found - apt install rsync" >&2; exit 1; }
command -v openssl >/dev/null || { echo "openssl not found" >&2; exit 1; }

# --- 1. directories ---------------------------------------------------------
log "creating directories"
mkdir -p "$APP_DIR" "$VENV_DIR" "$DATA_DIR" "$LK_DIR" "$CADDY_SNIPPET_DIR"
chmod 700 "$LK_DIR"
touch "$ENV_FILE" 2>/dev/null || true
chmod 600 "$ENV_FILE"

# --- 2. ship code -----------------------------------------------------------
log "syncing agent/ and web/ -> $APP_DIR"
rsync -a --delete --exclude '.git' --exclude '.env' --exclude '__pycache__' \
  "$REPO_ROOT/agent/" "$APP_DIR/agent/"
rsync -a --delete --exclude '.git' --exclude '.env' --exclude '__pycache__' \
  "$REPO_ROOT/web/" "$APP_DIR/web/"

# --- 3. venv + deps ----------------------------------------------------------
if [ ! -x "$VENV_DIR/bin/python" ]; then
  log "creating venv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi
log "installing python deps"
"$VENV_DIR/bin/pip" install -q --upgrade pip
if [ -f "$APP_DIR/agent/requirements.txt" ]; then
  "$VENV_DIR/bin/pip" install -q -r "$APP_DIR/agent/requirements.txt"
else
  warn "agent/requirements.txt not found - installing flask + livekit-agents as a placeholder."
  warn "The agent rewrite should add agent/requirements.txt; re-run deploy.sh after."
  "$VENV_DIR/bin/pip" install -q flask "livekit-agents"
fi

# --- 4. livekit keys + config (first run only, never overwritten) ------------
if [ ! -f "$LK_DIR/keys.yaml" ]; then
  log "generating LiveKit API keys"
  bash "$DEPLOY_DIR/generate-keys.sh" "$LK_DIR/keys.yaml" >/dev/null
else
  log "keys.yaml exists - keeping existing keys"
fi
chmod 600 "$LK_DIR/keys.yaml"
if [ ! -f "$LK_DIR/livekit.yaml" ]; then
  log "installing livekit.yaml from example"
  cp "$DEPLOY_DIR/livekit.yaml.example" "$LK_DIR/livekit.yaml"
else
  log "livekit.yaml exists - not overwriting (diff against livekit.yaml.example manually)"
fi
chmod 600 "$LK_DIR/livekit.yaml"

# --- 5. /opt/jarvis/.env -----------------------------------------------------
# set_env_var KEY VALUE : replace-or-append (used for fresh generation)
set_env_var() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" "$ENV_FILE"
}
# ensure_env_var KEY VALUE : append only if KEY absent (safe on re-runs)
ensure_env_var() {
  local key="$1" value="$2"
  grep -qE "^${key}=" "$ENV_FILE" || printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
}

LK_KEY="$(awk -F': *' '!/^#/ && NF==2 {print $1; exit}' "$LK_DIR/keys.yaml")"
LK_SECRET="$(awk -F': *' '!/^#/ && NF==2 {print $2; exit}' "$LK_DIR/keys.yaml")"
if [ -z "$LK_KEY" ] || [ -z "$LK_SECRET" ]; then
  echo "could not parse $LK_DIR/keys.yaml" >&2; exit 1
fi

if [ ! -s "$ENV_FILE" ]; then
  log "creating $ENV_FILE from .env.example with generated secrets"
  cp "$REPO_ROOT/.env.example" "$ENV_FILE"
  set_env_var JARVIS_WEBHOOK_SECRET "$(openssl rand -hex 32)"
  set_env_var LIVEKIT_API_KEY "$LK_KEY"
  set_env_var LIVEKIT_API_SECRET "$LK_SECRET"
else
  log "$ENV_FILE exists - filling missing keys only"
  ensure_env_var JARVIS_WEBHOOK_SECRET "$(openssl rand -hex 32)"
  ensure_env_var LIVEKIT_API_KEY "$LK_KEY"
  ensure_env_var LIVEKIT_API_SECRET "$LK_SECRET"
  ensure_env_var OLLAMA_URL "http://localhost:11434"
  ensure_env_var LIVEKIT_URL "ws://localhost:7880"
  ensure_env_var FLASK_PORT "5000"
  ensure_env_var JARVIS_DATA_DIR "/opt/jarvis/data"
  ensure_env_var JARVIS_DB "/opt/jarvis/data/jarvis.db"
fi
chmod 600 "$ENV_FILE"

# --- 6. systemd units ---------------------------------------------------------
log "installing systemd units"
cp "$DEPLOY_DIR/jarvis-web.service" "$DEPLOY_DIR/jarvis-agent.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable -q jarvis-web.service jarvis-agent.service
log "restarting jarvis-web and jarvis-agent"
systemctl restart jarvis-web.service jarvis-agent.service

# --- 7. livekit ---------------------------------------------------------------
log "bringing up LiveKit (docker compose)"
docker compose -f "$COMPOSE_FILE" up -d --quiet-pull 2>/dev/null || \
  docker compose -f "$COMPOSE_FILE" up -d

# --- 8. caddy snippet ----------------------------------------------------------
log "installing Caddy snippet to $CADDY_SNIPPET_DIR/caddy-snippets.conf"
cp "$DEPLOY_DIR/caddy-snippets.conf" "$CADDY_SNIPPET_DIR/caddy-snippets.conf"
chmod 644 "$CADDY_SNIPPET_DIR/caddy-snippets.conf"
CADDYFILE=""
for cand in /etc/caddy/Caddyfile /opt/caddy/Caddyfile; do
  [ -f "$cand" ] && CADDYFILE="$cand" && break
done
if [ -n "$CADDYFILE" ] && grep -q "caddy-snippets.conf" "$CADDYFILE"; then
  log "snippet is imported in $CADDYFILE - reloading caddy"
  if systemctl is-active -q caddy 2>/dev/null; then
    systemctl reload caddy
  elif docker ps --format '{{.Names}}' 2>/dev/null | grep -qi caddy; then
    CADDY_CTN="$(docker ps --format '{{.Names}}' | grep -i caddy | head -1)"
    docker exec "$CADDY_CTN" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile || \
      warn "caddy reload inside $CADDY_CTN failed - reload it manually"
  else
    warn "could not find a running caddy to reload - reload it manually"
  fi
else
  warn "MANUAL STEP: add this line to your Caddyfile (global scope), then reload caddy:"
  warn "    import $CADDY_SNIPPET_DIR/caddy-snippets.conf"
  [ -n "$CADDYFILE" ] && warn "Caddyfile found at: $CADDYFILE"
fi

# --- 9. ufw (documented, NOT applied) ------------------------------------------
cat <<'EOF'

============================================================
UFW - run these yourself (deploy.sh never touches the firewall):
  ufw allow 7881/tcp comment 'jarvis livekit rtc-tcp'
  ufw allow 7882/udp comment 'jarvis livekit rtc-udp'
  ufw allow 3478/udp comment 'jarvis livekit turn'   # optional, only if TURN is used
Port 7880 stays localhost-only (Caddy proxies it); 5000 stays localhost-only.
============================================================
EOF

# --- 10. verification checklist -----------------------------------------------
cat <<'EOF'

VERIFICATION CHECKLIST
  [ ] Flask health (local):      curl -s http://localhost:5000/health
  [ ] Flask health (public):     curl -s https://jarvis.86-48-18-41.sslip.io/health
  [ ] systemd:                   systemctl status jarvis-web jarvis-agent --no-pager
  [ ] web logs:                  journalctl -u jarvis-web -n 30 --no-pager
  [ ] agent logs:                journalctl -u jarvis-agent -n 50 --no-pager
  [ ] livekit container:         docker ps --filter name=jarvis-livekit
  [ ] livekit logs:              docker logs jarvis-livekit --tail 30
  [ ] livekit listening:         curl -s -o /dev/null -w '%{http_code}\n' http://localhost:7880/   # expect 404 = up
  [ ] token test:                see DEPLOY.md "Token generation test"
  [ ] agent dispatch:            create/join the agent room, watch `journalctl -u jarvis-agent -f`
                                 for the session starting
  [ ] ufw:                       ufw status | grep -E '7881|7882'

Full runbook: deploy/DEPLOY.md
EOF
log "done."
