from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)

class CalendarConfig(BaseModel):
    duration_minutes: int = Field(ge=15, le=180)
    business_hours_start: int = Field(ge=0, le=23)
    business_hours_end: int = Field(ge=1, le=24)

class QualificationConfig(BaseModel):
    supported_services: list[str]
    urgent_words: list[str] = []
    min_confidence_for_auto_booking: float = Field(default=.65, ge=0, le=1)

class PipelineConfig(BaseModel):
    new: str
    qualified: str
    booked: str
    review: str

class NotificationConfig(BaseModel):
    internal_enabled: bool = True
    lead_enabled: bool = True
    external_enabled: bool = False
    test_recipient_allowlist: list[str] = []

class ReliabilityConfig(BaseModel):
    max_transient_attempts: int = Field(default=3, ge=1, le=6)
    idempotency_window_hours: int = 72

class ClientProfile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    client_key: str
    company_name: str
    industry: str
    timezone: str
    crm_adapter: str
    calendar_adapter: str
    calendar: CalendarConfig
    pipeline: PipelineConfig
    qualification: QualificationConfig
    notifications: NotificationConfig
    reliability: ReliabilityConfig

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, v):
        ZoneInfo(v)
        return v

@lru_cache(maxsize=1)
def profiles() -> dict[str, ClientProfile]:
    found = {}
    for p in sorted((ROOT / "config").glob("*.yaml")):
        item = ClientProfile.model_validate(yaml.safe_load(p.read_text()))
        if item.client_key in found:
            raise ValueError(f"Duplicate client_key: {item.client_key}")
        found[item.client_key] = item
    return found


def profile_for(key: str) -> ClientProfile:
    options = profiles()
    if key not in options:
        raise KeyError(f"Unknown client profile: {key}")
    return options[key]


def demo_mode() -> str:
    # This release deliberately does NOT permit write access to a live provider.
    return os.getenv("DEMO_MODE", "mock")


def dry_run() -> bool:
    return os.getenv("DRY_RUN", "false").lower() == "true"
