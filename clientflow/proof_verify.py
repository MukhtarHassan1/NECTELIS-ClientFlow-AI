"""Read-only, database-backed proof verification. No client-supplied pass/fail flags.

Uses persisted rows rather than returning prewritten success JSON. This verifies
our local synthetic integration path, NOT a real external GHL account.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from sqlalchemy import select, func
from . import db


def verify_persisted_event(client_key: str, source: str, event_id: str) -> dict | None:
    with db.session() as session:
        event = session.scalar(select(db.Event).where(
            db.Event.client_key == client_key,
            db.Event.source == source,
            db.Event.external_event_id == event_id,
        ))
        if event is None:
            return None
        contact = session.get(db.Contact, event.contact_id) if event.contact_id else None
        bookings = session.scalars(select(db.Booking).where(db.Booking.event_id == event.id)).all()
        timeline = session.scalars(select(db.Audit).where(db.Audit.event_id == event.id)
                                   .order_by(db.Audit.created_at, db.Audit.id)).all()
        event_count = session.scalar(select(func.count()).select_from(db.Event).where(
            db.Event.client_key == client_key, db.Event.source == source,
            db.Event.external_event_id == event_id))
        try:
            stored_result = json.loads(event.result_json or 'null')
        except (ValueError, TypeError):
            stored_result = None
        booked = event.status == 'booked'
        checks = {
            'unique_event_in_database': event_count == 1,
            'stored_result_matches_event': isinstance(stored_result, dict)
                and stored_result.get('status') == event.status
                and stored_result.get('event_id') == event_id,
            'contact_record_is_linked': contact is not None
                and contact.client_key == client_key
                and stored_result is not None
                and stored_result.get('contact_id') == contact.id,
            'decision_timeline_persisted': len(timeline) >= 3
                and any(step.step == 'receive' for step in timeline)
                and any(step.step == 'contact_upsert' for step in timeline),
            'booking_state_is_consistent': (
                len(bookings) == 1
                and bookings[0].id == event.appointment_id
                and bookings[0].contact_id == event.contact_id
                and stored_result is not None
                and stored_result.get('appointment_id') == bookings[0].id
            ) if booked else len(bookings) == 0 and event.appointment_id is None,
        }
        return {
            'mode': 'LOCAL_SQLITE_READBACK',
            'external_provider_called': False,
            'verified_at_utc': datetime.now(timezone.utc).isoformat(),
            'identity': {'client_key': client_key, 'source': source, 'event_id': event_id},
            'stored': {'event_row_id': event.id, 'status': event.status,
                       'contact_id': event.contact_id, 'appointment_id': event.appointment_id,
                       'audit_steps': len(timeline), 'booking_rows_for_event': len(bookings),
                       'first_name': contact.first_name if contact else None,
                       'service': contact.service if contact else None,
                       'slot_utc': bookings[0].start_at if bookings else None},
            'checks': checks,
            'passed': all(checks.values()),
            'scope': 'Independently queries SQLite for this event; does not validate a live GHL tenant.',
        }
