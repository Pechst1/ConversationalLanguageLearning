#!/usr/bin/env bash
# Use the same tested image for the API and worker. Rollback by choosing the
# previous image; never downgrade or replace the learner database here.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${APP_IMAGE:-}"
if [[ ! "$IMAGE" =~ ^ghcr\.io/pechst1/conversational-language-learning:(sha-[a-f0-9]{40})$ && ! "$IMAGE" =~ ^ghcr\.io/pechst1/conversational-language-learning@sha256:[a-f0-9]{64}$ ]]; then
  echo "APP_IMAGE must be a tested full sha tag or sha256 digest." >&2
  exit 2
fi
export APP_IMAGE
exec docker compose --env-file "$REPO/.env.prod" -f "$REPO/docker/docker-compose.prod.yml" "$@"
