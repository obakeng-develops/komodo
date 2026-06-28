# Deploy with Docker Compose

This is the supported way to run Komodo on a server. Caddy takes the only public port. It serves
the frontend and forwards `/api` to the backend, so everything lives on one origin. That is what
makes the session cookie and the live stream work. See [Why one origin](../explanation/one-origin.md)
for the reasoning.

You need Docker and Docker Compose on the host.

## 1. Make the secrets

```bash
./scripts/gen-secrets.sh    # writes secrets/executor.{key,pub}, prints the random secrets
cp .env.example .env        # paste the printed values in
```

`ENCRYPTION_KEY` and `INTERNAL_API_KEY` are shared. The backend and the llm-service must use the
same values, so set each one once in `.env`. The full list of variables is in
[Configuration](../reference/configuration.md).

## 2. Start it

```bash
docker compose up -d --build
```

## 3. Create the owner

Open your `APP_ORIGIN`. Create the owner account on the first-run screen. Komodo then closes the
setup endpoint for good. Add your LLM key in **Settings**, not the environment; see
[Choose an LLM provider](choose-an-llm-provider.md).

## Example: one box, plain HTTP

`.env`:

```dotenv
APP_ORIGIN=http://localhost       # the http:// scheme turns TLS off
COOKIE_SECURE=false
# SETUP_TOKEN blank is fine on a box only you can reach
POSTGRES_PASSWORD=…               # from gen-secrets.sh
ENCRYPTION_KEY=…
INTERNAL_API_KEY=…
AUTH_SECRET=…
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-flash
```

```bash
docker compose up -d --build      # serves http://localhost
```

## Example: a public domain with HTTPS

Point an A record at the host and open ports 80 and 443. Then:

`.env`:

```dotenv
APP_ORIGIN=komodo.example.com     # a bare host, so Caddy gets a Let's Encrypt cert on its own
COOKIE_SECURE=true                # required over HTTPS
SETUP_TOKEN=…                     # so only you can claim the owner account
POSTGRES_PASSWORD=…
ENCRYPTION_KEY=…
INTERNAL_API_KEY=…
AUTH_SECRET=…
```

```bash
docker compose up -d --build      # serves https://komodo.example.com
```

On the first visit, Komodo asks for the setup token before it lets you create the owner.

## Next

- [Install the agent on a host](install-the-agent.md) so Komodo has something to watch.
- [Manage your team](manage-your-team.md) to add your backup on-call.
