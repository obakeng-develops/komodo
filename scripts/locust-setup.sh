#!/usr/bin/env bash
# Prepare a LOCAL Komodo for a Locust run: create the owner (or log in) and a
# host, then print the env to paste before running locust. Assumes a local
# instance is already up (docker compose up) with an open first-run setup.
set -euo pipefail
HOST=${KOMODO_HOST:-http://localhost}
EMAIL=${KOMODO_EMAIL:-owner@example.com}
PASSWORD=${KOMODO_PASSWORD:-locustpw123}

jar=$(mktemp)
# Claim the owner on a fresh instance; fall back to login if it already exists.
curl -fsS -c "$jar" -X POST "$HOST/api/v1/auth/setup" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"name\":\"Load Owner\",\"password\":\"$PASSWORD\"}" >/dev/null 2>&1 \
  || curl -fsS -c "$jar" -X POST "$HOST/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null

token=$(curl -fsS -b "$jar" -X POST "$HOST/api/v1/hosts" -H 'Content-Type: application/json' \
  -d '{"name":"loadtest"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

cat <<EOF
export KOMODO_HOST=$HOST
export KOMODO_EMAIL=$EMAIL
export KOMODO_PASSWORD=$PASSWORD
export KOMODO_AGENT_TOKEN=$token
EOF
