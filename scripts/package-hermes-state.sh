#!/bin/bash
# Package Hermes state for shipping to the hermes-state repo.
# Keeps the agent repo clean and lets the iMac pull state without the source.

set -euo pipefail

STATE_ROOT="${HERMES_STATE_ROOT:-/c/Users/alexa/.hermes_state}"
OUTDIR="${OUTDIR:-.}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

PACKAGE="$(cd "$OUTDIR" && pwd)/hermes-state-${TIMESTAMP}.tgz"

echo "Packaging Hermes state from: $STATE_ROOT"
echo "Writing package to: $PACKAGE"

tar \
  --exclude='*.db-wal' \
  --exclude='*.db-shm' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite-wal' \
  --exclude='*.sqlite-shm' \
  -czf "$PACKAGE" \
  -C "$(dirname "$STATE_ROOT")" \
  "$(basename "$STATE_ROOT")"

echo "Package created: $PACKAGE"
echo "Size: $(du -h "$PACKAGE" | cut -f1)"
