# Get Mino running and watch it heal a container

This is a lesson, not a reference. Follow it start to finish and you will end with Mino watching
a real container, catching it when it fails, and bringing it back. Set aside about fifteen minutes.

You need Python 3.13, Node, and Docker on your machine.

## 1. Start the backend

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
AUTH_SECRET=dev-secret ENCRYPTION_KEY=dev-key DATABASE_URL="sqlite:///./oncall.db" \
  uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The backend now runs on port 8000 against a local SQLite file. Leave it running.

## 2. Start the frontend

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Mino asks you to create the owner account. Pick any email and
password. You are now looking at the **Now** view. It is quiet, because nothing is being watched yet.

## 3. Give Mino a host to watch

Mino watches a host through a small agent. You will run that agent against your own Docker.

1. Open **Settings**, then **Connected servers**, then **Add server**. Name it `local`.
2. Click **Install**. Mino shows a command with a token in it. Copy it.
3. Run it in a third terminal. It looks like this:

```bash
curl -fsSL http://localhost:8000/api/v1/agent/script \
  | python3 - --server http://localhost:8000 --token <your-token>
```

Within a few seconds the agent reports your containers, and they appear in Mino.

## 4. Break something on purpose

Start a throwaway container, then stop it and watch Mino notice.

```bash
docker run -d --name mino-demo nginx
```

Give the agent a moment to report it. Then stop it:

```bash
docker stop mino-demo
```

Switch to the **Now** view. Mino detects that `mino-demo` is down, opens an incident, reads the
logs, and asks the LLM what happened. If you set an autonomy of auto-fix, the agent restarts the
container and the incident resolves on its own. If you left it on ask-first, Mino waits with a
diagnosis and an **Approve** button. Click it and watch the container come back.

## 5. Clean up

```bash
docker rm -f mino-demo
```

## What you learned

You ran Mino, connected a host, and watched a full incident: detect, diagnose, fix, resolve. From
here:

- To put this on a server, read [Deploy with Docker Compose](../how-to/deploy-with-docker-compose.md).
- To understand the decisions Mino just made, read [How Mino works](../explanation/how-mino-works.md).
- For LLM diagnoses with a real model, read [Choose an LLM provider](../how-to/choose-an-llm-provider.md).
