# Events

Mino emits one **wide, structured event per unit of work** — a single JSON line, not a
trail of plain-text lines you have to grep and stitch together. Each line is a flat JSON
object on the named logger, so you can filter by `event` and read an incident, a beat, or an
action end to end.

```json
{"event": "incident_resolved", "ts": "2026-06-29T08:59:19Z", "incident_id": "…", "service": "web", "final_status": "resolved", "duration_s": 42, …}
```

Common to every event: `event` (the name) and `ts` (UTC ISO-8601). **Fields that are absent
were not set** — the emitter drops `null` values rather than logging them.

No event carries personally identifiable data. A person is referenced by `user_id` (an opaque
UUID) only; never a name, email, secret, or token.

## `incident_opened`

Emitted when an incident starts, for real-time visibility. Logger: `oncall.events` (backend).

| Field | Meaning |
|---|---|
| `incident_id` | the incident |
| `service` | service name |
| `host_id` | host the service runs on |
| `method` | executor type (`agent` / `docker` / `url`) |
| `severity` | `down` or `degraded` |
| `autonomy` | resolved autonomy for this incident (host override or fleet default) |
| `user_id` | owner the incident belongs to |

## `incident_resolved`

Emitted once when an incident ends — the whole life in a single line. Logger: `oncall.events`
(backend). Fires for every terminal status, not just `resolved`.

| Field | Meaning |
|---|---|
| `incident_id`, `service`, `host_id`, `method`, `severity`, `autonomy` | as above |
| `final_status` | `resolved`, `escalated`, or `took_over` |
| `action_taken` | human-readable summary of what closed it |
| `llm_diagnosis` | the model's root-cause text (about the service, not the user) |
| `llm_confidence` | `low` / `medium` / `high` |
| `llm_action` | the action the model picked (`restart_container`, …, or `none`) |
| `proposed_action` | the action Mino intended to run |
| `user_id` | who acted, if a human did |
| `duration_s` | seconds from open to close |

## `agent_beat`

Emitted on each agent heartbeat. Logger: `oncall.events` (backend). High volume — one per
host per interval.

| Field | Meaning |
|---|---|
| `host` | host name |
| `agent_version` | version the agent reported |
| `agent_outdated` | `true` if it differs from the version the server serves |
| `containers` | containers reported this beat |
| `down`, `degraded` | counts by status |
| `actions` | approved actions returned to the agent |

## `executor_action`

Emitted by the executor for each action it runs. Logger: `executor.events` (executor service).

| Field | Meaning |
|---|---|
| `action` | `restart_container`, `stop_container`, `start_container`, `fetch_logs`, `list_containers` |
| `container` | target container, if the action takes one |
| `ok` | whether the action succeeded |
| `duration_ms` | how long it took |

## Shipping events somewhere

Events go to stdout as JSON. A log collector (Honeycomb, OTel, Loki, …) can consume them as
structured records without further work; Mino does not ship them anywhere itself. Frontend
product analytics is a separate concern — see issue #55.
