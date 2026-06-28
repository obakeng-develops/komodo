# Add an executor type

Komodo watches Docker today. The kind of thing a service runs on is its **executor type**, and it is
carried by the service's `method`:

- `agent` and `docker` — a Docker container Komodo can `docker restart`.
- `url` — an HTTP endpoint Komodo can only alert on.

Adding a new type, say Kubernetes, means teaching four parts of the system about it. Only one of them
is a one-line change; the rest is real work, so this guide is a map, not a recipe.

## 1. Report the services

Something has to tell Komodo what services exist and whether they are healthy. For Docker that is the
agent (`agent/komodo-agent.py`), which runs `docker ps` and posts the result to `/api/v1/agent/beat`.
The backend turns that into services with `method = "agent"` in `_sync_agent_services`
(`backend/app/monitor.py`).

A new platform needs its own reporter that posts services tagged with the new method, and a backend
path that accepts them. The beat endpoint is shaped around Docker containers, so this is the largest
piece.

## 2. Give the model the right context

This is the clean seam. In `llm-service/app/llm.py`, `_platform_guidance(method)` returns the sentence
that tells the model what the service is and what Komodo can do about it. Add a case:

```python
if method == "kubernetes":
    return (
        "This service is a Kubernetes deployment. The only remediation Komodo can "
        "perform is `kubectl rollout restart deployment <name>`. ..."
    )
```

Without this, the model invents a fix from thin air, which is how an early version suggested `kubectl`
on a Docker-only fleet.

## 3. Define the remediation and run it

Decide the action that fixes the service and the component that performs it. For Docker the agent runs
`docker restart`, and the signed-action executor (`executor/`) runs whitelisted Docker actions on
hosts that allow it. A new type needs its own action and an executor that carries it out.

## 4. Keep it inside the guardrails

Remediation only runs if it passes the action whitelist (`backend/app/actions.py`,
`is_allowed_action`). Add the new action there, and nowhere else, so the safety boundary stays in one
place. See [How Komodo works](../explanation/how-komodo-works.md#guardrails) for why the whitelist
exists.

## The short version

The model context (step 2) is meant to be extended by anyone, in one place. The reporter and the
remediation (steps 1 and 3) are where the work is, because Komodo's heartbeat and executor are built
for Docker. Start there only if you have a real second platform to watch; until then, the single
executor type is the right amount of system.
