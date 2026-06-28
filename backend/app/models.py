import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    role = Column(String, nullable=False, default="operator")
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    settings = relationship("UserSettings", back_populates="user", uselist=False)
    hosts = relationship("Host", back_populates="user")
    services = relationship("Service", back_populates="user")
    incidents = relationship("Incident", back_populates="user")
    learnings = relationship("Learning", back_populates="user")
    guardrails = relationship("Guardrail", back_populates="user")


class Host(Base):
    __tablename__ = "hosts"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    token_hash = Column(String, nullable=True)
    token = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="hosts")
    services = relationship("Service", back_populates="host")


class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    autonomy = Column(String, nullable=False, default="auto_fix")  # auto_fix | ask_first
    ask_below_pct = Column(Integer, nullable=False, default=80)
    quiet_low_severity = Column(Boolean, nullable=False, default=False)
    escalation_contact = Column(String, nullable=False, default="Sam Rivera (me)")
    phone_number = Column(String, nullable=True)
    llm_provider = Column(String, nullable=False, default="deepseek")
    llm_model = Column(String, nullable=False, default="deepseek-v4-flash")
    llm_api_key_encrypted = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")


class Service(Base):
    __tablename__ = "services"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    host_id = Column(String, ForeignKey("hosts.id"), nullable=True)
    name = Column(String, nullable=False)
    method = Column(String, nullable=False)  # agent | url
    health_check_url = Column(String, nullable=True)
    agent_token = Column(String, nullable=True)
    agent_host_info = Column(JSON, nullable=True)
    watch_logs = Column(JSON, default=list, nullable=False)
    allowed_fix_action = Column(JSON, nullable=True)
    watch_only = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="healthy")
    last_check_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="services")
    host = relationship("Host", back_populates="services")
    # cascade so removing a service drops everything that references it instead
    # of hitting a foreign-key violation (which 500s the delete).
    incidents = relationship(
        "Incident", back_populates="service", cascade="all, delete-orphan"
    )
    learnings = relationship(
        "Learning", back_populates="service", cascade="all, delete-orphan"
    )
    guardrails = relationship(
        "Guardrail", back_populates="service", cascade="all, delete-orphan"
    )


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    service_id = Column(String, ForeignKey("services.id"), nullable=False)
    severity = Column(String, nullable=False)  # down | degraded
    status = Column(String, nullable=False)  # open | resolved | escalated | took_over
    summary = Column(String, nullable=False)
    diagnosis = Column(Text, nullable=False)
    confidence_pct = Column(Integer, nullable=False)
    sure = Column(Boolean, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    action_taken = Column(String, nullable=True)
    llm_diagnosis = Column(Text, nullable=True)
    llm_suggested_fix = Column(String, nullable=True)
    llm_confidence = Column(String, nullable=True)
    llm_diagnosed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="incidents")
    service = relationship("Service", back_populates="incidents")
    events = relationship(
        "IncidentEvent",
        back_populates="incident",
        order_by="IncidentEvent.timestamp",
        cascade="all, delete-orphan",
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    id = Column(String, primary_key=True, default=gen_uuid)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String, nullable=False)
    code = Column(String, nullable=False)
    note = Column(String, nullable=False)

    incident = relationship("Incident", back_populates="events")


class Learning(Base):
    __tablename__ = "learnings"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    service_id = Column(String, ForeignKey("services.id"), nullable=True)
    rule = Column(Text, nullable=False)
    learned_from = Column(String, nullable=False)
    behavior = Column(String, nullable=False)  # auto_fix | ask_first
    incident_count = Column(Integer, nullable=False, default=1)
    success_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="learnings")
    service = relationship("Service", back_populates="learnings")


class Guardrail(Base):
    __tablename__ = "guardrails"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    service_id = Column(String, ForeignKey("services.id"), nullable=True)  # null = all services
    key = Column(String, nullable=False)
    label = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    kind = Column(String, nullable=False)  # toggle | locked
    value = Column(Boolean, nullable=False)

    user = relationship("User", back_populates="guardrails")
    service = relationship("Service", back_populates="guardrails")


