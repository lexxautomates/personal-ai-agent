#!/usr/bin/env bash
# generate-keys.sh - create a LiveKit API keys file.
#
# Usage:  generate-keys.sh [output-path]
#         FORCE=1 generate-keys.sh [output-path]   # overwrite an existing file
#
# Writes one random key pair as YAML (api_key: api_secret), chmod 600.
# deploy.sh calls this for /opt/jarvis/livekit/keys.yaml on first run.
# The file is a secret: never commit it, never print it into logs you keep.
set -euo pipefail

OUT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/keys.yaml}"

if [ -e "$OUT" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "exists: $OUT (set FORCE=1 to overwrite)" >&2
  exit 0
fi

API_KEY="$(openssl rand -hex 16)"
API_SECRET="$(openssl rand -hex 32)"

umask 077
cat > "$OUT" <<EOF
# LiveKit API keys - generated $(date -u +%FT%TZ). Keep this file secret (mode 600).
$API_KEY: $API_SECRET
EOF
chmod 600 "$OUT"

echo "wrote $OUT (mode 600)"
echo "--- copy these into /opt/jarvis/.env (deploy.sh does this automatically) ---"
echo "LIVEKIT_API_KEY=$API_KEY"
echo "LIVEKIT_API_SECRET=$API_SECRET"
