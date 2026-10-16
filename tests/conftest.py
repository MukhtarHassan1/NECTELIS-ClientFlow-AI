from __future__ import annotations
import os
import pytest
from fastapi.testclient import TestClient
from clientflow import db as store
from clientflow.api import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path}/test.sqlite3')
    monkeypatch.setenv('DEMO_MODE','mock')
    monkeypatch.setenv('DRY_RUN','false')
    monkeypatch.delenv('OLLAMA_MODEL',raising=False)
    monkeypatch.delenv('ADMIN_API_KEY',raising=False)
    monkeypatch.delenv('WEBHOOK_API_KEY',raising=False)
    with TestClient(app) as api:
        yield api

@pytest.fixture
def sample():
    return {'event_id':'cf-test-0001','source':'website_form','client_key':'home-services-demo',
        'lead':{'first_name':'Alex','email':'alex@example.com','phone':'+15550101001',
                'service':'plumbing','message':'Urgent leaking pipe','consent_to_contact':True},
        'requested_slot':'2030-10-16T14:00:00-04:00'}
