# Deploy with Kamal

Kamal expects one web image plus a few prebuilt accessories. Mino is several services, so the
clean fit is to fold them: the backend serves the built frontend as Kamal's one web app,
`kamal-proxy` handles TLS, and Postgres, the llm-service, and the executor run as accessories.

## Build the combined web image first

This repo does not ship one. The Compose path runs the frontend as its own service behind Caddy.
For Kamal, build the frontend as static files and let the backend serve them:

```dockerfile
# build the SPA (adapter-static, ssr=false, fallback index.html)
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/ .
RUN npm ci && npm run build          # produces /web/build

# the backend serves it: app.mount("/", StaticFiles(directory="static", html=True))
FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt . && RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /web/build ./static  # FastAPI serves the SPA and /api/v1 on one origin
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The one code change is to mount `StaticFiles` with an SPA fallback next to the existing `/api/v1`
routes. There is then no Caddy and no path splitting. One origin by design.

Kamal builds only the web image, so push the llm-service and executor images to GHCR yourself.

## config/deploy.yml

A starting point:

```yaml
service: mino
image: ghcr.io/<you>/mino

servers:
  web:
    - your.server.ip

proxy:
  ssl: true
  host: mino.example.com

registry:
  server: ghcr.io
  username: <you>
  password:
    - KAMAL_REGISTRY_PASSWORD

env:
  clear:
    LLM_SERVICE_URL: http://mino-llm-service:8001
    DATABASE_URL: postgresql+psycopg://mino:PASS@mino-postgres:5432/mino
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
      clear: { POSTGRES_USER: mino, POSTGRES_DB: mino }
      secret: [ POSTGRES_PASSWORD ]
    directories:
      - data:/var/lib/postgresql/data

  llm-service:
    image: ghcr.io/<you>/mino-llm-service   # build and push this yourself
    host: your.server.ip
    env:
      secret: [ ENCRYPTION_KEY, INTERNAL_API_KEY ]

  executor:
    image: ghcr.io/<you>/mino-executor       # build and push this yourself
    host: your.server.ip
    options:
      privileged: true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

## .kamal/secrets

```bash
KAMAL_REGISTRY_PASSWORD=$(gh auth token)
ENCRYPTION_KEY=...
INTERNAL_API_KEY=...
AUTH_SECRET=...
EXECUTOR_SIGNING_KEY="$(cat secrets/executor.key)"
SETUP_TOKEN=...
POSTGRES_PASSWORD=...
```

## Deploy

```bash
docker login ghcr.io
kamal setup     # the first time
kamal deploy    # after that
```

Give the backend and the llm-service the same `ENCRYPTION_KEY`, or the stored LLM key will not
decrypt.
