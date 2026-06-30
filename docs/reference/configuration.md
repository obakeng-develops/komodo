# Configuration

Every environment variable Mino reads, where it applies, and whether you must set it.

| Variable | Service | Required | Notes |
|---|---|---|---|
| `APP_ORIGIN` | caddy | yes | `http://localhost` for local, or your domain for TLS |
| `POSTGRES_PASSWORD` | postgres, backend | yes | database password |
| `ENCRYPTION_KEY` | backend, llm-service | yes | must match on both; encrypts the stored LLM key |
| `INTERNAL_API_KEY` | backend, llm-service | yes | must match on both; authenticates backend to llm-service |
| `AUTH_SECRET` | backend | yes | signs session cookies |
| `COOKIE_SECURE` | backend | no | `true` over HTTPS, otherwise `false` |
| `SETUP_TOKEN` | backend | no | guards the first-run setup; set it on a public URL |
| `OWNER_EMAIL`, `OWNER_PASSWORD` | backend | no | bootstrap the owner without the setup page |
| `LLM_PROVIDER`, `LLM_MODEL` | llm-service | no | fleet default; `deepseek` / `deepseek-v4-pro`. `LLM_PROVIDER` may be `deepseek` or `openrouter` |
| `DATABASE_URL` | backend | no | defaults to the in-compose Postgres; SQLite for local work |
| `EXECUTOR_SIGNING_KEY` / `EXECUTOR_SIGNING_KEY_FILE` | backend | yes | RSA private key that signs executor actions |
| `PUBLIC_KEY` / `PUBLIC_KEY_FILE` | executor | yes | the matching RSA public key |

Generate the random secrets and the executor keypair with `./scripts/gen-secrets.sh`.

## The LLM key is not here

You set the LLM API key in the UI, under **Settings**. Mino stores it in the database, encrypted
with `ENCRYPTION_KEY`. It is deliberately not an environment variable.

## Shared values

`ENCRYPTION_KEY` and `INTERNAL_API_KEY` must be identical for the backend and the llm-service. In
Docker Compose, one `.env` value feeds both. With Kamal, set the same secret on the web service and
the llm-service accessory.

## Agent flags

The host agent takes command-line flags, not environment variables. See
[Install the agent](../how-to/install-the-agent.md#agent-flags).
