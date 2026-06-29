"""Service monitor: remote agents and URL health checks.

Drives the same ActiveIncidentState + SSE contract the frontend already consumes.
Sources of failure:
- agent: tiny agent on a user's server reports containers; fixed by queueing docker restart
       commands sent back via the next heartbeat
- url: HTTP health check, alert/escalate only — no auto-restart

ponytail: single active incident at a time, matching the single "Now" card. If several
services fail at once, the others still show status=down in the Services list and get
picked up on a later heartbeat. Per-process in-memory restart history is fine for this
single-process prototype; move it to the DB if you run multiple workers.
"""

import asyncio
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app import actions, executor_client, llm_client
from app.actions import is_allowed_action as _is_allowed_action
from app.config import get_settings
from app.database import SessionLocal
from app.events import log_event
from app.models import Guardrail, Host, Incident, IncidentEvent, Learning, Service, User, UserSettings
from app.schemas import ActiveIncidentState
from app.stream import stream_manager

logger = logging.getLogger("oncall.monitor")

ACTIVE_VIEWS = ("detecting", "diagnosing", "fixing", "verifying")
FAILED = ("down", "degraded")


def _owner(db: Session) -> User | None:
    """The fleet owner. Fleet data is scoped to this user, not whichever User
    happens to be first now that operator accounts also live in the table."""
    return db.query(User).filter(User.role == "owner").first()


def _learned_from(incidents: int, successes: int) -> str:
    noun = "incident" if incidents == 1 else "incidents"
    return f"learned from {incidents} {noun} · recovered {successes} / {incidents}"


# Strip a container's version suffix to get the service it belongs to. Kamal
# names containers <service>-<role>-<git-sha>, <service>-<role>-latest, and
# tacks on _replaced_<hex> when it rolls one out. All of those are one service.
# Names without such a suffix (plain Docker, a `db` role) are their own identity.
_VERSION_SUFFIX = re.compile(r"-([0-9a-f]{7,40}|latest)(_replaced_[0-9a-f]+)?$")


def _service_identity(name: str) -> str:
    return _VERSION_SUFFIX.sub("", name) or name


class _ServiceSnapshot:
    """Unified view of a service's current state, regardless of source."""

    def __init__(
        self,
        service_id: str,
        name: str,
        status: str,
        method: str,
        host_id: str | None,
        watch_only: bool,
        host_name: str | None = None,
        image: str | None = None,
        state: str | None = None,
        health: str | None = None,
        url: str | None = None,
        allowed_fix_action: dict | None = None,
    ):
        self.service_id = service_id
        self.name = name
        self.status = status
        self.method = method
        self.host_id = host_id
        self.watch_only = watch_only
        self.host_name = host_name
        self.image = image
        self.state = state
        self.health = health
        self.url = url
        self.allowed_fix_action = allowed_fix_action

    def display_location(self) -> str:
        if self.method == "url":
            return self.url or ""
        if self.method == "agent" and self.host_name:
            return f"{self.host_name}:{self.name}"
        return self.name


class ServiceMonitor:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._incident_id: str | None = None
        self._opened_at: datetime | None = None  # set on open; for the wide event's duration
        self._view: str = "resting"
        self._elapsed: int = 0
        self._autonomy: str = "ask_first"
        self._service_id: str | None = None
        self._service_name: str | None = None
        self._container: str | None = None
        self._method: str | None = None
        self._host_id: str | None = None
        self._severity: str = "down"
        self._proposed_fix: str | None = None
        self._proposed_fix_action: dict | None = None
        self._user_id: str | None = None
        self._escalate_on: bool = True
        self._tail_logs: bool = False
        self._llm_diagnosis: str | None = None
        self._llm_suggested_fix: str | None = None
        self._llm_confidence: str | None = None
        self._llm_action: str | None = None  # restart_container | none (model's pick)
        self._logs_arrived: asyncio.Event = asyncio.Event()
        self._llm_ready: asyncio.Event = asyncio.Event()
        self._awaiting_logs_task: asyncio.Task | None = None
        # prev status keyed by service_id so url/agent live together
        self._prev_status: dict[str, str] = {}
        self._restart_history: dict[str, list[datetime]] = {}
        # pending restarts for remote agents: {service_id: container_name}
        self._pending_agent_restarts: dict[str, dict] = {}
        # force URL check after a new URL service is registered
        self._check_urls_now = asyncio.Event()
        self._url_interval = 30

    async def start(self):
        async with self._lock:
            # Captured so threaded callers (store_agent_logs runs via
            # asyncio.to_thread) can schedule coroutines back onto the loop.
            self._loop_ref = asyncio.get_running_loop()
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def mark_url_check_needed(self):
        self._check_urls_now.set()

    async def _loop(self):
        next_url = asyncio.get_event_loop().time()
        while True:
            now = asyncio.get_event_loop().time()
            wait_url = max(0, next_url - now)
            try:
                if wait_url > 0:
                    await asyncio.wait_for(self._check_urls_now.wait(), timeout=wait_url)
                    self._check_urls_now.clear()
                next_url = now + self._url_interval
                async with self._lock:
                    await self._tick_urls()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("monitor loop failed")

    # ---- url --------------------------------------------------------------

    async def _tick_urls(self):
        services = await asyncio.to_thread(self._url_services)
        if not services:
            return
        snapshots: dict[str, _ServiceSnapshot] = {}
        async with httpx.AsyncClient(timeout=10) as client:
            for svc in services:
                status = await self._check_one_url(client, svc.health_check_url)
                snapshots[svc.name] = _ServiceSnapshot(
                    service_id=svc.id,
                    name=svc.name,
                    status=status,
                    method="url",
                    host_id=None,
                    watch_only=svc.watch_only,
                    url=svc.health_check_url,
                    allowed_fix_action=svc.allowed_fix_action,
                )
        await asyncio.to_thread(self._persist_url_statuses, snapshots)
        await self._process_sources(snapshots, source_name="url")

    def _url_services(self) -> list[Service]:
        db = SessionLocal()
        try:
            user = _owner(db)
            if not user:
                return []
            return (
                db.query(Service)
                .filter(Service.user_id == user.id, Service.method == "url")
                .all()
            )
        finally:
            db.close()

    async def _check_one_url(self, client: httpx.AsyncClient, url: str | None) -> str:
        if not url:
            return "down"
        try:
            resp = await client.get(url)
            return "healthy" if resp.status_code < 300 else "down"
        except Exception:
            return "down"

    def _persist_url_statuses(self, snapshots: dict[str, _ServiceSnapshot]):
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            for snap in snapshots.values():
                svc = db.query(Service).filter(Service.id == snap.service_id).first()
                if svc:
                    svc.status = snap.status
                    svc.last_check_at = now
            db.commit()
        finally:
            db.close()

    # ---- agent ------------------------------------------------------------

    async def handle_agent_beat(
        self, host: Host, containers: list[dict]
    ) -> tuple[list[dict], list[str]]:
        async with self._lock:
            svc_map, snapshots, fetch_logs = await asyncio.to_thread(
                self._sync_agent_services, host, containers
            )
            await self._process_sources(snapshots, source_name="agent")
            restarts: list[dict] = []
            to_clear: list[str] = []
            for sid, action in list(self._pending_agent_restarts.items()):
                name = action.get("container")
                svc = svc_map.get(name) if name else None
                if svc and svc.get("host_id") == host.id:
                    restarts.append(action)
                    to_clear.append(sid)
            for sid in to_clear:
                self._pending_agent_restarts.pop(sid, None)
            return restarts, fetch_logs

    def _sync_agent_services(
        self, host: Host, containers: list[dict]
    ) -> tuple[dict[str, dict], dict[str, _ServiceSnapshot], list[str]]:
        db = SessionLocal()
        try:
            user = _owner(db)
            if not user:
                return {}, {}, []
            existing = {
                (s.host_id, s.name): s
                for s in db.query(Service).filter(Service.user_id == user.id).all()
            }
            now = datetime.utcnow()
            svc_map: dict[str, dict] = {}
            snapshots: dict[str, _ServiceSnapshot] = {}
            fetch_logs: list[str] = []
            # Service identities that have a running container this beat. A down
            # container whose service still has a running sibling is a rollover or
            # an old version, not an outage. See issue #17.
            running_identities = {
                _service_identity(c["name"]) for c in containers if c["status"] != "down"
            }
            for c in containers:
                name = c["name"]
                key = (host.id, name)
                svc = existing.get(key)
                superseded = c["status"] == "down" and _service_identity(name) in running_identities
                if svc is None:
                    if c["status"] == "down":
                        # First time we've seen this container and it isn't
                        # running. It's a pre-existing stopped container — an old
                        # deploy left behind on a Kamal host, say — not a failure
                        # we watched happen. Ignore it until it actually comes up,
                        # so deployment history doesn't show up as a fleet of
                        # dead services. See issue #17.
                        continue
                    svc = Service(
                        user_id=user.id,
                        host_id=host.id,
                        name=name,
                        method="agent",
                        watch_only=False,
                    )
                    db.add(svc)
                elif superseded:
                    # We tracked this container while it ran, but a deploy has
                    # since replaced it with a running sibling. Drop the old
                    # version so a rollover doesn't read as an outage. The agent
                    # keeps reporting the stopped container, but it's first-seen
                    # again next beat and skipped above. See issue #17.
                    db.delete(svc)
                    continue
                else:
                    svc.method = "agent"
                    svc.host_id = host.id
                prev_status = svc.status
                svc.status = c["status"]
                svc.last_check_at = now
                svc.allowed_fix_action = {"action": "restart_container", "container": name}
                svc.agent_host_info = {
                    "id": c.get("id"),
                    "image": c.get("image"),
                    "state": c.get("state"),
                    "health": c.get("health"),
                    "host_name": host.name,
                    # Present on the log-fetch beat for a failed container; exit 137
                    # / oom_killed means a restart won't durably fix it. See #43.
                    "exit_code": c.get("exit_code"),
                    "oom_killed": c.get("oom_killed"),
                }
                # ponytail: fetch logs once on transition to failed so the
                # diagnosis has context. The agent returns them on next beat.
                if prev_status not in FAILED and c["status"] in FAILED:
                    fetch_logs.append(name)
                db.flush()
                db.refresh(svc)
                svc_map[name] = {"service_id": svc.id, "watch_only": svc.watch_only, "host_id": host.id}
                snapshots[name] = _ServiceSnapshot(
                    service_id=svc.id,
                    name=name,
                    status=c["status"],
                    method="agent",
                    host_id=host.id,
                    watch_only=svc.watch_only,
                    host_name=host.name,
                    image=c.get("image"),
                    state=c.get("state"),
                    health=c.get("health"),
                    allowed_fix_action=svc.allowed_fix_action,
                )
            db.commit()
            return svc_map, snapshots, fetch_logs
        finally:
            db.close()

    def store_agent_logs(self, host: Host, logs: dict[str, str | None]):
        """Store the latest logs sent by an agent and attach them to any open incident."""
        db = SessionLocal()
        try:
            user = _owner(db)
            settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first() if user else None
            if not user:
                return
            now = datetime.utcnow()
            for name, text in logs.items():
                if not text:
                    continue
                service = (
                    db.query(Service)
                    .filter(Service.user_id == user.id, Service.host_id == host.id, Service.name == name)
                    .first()
                )
                if not service:
                    continue
                service.watch_logs = [text]
                # Attach to the most recent open incident for this service, if any.
                incident = (
                    db.query(Incident)
                    .filter(
                        Incident.user_id == user.id,
                        Incident.service_id == service.id,
                        Incident.status == "open",
                    )
                    .order_by(Incident.started_at.desc())
                    .first()
                )
                if incident:
                    snippet = text[-2000:] if len(text) > 2000 else text
                    incident.diagnosis = (
                        f"{incident.diagnosis}\n\n--- docker logs ({name}) ---\n{snippet}"
                    ).strip()
                    incident.events.append(
                        IncidentEvent(
                            timestamp=now,
                            source="docker_logs",
                            code="logs",
                            note=f"Fetched docker logs for {name}",
                        )
                    )
                    # store_agent_logs runs in a worker thread (asyncio.to_thread),
                    # so there's no running loop here — schedule back onto the
                    # captured main loop instead of asyncio.create_task.
                    loop = getattr(self, "_loop_ref", None)
                    if loop is not None:
                        loop.call_soon_threadsafe(self._logs_arrived.set)
                        # ponytail: one-shot LLM diagnosis after the first useful log snapshot.
                        if not incident.llm_diagnosed_at and settings:
                            asyncio.run_coroutine_threadsafe(
                                self._request_llm_diagnosis(
                                    incident_id=incident.id,
                                    service=service,
                                    logs=snippet,
                                    settings=settings,
                                ),
                                loop,
                            )
                db.add(service)
            db.commit()
        finally:
            db.close()

    async def _request_llm_diagnosis(
        self,
        incident_id: str,
        service: Service,
        logs: str,
        settings: UserSettings,
    ):
        context = {
            "service_name": service.name,
            "method": service.method,
            "status": service.status,
            "image": service.agent_host_info.get("image") if service.agent_host_info else None,
            "container_state": service.agent_host_info.get("state") if service.agent_host_info else None,
            "container_health": service.agent_host_info.get("health") if service.agent_host_info else None,
            "exit_code": service.agent_host_info.get("exit_code") if service.agent_host_info else None,
            "oom_killed": service.agent_host_info.get("oom_killed") if service.agent_host_info else None,
            "location": (
                service.health_check_url
                if service.method == "url" and service.health_check_url
                else (
                    f"{service.agent_host_info.get('host_name')}:{service.name}"
                    if service.agent_host_info
                    else service.name
                )
            ),
            "logs": logs,
        }
        result = await llm_client.diagnose(
            context,
            api_key_encrypted=settings.llm_api_key_encrypted,
            provider=settings.llm_provider,
            model=settings.llm_model,
        )
        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
            if incident and incident.status == "open":
                if result:
                    incident.llm_diagnosis = result["diagnosis"]
                    incident.llm_suggested_fix = result["suggested_fix"]
                    incident.llm_confidence = result["confidence"]
                    incident.llm_diagnosed_at = datetime.utcnow()
                    db.add(incident)
                    db.commit()
                async with self._lock:
                    if self._incident_id == incident_id:
                        if result:
                            self._llm_diagnosis = result["diagnosis"]
                            self._llm_suggested_fix = result["suggested_fix"]
                            self._llm_confidence = result["confidence"]
                            # The model proposes; the server still validates against
                            # the whitelist before anything runs. "none" means the
                            # model judged no action will help. See issues #44.
                            self._llm_action = result.get("action")
                            # Let the model's pick be the action we'd run (still
                            # whitelist-checked at execution).
                            if self._llm_action in ("restart_container", "stop_container", "start_container") and self._container:
                                self._proposed_fix_action = {"action": self._llm_action, "container": self._container}
                        self._llm_ready.set()
                        self._broadcast_state()
        finally:
            db.close()

    # ---- shared state machine ---------------------------------------------

    async def _process_sources(self, snapshots: dict[str, _ServiceSnapshot], source_name: str):
        await self._reconcile_active_incident()
        by_name = {s.name: s for s in snapshots.values()}

        if self._view in ACTIVE_VIEWS:
            await self._advance_active(by_name)
        elif self._view in ("asking", "takeover"):
            cur = by_name.get(self._container)
            if self._view == "asking" and cur and cur.status == "healthy":
                await self._finish("resolved", "Recovered on its own before I acted")
            else:
                self._broadcast_state()
        else:
            await self._maybe_open(by_name)

        for snap in snapshots.values():
            self._prev_status[snap.service_id] = snap.status

    async def _advance_active(self, by_name: dict[str, _ServiceSnapshot]):
        cur = by_name.get(self._container)
        self._elapsed += get_settings().url_poll_seconds
        if cur and cur.status == "healthy":
            await self._finish("resolved", f"Restarted {self._container} — it came back healthy")
            return
        # Only the verify timer escalates here, and only once we've actually
        # attempted a restart. During detecting/diagnosing (ask_first waiting on
        # logs, the LLM, or a human) the incident must stay put — escalating then
        # would skip the diagnosis entirely.
        if (
            self._view in ("fixing", "verifying")
            and self._escalate_on
            and self._elapsed >= get_settings().docker_verify_timeout_seconds
        ):
            await self._finish("escalated", "Restart didn't bring it back in time — handed to you")
            return
        if self._view == "fixing":
            self._view = "verifying"
        self._broadcast_state()

    async def _maybe_open(self, by_name: dict[str, _ServiceSnapshot]):
        newly_failed = [
            c
            for name, c in by_name.items()
            if c.status in FAILED and self._prev_status.get(c.service_id) not in FAILED
        ]
        target = None
        for c in newly_failed:
            if c.watch_only:
                await asyncio.to_thread(self._log_watch_only_incident, c)
            elif target is None:
                target = c
        if not target:
            if self._view == "resolved":
                self._view = "resting"
                self._broadcast_state()
            return

        info = await asyncio.to_thread(self._open_incident, target)
        if not info:
            return
        self._incident_id = info["incident_id"]
        self._opened_at = datetime.utcnow()
        self._service_id = info["service_id"]
        self._user_id = info["user_id"]
        self._service_name = target.name
        self._container = target.name
        self._method = target.method
        self._host_id = target.host_id
        self._severity = "down" if target.status == "down" else "degraded"
        self._autonomy = info["autonomy"]
        self._escalate_on = info["escalate_on"]
        self._tail_logs = target.method == "agent"
        self._proposed_fix = target.allowed_fix_action.get("container") if isinstance(target.allowed_fix_action, dict) else target.name
        self._proposed_fix_action = target.allowed_fix_action if isinstance(target.allowed_fix_action, dict) else {"action": "restart_container", "container": target.name}
        self._elapsed = 0  # fresh incident; the verify timer starts at the restart
        self._llm_action = None
        self._logs_arrived.clear()
        self._llm_ready.clear()

        stream_manager.broadcast("incident_created", {"incident_id": self._incident_id})

        if self._method == "url":
            # Komodo can't restart a URL endpoint. There are no logs to fetch, so
            # diagnose from the endpoint + status and hand it to a human — never
            # offer a restart we can't perform. See issues #33, #35.
            self._proposed_fix = None
            self._proposed_fix_action = None
            self._view = "detecting"
            self._logs_arrived.set()
            self._awaiting_logs_task = asyncio.create_task(self._diagnose_url_then_ask())
        elif self._autonomy == "ask_first":
            self._view = "detecting"
            self._awaiting_logs_task = asyncio.create_task(self._wait_then_ask())
        elif info["rate_limited"]:
            await self._finish("escalated", "Hit the restart limit (3/hour) — handed to you")
            return
        elif self._method == "agent":
            # ponytail: pause to collect logs and LLM diagnosis before acting.
            # This keeps the dashboard useful and gives the LLM context.
            self._view = "detecting"
            self._awaiting_logs_task = asyncio.create_task(self._wait_then_restart())
        else:
            await self._do_restart()
        self._broadcast_state()

    async def _diagnose_url_then_ask(self, llm_timeout: float = 20.0):
        try:
            await asyncio.wait_for(self._diagnose_url(self._incident_id, self._service_id), timeout=llm_timeout)
        except (asyncio.TimeoutError, Exception):
            pass
        async with self._lock:
            if self._view in ("detecting", "diagnosing") and self._incident_id:
                self._view = "asking"
                self._broadcast_state()

    async def _diagnose_url(self, incident_id: str | None, service_id: str | None):
        if not incident_id or not service_id:
            return

        def load():
            db = SessionLocal()
            try:
                user = _owner(db)
                svc = db.query(Service).filter(Service.id == service_id).first()
                settings = (
                    db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
                    if user
                    else None
                )
                if svc is not None:
                    # touch fields so they load before the session closes
                    _ = (svc.name, svc.method, svc.status, svc.health_check_url, svc.agent_host_info)
                return svc, settings
            finally:
                db.close()

        svc, settings = await asyncio.to_thread(load)
        if svc and settings:
            await self._request_llm_diagnosis(incident_id=incident_id, service=svc, logs=None, settings=settings)

    async def _wait_then_ask(self, log_timeout: float = 12.0, llm_timeout: float = 15.0):
        try:
            await asyncio.wait_for(self._logs_arrived.wait(), timeout=log_timeout)
            async with self._lock:
                if self._view == "detecting" and self._incident_id:
                    self._view = "diagnosing"
                    self._broadcast_state()
        except asyncio.TimeoutError:
            pass
        try:
            await asyncio.wait_for(self._llm_ready.wait(), timeout=llm_timeout)
        except asyncio.TimeoutError:
            pass
        async with self._lock:
            if self._view in ("detecting", "diagnosing") and self._incident_id:
                self._view = "asking"
                self._broadcast_state()

    async def _wait_then_restart(self, log_timeout: float = 12.0, llm_timeout: float = 15.0):
        try:
            await asyncio.wait_for(self._logs_arrived.wait(), timeout=log_timeout)
            async with self._lock:
                if self._view == "detecting" and self._incident_id:
                    self._view = "diagnosing"
                    self._broadcast_state()
        except asyncio.TimeoutError:
            pass
        try:
            await asyncio.wait_for(self._llm_ready.wait(), timeout=llm_timeout)
        except asyncio.TimeoutError:
            pass
        async with self._lock:
            if self._view in ("detecting", "diagnosing") and self._incident_id:
                if self._llm_action == "none":
                    # The model judged a restart won't help — don't auto-restart
                    # into the same failure; hand it to a person. See issue #44.
                    await self._finish("escalated", "A restart likely won't fix this — handed to you")
                else:
                    await self._do_restart()
                self._broadcast_state()

    async def _do_restart(self):
        """Queue or perform a restart using only whitelisted actions."""
        self._restart_history.setdefault(self._container, []).append(datetime.utcnow())
        if self._method == "agent":
            action = self._proposed_fix_action or {"action": "restart_container", "container": self._container}
            if not _is_allowed_action(action):
                logger.warning("refusing disallowed action: %s", action)
                await self._finish("escalated", "Refusing unsafe fix command — handed to you")
                return
            self._pending_agent_restarts[self._service_id] = action
            self._view = "fixing"
            self._elapsed = 0
        elif self._method == "url":
            await self._finish("escalated", "URL service is down — I can't restart it, handing to you")
        else:
            token = executor_client.sign_action("restart_container", self._container)
            ok, err = await executor_client.send_action(self._executor_url(), token)
            if not ok:
                logger.warning("local executor restart failed: %s", err)
                await self._finish("escalated", f"Restart failed: {err}")
                return
            self._view = "fixing"
            self._elapsed = 0

    # ---- human actions (called by routers/incidents.py) -------------------

    async def approve(self) -> ActiveIncidentState:
        async with self._lock:
            if self._view != "asking":
                return self._build_state()
            await self._do_restart()
            self._broadcast_state()
            return self._build_state()

    async def take_over(self) -> ActiveIncidentState:
        async with self._lock:
            if self._view not in ("asking",) + ACTIVE_VIEWS:
                return self._build_state()
            self._view = "takeover"
            self._tail_logs = False
            if self._awaiting_logs_task and not self._awaiting_logs_task.done():
                self._awaiting_logs_task.cancel()
            self._awaiting_logs_task = None
            self._broadcast_state()
            return self._build_state()

    async def hand_back(self) -> ActiveIncidentState:
        async with self._lock:
            if self._view != "takeover":
                return self._build_state()
            self._tail_logs = True
            await self._do_restart()
            self._broadcast_state()
            return self._build_state()

    async def resolve(self, *, manual: bool = False) -> ActiveIncidentState:
        async with self._lock:
            if self._view in ("resting", "resolved"):
                return self._build_state()
            if manual:
                await self._finish("took_over", "You took it")
            else:
                await self._finish("resolved", f"Restarted {self._container}")
            return self._build_state()

    async def simulate(self) -> ActiveIncidentState:
        """Real failure test: stop a healthy agent-managed container."""
        async with self._lock:
            if self._view not in ("resting", "resolved"):
                return self._build_state()

        db = SessionLocal()
        try:
            user = _owner(db)
            if not user:
                async with self._lock:
                    return self._build_state()
            target = (
                db.query(Service)
                .filter(Service.user_id == user.id, Service.method == "agent", Service.status == "healthy")
                .order_by(Service.last_check_at.desc())
                .first()
            )
        finally:
            db.close()

        if target and target.allowed_fix_action:
            action = target.allowed_fix_action.get("action")
            name = target.allowed_fix_action.get("container")
            if name:
                token = executor_client.sign_action(action, name)
                ok, err = await executor_client.send_action(self._executor_url(), token)
                if not ok:
                    logger.warning("simulate action failed: %s", err)

        async with self._lock:
            return self._build_state()

    def _executor_url(self) -> str | None:
        # ponytail: for MVP, executor runs on the same host as the control plane.
        # Replace with per-host executor URL when scaling out.
        return "http://localhost:8002"

    async def _reconcile_active_incident(self):
        """Self-heal if the active incident's row was deleted out from under us
        (e.g. its server was removed). The monitor keeps the active incident in
        memory, so a delete would otherwise leave the Now card stuck on a
        nonexistent incident until the process restarts. See issue #21."""
        if not self._incident_id:
            return
        still_there = await asyncio.to_thread(self._active_incident_exists, self._incident_id)
        if not still_there:
            logger.info("active incident %s is gone from the DB; resetting to resting", self._incident_id)
            self._reset_to_resting()
            self._broadcast_state()

    @staticmethod
    def _active_incident_exists(incident_id: str) -> bool:
        db = SessionLocal()
        try:
            return db.query(Incident.id).filter(Incident.id == incident_id).first() is not None
        finally:
            db.close()

    def _reset_to_resting(self):
        self._view = "resting"
        self._incident_id = None
        self._service_id = None
        self._service_name = None
        self._container = None
        self._method = None
        self._host_id = None
        self._tail_logs = False
        self._llm_diagnosis = None
        self._llm_suggested_fix = None
        self._llm_confidence = None
        self._llm_action = None
        self._elapsed = 0
        if self._awaiting_logs_task and not self._awaiting_logs_task.done():
            self._awaiting_logs_task.cancel()
        self._awaiting_logs_task = None

    async def _finish(self, status: str, action: str):
        await asyncio.to_thread(self._resolve_incident, status, action)
        # One wide event per incident: the whole life in a single line.
        log_event(
            "incident_resolved",
            incident_id=self._incident_id,
            service=self._service_name,
            host_id=self._host_id,
            method=self._method,
            severity=self._severity,
            autonomy=self._autonomy,
            final_status=status,
            action_taken=action,
            llm_diagnosis=self._llm_diagnosis,
            llm_confidence=self._llm_confidence,
            llm_action=self._llm_action,
            proposed_action=(self._proposed_fix_action or {}).get("action"),
            user_id=self._user_id,
            duration_s=int((datetime.utcnow() - self._opened_at).total_seconds())
            if self._opened_at
            else None,
        )
        self._view = "resolved"
        self._tail_logs = False
        self._llm_diagnosis = None
        self._llm_suggested_fix = None
        self._llm_confidence = None
        self._llm_action = None
        if self._awaiting_logs_task and not self._awaiting_logs_task.done():
            self._awaiting_logs_task.cancel()
        self._awaiting_logs_task = None
        self._logs_arrived.set()
        self._llm_ready.set()
        self._broadcast_state()

    # ---- DB writes (run in a thread) --------------------------------------

    def _open_incident(self, snapshot: _ServiceSnapshot) -> dict | None:
        db = SessionLocal()
        try:
            user = _owner(db)
            settings = db.query(UserSettings).first()
            service = db.query(Service).filter(Service.id == snapshot.service_id).first()
            if not user or not settings or not service:
                return None

            severity = "down" if snapshot.status == "down" else "degraded"
            location = snapshot.display_location()
            if snapshot.method == "url":
                summary = f"{snapshot.name} is down"
                diagnosis = f"URL check to {snapshot.url} failed."
            else:
                state_note = snapshot.state if snapshot.status == "down" else "unhealthy"
                summary = (
                    f"{snapshot.name} went down"
                    if severity == "down"
                    else f"{snapshot.name} is unhealthy"
                )
                diagnosis = f"Container {location} ({snapshot.image}) reported {state_note}."

            incident = Incident(
                user_id=user.id,
                service_id=service.id,
                severity=severity,
                status="open",
                summary=summary,
                diagnosis=diagnosis,
                confidence_pct=95,
                sure=True,
                started_at=datetime.utcnow(),
                action_taken="Pending",
            )
            incident.events.append(
                IncidentEvent(
                    timestamp=datetime.utcnow(),
                    source=snapshot.method,
                    code=severity,
                    note=f"state={snapshot.state or 'none'} health={snapshot.health or 'none'}",
                )
            )
            db.add(incident)
            db.commit()
            db.refresh(incident)

            rate_on = self._guardrail_on(db, user.id, "rate_limit")
            # A server can override the fleet-wide autonomy (e.g. ask-first on a
            # production box, auto-fix elsewhere). Null means use the global one.
            host = db.query(Host).filter(Host.id == service.host_id).first() if service.host_id else None
            autonomy = (host.autonomy if host and host.autonomy else settings.autonomy)
            log_event(
                "incident_opened",
                incident_id=incident.id,
                service=service.name,
                host_id=service.host_id,
                method=snapshot.method,
                severity=severity,
                autonomy=autonomy,
                user_id=user.id,
            )
            return {
                "incident_id": incident.id,
                "service_id": service.id,
                "user_id": user.id,
                "autonomy": autonomy,
                "rate_limited": rate_on and self._recent_restarts(snapshot.name) >= 3,
                "escalate_on": self._guardrail_on(db, user.id, "escalate_90"),
            }
        finally:
            db.close()

    def _log_watch_only_incident(self, snapshot: _ServiceSnapshot):
        db = SessionLocal()
        try:
            user = _owner(db)
            service = db.query(Service).filter(Service.id == snapshot.service_id).first()
            if not user or not service:
                return
            severity = "down" if snapshot.status == "down" else "degraded"
            now = datetime.utcnow()
            incident = Incident(
                user_id=user.id,
                service_id=service.id,
                severity=severity,
                status="escalated",
                summary=f"{snapshot.name} is {severity}",
                diagnosis=f"{snapshot.name} is watch-only — I flagged it but won't touch it.",
                confidence_pct=95,
                sure=True,
                started_at=now,
                resolved_at=now,
                duration_seconds=0,
                action_taken="watch-only — I won't touch this one",
            )
            incident.events.append(
                IncidentEvent(
                    timestamp=now,
                    source=snapshot.method,
                    code=severity,
                    note=f"watch-only · state={snapshot.state or 'none'} health={snapshot.health or 'none'}",
                )
            )
            db.add(incident)
            db.commit()
            db.refresh(incident)
            stream_manager.broadcast("incident_created", {"incident_id": incident.id})
        finally:
            db.close()

    def _resolve_incident(self, status: str, action: str):
        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == self._incident_id).first()
            if not incident:
                return
            now = datetime.utcnow()
            incident.status = status
            incident.resolved_at = now
            incident.duration_seconds = int((now - incident.started_at).total_seconds())
            incident.action_taken = action
            db.add(incident)
            code = {"resolved": "resolved", "took_over": "took over", "escalated": "escalated"}.get(status, status)
            incident.events.append(IncidentEvent(timestamp=now, source=self._method or "docker", code=code, note=action))
            if status == "resolved" and self._service_id:
                self._record_learning(db, incident)
            db.commit()
        finally:
            db.close()

    def _record_learning(self, db: Session, incident: Incident):
        rule_text = f"When {self._service_name} goes unhealthy, a docker restart brings it back."
        # Match on the rule, not the service id. A re-added host gives the same
        # container a fresh service id, and keying on it spawned a duplicate card
        # for what is the same recurring behavior.
        existing = (
            db.query(Learning)
            .filter(Learning.user_id == incident.user_id, Learning.rule == rule_text)
            .first()
        )
        if existing:
            existing.incident_count += 1
            existing.success_count += 1
            existing.service_id = self._service_id  # point at the current service
            existing.learned_from = _learned_from(existing.incident_count, existing.success_count)
            existing.updated_at = datetime.utcnow()
        else:
            db.add(
                Learning(
                    user_id=incident.user_id,
                    service_id=self._service_id,
                    rule=rule_text,
                    learned_from=_learned_from(1, 1),
                    behavior="auto_fix",
                    incident_count=1,
                    success_count=1,
                )
            )
            stream_manager.broadcast(
                "learning_created", {"service_id": self._service_id, "rule": rule_text}
            )

    def _guardrail_on(self, db: Session, user_id: str, key: str) -> bool:
        g = db.query(Guardrail).filter(Guardrail.user_id == user_id, Guardrail.key == key).first()
        return bool(g and g.value)

    def _recent_restarts(self, name: str) -> int:
        cutoff = datetime.utcnow() - timedelta(hours=1)
        hist = [t for t in self._restart_history.get(name, []) if t >= cutoff]
        self._restart_history[name] = hist
        return len(hist)

    # ---- state for the frontend -------------------------------------------

    def should_tail_logs(self) -> tuple[bool, str | None]:
        return self._tail_logs, self._container if self._tail_logs else None

    def get_state(self) -> ActiveIncidentState:
        return self._build_state()

    def _broadcast_state(self):
        stream_manager.broadcast("incident_state", self._build_state().model_dump())

    def _build_state(self) -> ActiveIncidentState:
        return ActiveIncidentState(
            incident_id=self._incident_id,
            service_id=self._service_id,
            service_name=self._service_name,
            host_id=self._host_id,
            method=self._method,
            proposed_action=(
                self._proposed_fix_action.get("action")
                if isinstance(self._proposed_fix_action, dict)
                else None
            ),
            view=self._view,
            elapsed=self._elapsed,
            autonomy=self._autonomy,
            # Offer approve-restart only when it's actually runnable: at the ask
            # step, not a URL (can't restart), and the model didn't say a restart
            # won't help. See issues #33, #44.
            can_approve=(
                self._view == "asking"
                and self._method != "url"
                and self._llm_action != "none"
            ),
            can_take_over=self._view in ("asking",) + ACTIVE_VIEWS,
            can_hand_back=self._view == "takeover",
            timeline=self._build_timeline(),
            proposed_fix=self._llm_suggested_fix or self._proposed_fix,
            status_text=self._status_text(),
            status_dot=self._status_dot(),
            llm_diagnosis=self._llm_diagnosis,
            llm_suggested_fix=self._llm_suggested_fix,
            llm_confidence=self._llm_confidence,
        )

    def _status_text(self) -> str:
        return {
            "resting": "all green",
            "resolved": "recovered",
            "detecting": "acting",
            "diagnosing": "acting",
            "fixing": "acting",
            "verifying": "acting",
            "asking": "waiting on you",
            "takeover": "you have it",
        }.get(self._view, "watching")

    def _status_dot(self) -> str:
        if self._view in ("resting", "resolved"):
            return "green"
        if self._view == "asking":
            return "dashed-red"
        if self._view == "takeover":
            return "dashed-gray"
        return "red"

    def _build_timeline(self) -> list[dict[str, Any]]:
        if not self._incident_id:
            return []
        name = self._container
        detected = {"kind": "done", "text": f"Detected — {name} is {self._severity}", "time": "now"}

        if self._view == "asking":
            return [
                detected,
                {"kind": "wait", "text": "Waiting for you — approve a docker restart", "time": "paused"},
                {"kind": "pending", "text": f"Restart {name}", "time": ""},
                {"kind": "pending", "text": "Verify it comes back healthy", "time": ""},
            ]
        if self._view == "takeover":
            return [
                detected,
                {"kind": "wait", "text": "You took it — I'll stand by", "time": "paused"},
            ]

        resolved = self._view == "resolved"
        te = self._elapsed
        return [
            detected,
            {
                "kind": "done",
                "text": f"Restarting {name}",
                "time": "docker restart",
            },
            {
                "kind": "done" if resolved else "active",
                "text": "Verify — waiting for healthy",
                "time": "healthy again" if resolved else f"checking… {te}s",
            },
            {
                "kind": "done" if resolved else "pending",
                "text": "Log the outcome to incidents",
                "time": "done" if resolved else "",
            },
        ]


monitor = ServiceMonitor()
