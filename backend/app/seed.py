from app.config import get_settings
from app.database import SessionLocal
from app.deps import hash_password
from app.models import Guardrail, User, UserSettings


def ensure_seed_data():
    db = SessionLocal()
    try:
        _seed_fleet(db)
        _bootstrap_owner(db)
    finally:
        db.close()


def _bootstrap_owner(db):
    """Headless owner bootstrap from env. Runs every startup but is CREATE-ONLY:
    once an owner who can log in exists (via env OR the first-run setup page), this
    no-ops, so a restart never clobbers a password. With no env creds and no owner,
    nobody can log in until the first-run setup page is used.
    """
    s = get_settings()
    if not (s.owner_email and s.owner_password):
        return
    if db.query(User).filter(User.role == "owner", User.password_hash.isnot(None)).first():
        return
    owner = db.query(User).filter(User.email == s.owner_email).first()
    if owner is None:
        owner = db.query(User).filter(User.role == "owner").first() or db.query(User).first()
        if owner is None:
            owner = User(email=s.owner_email, name="Owner")
            db.add(owner)
            db.flush()
    owner.email = s.owner_email
    owner.role = "owner"
    owner.password_hash = hash_password(s.owner_password)
    db.commit()


def _seed_fleet(db):
    if db.query(User).first():
        return

    user = User(email="sam@example.com", name="Sam Rivera", phone="+1 (415) 555-0142")
    db.add(user)
    db.flush()

    # ask_first by default: with auto-discovery the agent watches every container,
    # so nothing gets a real `docker restart` until you opt into auto-fix.
    settings = UserSettings(
        user_id=user.id,
        autonomy="ask_first",
        ask_below_pct=80,
        quiet_low_severity=False,
        escalation_contact="Sam Rivera (me)",
        phone_number="+1 (415) 555-0142",
    )
    db.add(settings)

    guardrails = [
        Guardrail(
            user_id=user.id,
            key="restart_only",
            label="Restart is the only action it takes",
            description="The agent only ever runs `docker restart` — never stop, scale or redeploy.",
            kind="locked",
            value=True,
        ),
        Guardrail(
            user_id=user.id,
            key="reversible",
            label="Never destructive",
            description="No `docker rm`, no deleting volumes or images. Nothing it can't undo.",
            kind="locked",
            value=True,
        ),
        Guardrail(
            user_id=user.id,
            key="rate_limit",
            label="Stop after 3 restarts in an hour",
            description="If a container keeps crash-looping, it escalates to you instead of restarting again.",
            kind="toggle",
            value=True,
        ),
        Guardrail(
            user_id=user.id,
            key="escalate_90",
            label="Escalate if not healthy within 90s",
            description="If a restart doesn't bring the container back in time, it hands off to you.",
            kind="toggle",
            value=True,
        ),
    ]
    db.add_all(guardrails)
    db.commit()
