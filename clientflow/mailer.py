"""Safely optional Mailpit-only internal email capture.

This is *not* a general SMTP adapter and refuses arbitrary remote destinations.
"""
from __future__ import annotations
import os
import smtplib
from email.message import EmailMessage

LOCAL_ONLY = {'127.0.0.1', 'localhost', 'mailpit'}


def send_test_mailpit(recipient: str, body: str) -> str:
    if os.getenv('TEST_MAILPIT_ENABLED','false').lower()!='true':
        return 'logged_only'
    host=os.getenv('TEST_MAILPIT_HOST','localhost')
    if host not in LOCAL_ONLY:
        raise ValueError('TEST_MAILPIT_HOST must be localhost or an internal Mailpit container')
    if not recipient.endswith('@example.com'):
        raise ValueError('Only synthetic example.com recipient is permitted')
    msg=EmailMessage()
    msg['Subject']='[SYNTHETIC ONLY] NECTELIS ClientFlow internal lead notice'
    msg['From']='proof@nectelis.example.com'
    msg['To']=recipient
    msg.set_content(body[:300])
    # Mailpit captures the message. No external internet delivery is permitted by design.
    with smtplib.SMTP(host,1025,timeout=4) as smtp:
        smtp.send_message(msg)
    return 'mailpit_test_captured'
