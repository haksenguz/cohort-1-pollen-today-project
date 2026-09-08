"""SQLModel tables — 1:1 with docs/erd/allergy_ai.dmm."""

from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class UserAllergy(SQLModel, table=True):
    __tablename__ = "user_allergies"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    allergen: str = Field(max_length=30)
    severity: str = Field(max_length=10)
    created_at: datetime = Field(default_factory=_now)


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    status: str = Field(default="ACTIVE", max_length=12)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)
    role: str = Field(max_length=10)
    content: str
    created_at: datetime = Field(default_factory=_now)


class SymptomEvent(SQLModel, table=True):
    __tablename__ = "symptom_events"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    conversation_id: int | None = Field(default=None, foreign_key="conversations.id")
    symptoms: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    severity: int | None = None
    duration: str | None = Field(default=None, max_length=50)
    possible_trigger: str | None = Field(default=None, max_length=50)
    breathing_difficulty: bool = False
    airway_swelling: bool = False
    created_at: datetime = Field(default_factory=_now)


class TriageResult(SQLModel, table=True):
    __tablename__ = "triage_results"
    id: int | None = Field(default=None, primary_key=True)
    symptom_event_id: int = Field(foreign_key="symptom_events.id", index=True)
    risk_level: str = Field(max_length=12)
    recommendation: str | None = None
    rule_version: str | None = Field(default=None, max_length=20)
    created_at: datetime = Field(default_factory=_now)


class EnvironmentSnapshot(SQLModel, table=True):
    __tablename__ = "environment_snapshots"
    id: int | None = Field(default=None, primary_key=True)
    latitude: float
    longitude: float
    tree_pollen: str | None = Field(default=None, max_length=10)
    grass_pollen: str | None = Field(default=None, max_length=10)
    weed_pollen: str | None = Field(default=None, max_length=10)
    pm25: float | None = None
    pm10: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    risk_level: str | None = Field(default=None, max_length=12)
    captured_at: datetime = Field(default_factory=_now)


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    environment_snapshot_id: int | None = Field(
        default=None, foreign_key="environment_snapshots.id"
    )
    risk_level: str = Field(max_length=12)
    alert_type: str = Field(max_length=15)
    message: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=_now)


class HospitalSearch(SQLModel, table=True):
    __tablename__ = "hospital_searches"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    latitude: float
    longitude: float
    specialty: str | None = Field(default=None, max_length=40)
    created_at: datetime = Field(default_factory=_now)


class HospitalResult(SQLModel, table=True):
    __tablename__ = "hospital_results"
    id: int | None = Field(default=None, primary_key=True)
    hospital_search_id: int = Field(foreign_key="hospital_searches.id", index=True)
    name: str = Field(max_length=200)
    address: str | None = Field(default=None, max_length=300)
    distance_m: int | None = None
    specialty: str | None = Field(default=None, max_length=40)
    is_open: bool | None = None
    phone: str | None = Field(default=None, max_length=40)
    place_id: str | None = Field(default=None, max_length=120)
    rank: int | None = None
    created_at: datetime = Field(default_factory=_now)
