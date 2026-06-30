# Architecture

## Services and ports

```
   ┌── a host you monitor ────┐         ┌──────────────── Mino server ─────────────────┐
   │  mino-agent.py         │  beats  │  backend (FastAPI)                              │
   │  reads docker ps         │ ──────► │  opens incidents, runs the state machine        │
   │  runs docker restart      │ ◄────── │  asks llm-service to diagnose                   │
   │  when told to            │ actions │  streams the live state to the UI over SSE      │
   └──────────────────────────┘         │  frontend (SvelteKit) · postgres · executor    │
                                         └─────────────────────────────────────────────────┘
```

| Service | Port | Role |
|---|---|---|
| caddy | 80, 443 | the only public port; serves the frontend, forwards `/api` to the backend |
| frontend | 5173 | the SvelteKit dashboard (internal) |
| backend | 8000 | control plane: incidents, auth, the SSE stream (internal) |
| llm-service | 8001 | makes the LLM call; reached only by the backend (internal) |
| executor | 8002 | runs whitelisted Docker actions for signed tokens (internal) |
| postgres | 5432 | state (internal) |

Only Caddy is published. The rest talk over the Compose network.

## The agent

A single dependency-free Python file on each monitored host. It reports container status over
`/api/v1/agent/beat` and fetches logs over `/api/v1/agent/logs`, authenticated by a host token. When
the backend tells it to, it runs `docker restart`. The agent handles remote hosts. The executor is
the equivalent path for the control-plane host itself.

## Roles

| Capability | Owner | Operator |
|---|---|---|
| See the fleet, incidents, guardrails | yes | yes |
| Approve, take over, resolve, hand back an incident | yes | yes |
| Change settings, the LLM key, autonomy | yes | no |
| Add or remove hosts and services | yes | no |
| Toggle guardrails | yes | no |
| Run a simulation, fetch the agent script | yes | no |
| Manage the team | yes | no |
| Edit their own profile | yes | yes |

## Auth

A user signs in and receives a JWT in an HttpOnly cookie. Passwords are hashed with bcrypt. Because
the whole app sits on one origin, the cookie travels with both the page and the API. The agent and
the executor use their own tokens, separate from user sessions.
