from copy import deepcopy
from unittest.mock import patch
from clientflow.mailer import send_test_mailpit
import pytest


def test_mailpit_disabled_does_not_send(monkeypatch):
    monkeypatch.setenv('TEST_MAILPIT_ENABLED','false')
    with patch('smtplib.SMTP') as s:
        assert send_test_mailpit('team.demo@example.com','Synthetic notice')=='logged_only'
        s.assert_not_called()


def test_mailpit_cannot_use_external_smtp(monkeypatch):
    monkeypatch.setenv('TEST_MAILPIT_ENABLED','true')
    monkeypatch.setenv('TEST_MAILPIT_HOST','smtp.real-provider.com')
    with pytest.raises(ValueError,match='must be localhost'):
        send_test_mailpit('team.demo@example.com','Synthetic notice')


def test_test_mailpit_capture_contract(client,sample,monkeypatch):
    monkeypatch.setenv('TEST_MAILPIT_ENABLED','true')
    monkeypatch.setenv('TEST_MAILPIT_HOST','localhost')
    with patch('smtplib.SMTP') as smtp:
        out=client.post('/api/v1/leads',json=sample).json()
        assert out['status']=='booked'
        assert out['notification_status']=='mailpit_test_captured'
        smtp.assert_called_once_with('localhost',1025,timeout=4)
    state=client.get('/api/v1/state').json()
    assert state['notifications'][0]['channel']=='mailpit_capture'
