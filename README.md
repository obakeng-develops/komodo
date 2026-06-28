# Komodo

Komodo keeps your Docker containers running. It watches them. When one goes down it works out
why, restarts it within the limits you set, and shows you the whole thing as it happens — or it
stops and asks first. That part is your call.

You log in. Your teammates log in. Everyone sees the same fleet. Owners change things; operators
watch and act on incidents but can't touch the settings.

---

## How it works

```
   ┌── a host you monitor ────┐         ┌──────────────── Komodo server ─────────────────┐
   │  komodo-agent.py         │  beats  │  backend (FastAPI)                              │
   │  • reads `docker ps`     │ ──────► │  • opens incidents, runs the state machine      │
   │  • runs `docker restart` │ ◄────── │  • asks llm-service to diagnose                 │
   │    when told to          │ actions │  • streams the live state to the UI over SSE    │
   └──────────────────────────┘         │  frontend (SvelteKit) · postgres · executor    │
                                         └─────────────────────────────────────────────────┘
```

A container fails. The agent reports it. The backend opens an incident, pulls the logs, and sends
them to the LLM. The diagnosis appears in the UI. Then the agent restarts the container — or, if
you asked to approve first, Komodo waits for you. Once the container is healthy again, the
incident resolves.

The pieces:

- **Agent** — a small, dependency-free Python script on each host you monitor. It reports container
  status every few seconds and restarts a container only when the backend tells it to. Nothing else.
- **Backend** — the control plane. It runs the incident state machine, enforces your guardrails,
  handles auth, and streams live state to the browser.
- **llm-service** — an isolated service that makes the LLM call. Hand it an incident's logs and it
  returns a cause, a fix, and a confidence level.
- **executor** — runs a short list of Docker actions on the control-plane host, and only when it
  receives a short-lived signed token. The agent handles remote hosts; the executor is the
  local-host path.
- **frontend** — the dashboard: a live "Now" view, incident history, guardrails, and settings.
- **postgres** — where state lives.

Two roles. **Owners** run everything. **Operators** — your backup on-call — see the whole fleet and
can approve, take over, resolve, or hand back an incident, but they can't change settings, the LLM
key, hosts, services, guardrails, or the team.

---

## Stack

- Backend: FastAPI + SQLAlchemy (Postgres in production, SQLite for local work)
- Frontend: SvelteKit + Tailwind, built with adapter-node
- Realtime: Server-Sent Events
- Auth: a JWT in an HttpOnly cookie, passwords hashed with bcrypt
- Proxy: Caddy, one origin, automatic TLS

---

## Run it locally

This path uses SQLite and needs no Docker.

**Backend**
```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
AUTH_SECRET=dev-secret \
ENCRYPTION_KEY=dev-encryption-key \
DATABASE_URL="sqlite:///./oncall.db" \
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

**Frontend** (Vite proxies `/api` to the backend)
```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. The first screen asks you to create the owner account.

---

## Deploy with Docker Compose

This is the supported way to run Komodo in production. Caddy takes the only public port. It serves
the frontend and forwards `/api` to the backend, so everything sits on one origin — which is what
makes the session cookie and the live stream just work.

**1. Make the secrets**

```bash
./scripts/gen-secrets.sh    # writes secrets/executor.{key,pub}, prints the random secrets
cp .env.example .env        # paste the printed values in
```

`ENCRYPTION_KEY` and `INTERNAL_API_KEY` are shared. The backend and the llm-service must use the
same values, so set each one once in `.env`.

**2. Start it**

```bash
docker compose up -d --build
```

**3. Create the owner**

Open your `APP_ORIGIN`. Create the owner account on the first-run screen. After that, Komodo
closes the setup endpoint for good.

> Add the LLM API key (DeepSeek, say) in **Settings → LLM diagnosis** after you log in. It isn't an
> environment variable — Komodo stores it encrypted with `ENCRYPTION_KEY`.

### Example A — one box, plain HTTP

`.env`:
```dotenv
APP_ORIGIN=http://localhost       # the http:// scheme turns TLS off
COOKIE_SECURE=false
# SETUP_TOKEN left blank → open setup, which is fine on a box only you can reach
POSTGRES_PASSWORD=…               # from gen-secrets.sh
ENCRYPTION_KEY=…
INTERNAL_API_KEY=…
AUTH_SECRET=…
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-flash
```
```bash
docker compose up -d --build      # → http://localhost
```

### Example B — a public domain, HTTPS

Point an A record at the host, open ports 80 and 443, then:

`.env`:
```dotenv
APP_ORIGIN=komodo.example.com     # a bare host → Caddy gets a Let's Encrypt cert on its own
COOKIE_SECURE=true                # required over HTTPS
SETUP_TOKEN=…                     # so only you can claim the owner account
POSTGRES_PASSWORD=…
ENCRYPTION_KEY=…
INTERNAL_API_KEY=…
AUTH_SECRET=…
```
```bash
docker compose up -d --build      # → https://komodo.example.com
```
On the first visit, Komodo asks for the setup token before it lets you create the owner.

---

## Deploy with Kamal

Kamal expects one web image plus a few prebuilt accessories. Komodo is several services, so the
clean fit is to fold them: the **backend serves the built frontend** as Kamal's one web app,
`kamal-proxy` handles TLS, and Postgres, the llm-service, and the executor run as accessories.

> **You have to build that combined image first — this repo doesn't ship one.** The Compose path
> runs the frontend as its own service behind Caddy. For Kamal, build the frontend as static files
> and let the backend serve them:
>
> ```dockerfile
> # build the SPA (adapter-static, ssr=false, fallback index.html)
> FROM node:22-alpine AS web
> WORKDIR /web
> COPY frontend/ .
> RUN npm ci && npm run build          # → /web/build
>
> # the backend serves it: app.mount("/", StaticFiles(directory="static", html=True))
> FROM python:3.13-slim
> WORKDIR /app
> COPY backend/requirements.txt . && RUN pip install --no-cache-dir -r requirements.txt
> COPY backend/app ./app
> COPY --from=web /web/build ./static  # FastAPI serves the SPA and /api/v1 on one origin
> CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
> ```
> The one code change: mount `StaticFiles` with an SPA fallback next to the existing `/api/v1`
> routes. No Caddy, no path-splitting — one origin by design.

Kamal only builds the web image, so push the llm-service and executor images to GHCR yourself.

`config/deploy.yml` (a starting point):
```yaml
service: komodo
image: ghcr.io/<you>/komodo

servers:
  web:
    - your.server.ip

proxy:
  ssl: true
  host: komodo.example.com

registry:
  server: ghcr.io
  username: <you>
  password:
    - KAMAL_REGISTRY_PASSWORD

env:
  clear:
    LLM_SERVICE_URL: http://komodo-llm-service:8001
    DATABASE_URL: postgresql+psycopg://komodo:PASS@komodo-postgres:5432/komodo
    COOKIE_SECURE: "true"
  secret:
    - ENCRYPTION_KEY
    - INTERNAL_API_KEY
    - AUTH_SECRET
    - EXECUTOR_SIGNING_KEY
    - SETUP_TOKEN

accessories:
  postgres:
    image: postgres:16-alpine
    host: your.server.ip
    env:
      clear: { POSTGRES_USER: komodo, POSTGRES_DB: komodo }
      secret: [ POSTGRES_PASSWORD ]
    directories:
      - data:/var/lib/postgresql/data

  llm-service:
    image: ghcr.io/<you>/komodo-llm-service   # build and push this yourself
    host: your.server.ip
    env:
      secret: [ ENCRYPTION_KEY, INTERNAL_API_KEY ]

  executor:
    image: ghcr.io/<you>/komodo-executor       # build and push this yourself
    host: your.server.ip
    options:
      privileged: true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

`.kamal/secrets`:
```bash
KAMAL_REGISTRY_PASSWORD=$(gh auth token)
ENCRYPTION_KEY=...
INTERNAL_API_KEY=...
AUTH_SECRET=...
EXECUTOR_SIGNING_KEY="$(cat secrets/executor.key)"
SETUP_TOKEN=...
POSTGRES_PASSWORD=...
```

Then:
```bash
docker login ghcr.io
kamal setup     # the first time
kamal deploy    # after that
```

Give the backend and the llm-service the same `ENCRYPTION_KEY`, or the stored LLM key won't decrypt.

---

## Install the agent

Every server you want watched runs the agent. It needs Python 3 and access to the Docker socket.

1. In Komodo, open **Settings → Connected servers → Add server** (owners only) and name it.
2. Click **Install**, copy the command, and run it on that host:

```bash
curl -fsSL https://komodo.example.com/api/v1/agent/script \
  | python3 - --server https://komodo.example.com --token <agent-token>
```

The agent reports `docker ps` every few seconds and runs `docker restart` only when Komodo approves
it. To keep it running, wrap that command in a systemd unit.

---

## Sign off before you push

`scripts/signoff` runs the checks and, if they all pass, marks the commit as signed off on GitHub.
It refuses to run on a dirty repo.

```bash
./scripts/signoff
```

It compiles the Python, runs `svelte-check`, builds the frontend, and validates the Compose file.
Add tests to the script as the project grows. (Adapted from
[DHH's signoff](https://gist.github.com/dhh/c5051aae633ff91bc4ce30528e4f0b60).)

---

## Configuration

| Variable | Service | Required | Notes |
|---|---|---|---|
| `APP_ORIGIN` | caddy | yes | `http://localhost` for local, or your domain for TLS |
| `POSTGRES_PASSWORD` | postgres, backend | yes | database password |
| `ENCRYPTION_KEY` | backend, llm-service | yes | must match on both; encrypts the stored LLM key |
| `INTERNAL_API_KEY` | backend, llm-service | yes | must match on both; internal service auth |
| `AUTH_SECRET` | backend | yes | signs session cookies |
| `COOKIE_SECURE` | backend | no | `true` over HTTPS, otherwise `false` |
| `SETUP_TOKEN` | backend | no | guards the first-run setup; use it on a public URL |
| `OWNER_EMAIL`, `OWNER_PASSWORD` | backend | no | bootstrap the owner without the setup page |
| `LLM_PROVIDER`, `LLM_MODEL` | llm-service | no | default to `deepseek` / `deepseek-v4-pro` |
| executor keypair | backend, executor | yes | `./scripts/gen-secrets.sh` writes it; Compose mounts it |

You set the LLM API key in the UI, not the environment. Komodo keeps it encrypted.

---

## Security

- The executor runs privileged with the Docker socket mounted, so it can control any container on
  its host. It accepts only short-lived signed tokens for a fixed set of actions — restart, stop,
  fetch logs, list — but treat that host as sensitive all the same.
- Keep `secrets/`, `.env`, and the database files out of git. The `.gitignore` already does this.
- On a public deploy, set `COOKIE_SECURE=true` and a `SETUP_TOKEN`.

## Still to come

Compose health checks beyond Postgres, a secrets manager, executor fan-out across hosts, CI, and an
in-app way to change your password. The Kamal combined image is documented above but not built.
