#!/usr/bin/env bash
# Generate Komodo's deploy secrets: the executor RSA keypair (written to
# ./secrets/) and the random shared secrets (printed for you to paste into .env).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p secrets

# RSA keypair for executor action signing: backend signs (private), executor verifies (public).
if [ -f secrets/executor.key ]; then
  echo "secrets/executor.key already exists — leaving it untouched."
else
  openssl genrsa -out secrets/executor.key 2048 2>/dev/null
  openssl rsa -in secrets/executor.key -pubout -out secrets/executor.pub 2>/dev/null
  chmod 600 secrets/executor.key
  echo "Wrote secrets/executor.key + secrets/executor.pub"
fi

echo
echo "Paste these into your .env (copied from .env.example):"
echo "----------------------------------------------------------------"
echo "ENCRYPTION_KEY=$(openssl rand -hex 32)"
echo "INTERNAL_API_KEY=$(openssl rand -hex 32)"
echo "AUTH_SECRET=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
echo "----------------------------------------------------------------"
echo "(ENCRYPTION_KEY and INTERNAL_API_KEY are shared — the same value is used"
echo " by both the backend and llm-service via docker-compose. Done.)"
