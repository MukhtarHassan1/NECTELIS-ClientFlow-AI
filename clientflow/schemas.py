from __future__ import annotations
from datetime import datetime
from typing import Literal
import re
from pydantic import BaseModel, Field, field_validator, model_validator

class Lead(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=35)
    service: str = Field(min_length=1, max_length=120)
    postal_area: str | None = Field(default=None, max_length=100)
    message: str = Field(default='', max_length=1200)
    consent_to_contact: bool = False

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        if value is None or not value.strip(): return None
        value = value.strip().lower()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value):
            raise ValueError('Email must have a valid address format')
        return value

    @field_validator('phone')
    @classmethod
    def phone_valid(cls, value):
        if value is None or not value.strip(): return None
        cleaned = re.sub(r'[\s().-]', '', value)
        if not re.fullmatch(r'\+[1-9]\d{7,14}', cleaned):
            raise ValueError('Phone must be E.164 (for example +15550100123)')
        return cleaned

    @field_validator('first_name', 'service')
    @classmethod
    def stripped(cls, value):
        return value.strip()

    @model_validator(mode='after')
    def has_identity(self):
        if not self.email and not self.phone:
            raise ValueError('At least an email or a phone is required')
        return self

class LeadEvent(BaseModel):
    event_id: str = Field(min_length=3, max_length=120, pattern=r'^[a-zA-Z0-9._:-]+$')
    source: Literal['website_form', 'webhook', 'demo_ui', 'n8n', 'vapi', 'twilio'] = 'website_form'
    client_key: str
    received_at: datetime | None = None
    lead: Lead
    requested_slot: datetime | None = None
    # Fault injection exists only in mock mode and is exposed via the demo API.
    simulate: dict[str, str] = Field(default_factory=dict)

    @field_validator('requested_slot')
    @classmethod
    def aware_slot(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('requested_slot must include a timezone offset')
        return value

class Qualification(BaseModel):
    label: Literal['qualified', 'review']
    confidence: float
    priority: Literal['standard', 'high']
    reason: str
    method: str = 'deterministic_rules (AI-ready interface)'
