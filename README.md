# Komodo

Komodo keeps your Docker containers running. It watches them, works out why one failed, restarts
it within the limits you set, and shows you the whole thing as it happens. Or it stops and asks
first. That part is your call.

You log in. Your teammates log in. Everyone sees the same fleet. Owners change things; operators
watch and act on incidents but cannot touch the settings.

## Documentation

The docs follow [Diátaxis](https://diataxis.fr/). Pick the door that matches what you need right now.

**Learning.** New to Komodo? Start here.
- [Get Komodo running and watch it heal a container](docs/tutorials/getting-started.md)

**Doing.** You have a goal and want the steps.
- [Deploy with Docker Compose](docs/how-to/deploy-with-docker-compose.md)
- [Deploy with fly.io](docs/how-to/deploy-with-fly.md)
- [Deploy with Kamal](docs/how-to/deploy-with-kamal.md)
- [Install the agent on a host](docs/how-to/install-the-agent.md)
- [Choose an LLM provider](docs/how-to/choose-an-llm-provider.md)
- [Manage your team](docs/how-to/manage-your-team.md)
- [Add an executor type](docs/how-to/add-an-executor-type.md)
- [Sign off before pushing](docs/how-to/sign-off-before-pushing.md)

**Looking up.** You need a fact.
- [Configuration](docs/reference/configuration.md)
- [Architecture](docs/reference/architecture.md)

**Understanding.** You want to know why.
- [How Komodo works](docs/explanation/how-komodo-works.md)
- [Why one origin](docs/explanation/one-origin.md)
- [Security](docs/explanation/security.md)

## In a hurry

Run it on your machine in two terminals. No Docker needed.

```bash
# backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
AUTH_SECRET=dev-secret ENCRYPTION_KEY=dev-key DATABASE_URL="sqlite:///./oncall.db" \
  uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 and create the owner account. The full walkthrough is in the
[tutorial](docs/tutorials/getting-started.md).
