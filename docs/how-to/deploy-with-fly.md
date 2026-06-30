# Deploy with fly.io

This runs Mino as one fly.io app: the combined image, where the backend serves the SPA and the
API on a single origin. It pairs well with watching a fleet that lives elsewhere (a separate
server), since you keep Mino off that box.

You need `flyctl` logged in (`fly auth login`) and the root `Dockerfile` from the combined-image
change. The executor does not run on fly (a fly microVM has no host Docker socket); you watch a host
with the [agent](install-the-agent.md), which restarts containers itself.

## 1. Create the app and a database

```bash
fly apps create mino            # pick a free name if taken
fly postgres create --region jnb  # managed Postgres
fly postgres attach mino-db --app mino   # sets DATABASE_URL on the app
```

## 2. Set the secrets

Generate the random values with `./scripts/gen-secrets.sh` (you only need the three secrets here;
no executor keypair, since there is no executor on fly).

```bash
fly secrets set --app mino \
  AUTH_SECRET=...        \
  ENCRYPTION_KEY=...     \
  INTERNAL_API_KEY=...   \
  COOKIE_SECURE=true     \
  SETUP_TOKEN=...
```

Leave `LLM_SERVICE_URL` unset to start. Mino skips LLM diagnosis gracefully when it is missing;
monitoring and restarts still work. Add the llm-service later (below).

## 3. Deploy

```bash
fly deploy
```

## 4. Point your domain at it

```bash
fly certs create mino.example.com --app mino
```

Add the records fly prints (a CNAME, or A + AAAA) to your DNS. Once the certificate is issued, open
`https://mino.example.com`, complete the first-run owner setup (it asks for your `SETUP_TOKEN`),
and add your LLM key in **Settings**.

## 5. Watch a host

Follow [Install the agent](install-the-agent.md) on the server you want monitored, pointing
`--server` at your fly URL. Start in **ask-first** autonomy until you trust it.

## Adding the llm-service (optional)

Run the llm-service as a second, private fly app and point the web app at it.

```bash
cd llm-service
fly apps create mino-llm
fly ips allocate-v6 --private --app mino-llm   # private flycast address
fly secrets set --app mino-llm ENCRYPTION_KEY=<same> INTERNAL_API_KEY=<same>
fly deploy
```

Then point the web app at it over flycast:

```bash
fly secrets set --app mino LLM_SERVICE_URL=http://mino-llm.flycast:8001
```

Give the llm-service the **same** `ENCRYPTION_KEY` and `INTERNAL_API_KEY` as the web app, or the
stored LLM key will not decrypt. The service has no public ports; fly-proxy routes flycast to it
privately, so the image keeps binding `0.0.0.0`.
