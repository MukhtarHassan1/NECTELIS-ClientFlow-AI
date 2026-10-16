from __future__ import annotations
import json
import hashlib
import os
import threading
import smtplib
import time
from datetime import datetime, timedelta
from datetime import timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError
from . import db as store
from .ai import qualify, optional_ollama_advisory
from .mailer import send_test_mailpit
from .config import profile_for, dry_run, demo_mode
from .schemas import LeadEvent

_lock = threading.RLock()  # single-process demo safeguard; UNIQUE constraints back it at DB level.

class ReplayConflict(Exception):
    """The same source event ID was already used for a different request body."""


class ConnectorError(Exception):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f'HTTP {status}')


def safe_detail(text: str) -> str:
    # No raw inbound customer message / email / phone in the audit.
    return text[:450]


def _provider_step(simulate: dict[str, str], key: str, cfg, session, eid: str):
    """Deterministic mock fault injection; avoids pretending any remote API was called."""
    value = simulate.get(key, '200')
    codes = [int(p) for p in value.split(',') if p.strip().isdigit()]
    codes = codes or [200]
    attempts = 0
    for index in range(cfg.reliability.max_transient_attempts):
        attempts += 1
        status = codes[min(index, len(codes) - 1)]
        if status < 400:
            store.audit(session, eid, key, 'ok', 'MOCK provider accepted request', attempts)
            return attempts
        if status in (429, 500, 502, 503, 504):
            store.audit(session, eid, key, 'retry', f'MOCK HTTP {status}; bounded attempt {attempts}', attempts)
            # Virtual/demo retry delay, not an actual upstream Retry-After header.
            if attempts < cfg.reliability.max_transient_attempts:
                time.sleep(.005 * (2 ** index))
                continue
        store.audit(session, eid, key, 'failed', f'MOCK HTTP {status}; stopped', attempts)
        raise ConnectorError(status)
    raise ConnectorError(503)


def _get_contact(session, event: LeadEvent):
    lead = event.lead
    clauses = []
    if lead.email: clauses.append(store.Contact.email == lead.email)
    if lead.phone: clauses.append(store.Contact.phone == lead.phone)
    matches = session.scalars(select(store.Contact).where(store.Contact.client_key == event.client_key,
                                                        or_(*clauses))).all()
    if len(matches) > 1:
        raise ValueError('Contact identity conflict: email/phone resolve to different contacts')
    return matches[0] if matches else None


def _slot_key(event: LeadEvent, cfg):
    if not event.requested_slot:
        return None, 'No slot requested'
    slot = event.requested_slot
    if slot.astimezone(timezone.utc) <= datetime.now(timezone.utc):
        return None, 'Requested slot is in the past'
    local = slot.astimezone(ZoneInfo(cfg.timezone))
    if local.hour < cfg.calendar.business_hours_start or (local.hour * 60 + local.minute + cfg.calendar.duration_minutes > cfg.calendar.business_hours_end * 60):
        return None, 'Outside configured business hours'
    # No weekends in home services demo; scheduled mock availability is intentionally simplistic.
    if cfg.industry == 'home_services' and local.weekday() >= 5:
        return None, 'Weekend is unavailable in this profile'
    return slot.astimezone(timezone.utc).isoformat(timespec='seconds'), None


def _dry_plan(event: LeadEvent, cfg):
    q = qualify(event.lead, cfg)
    slot, issue = _slot_key(event, cfg)
    return {'event_id': event.event_id, 'status': 'dry_run', 'connector_mode': 'MOCK / SYNTHETIC',
            'writes': 0, 'would': {'contact': 'lookup then upsert', 'qualification': q.model_dump(),
                                  'booking': 'attempt slot check' if slot and q.label == 'qualified' else f'not requested / review ({issue or q.reason})',
                                  'notifications': 'log-only; no external dispatch'},
            'limitations': ['No remote GHL account accessed', 'Dry-run performs no database or provider writes']}


def process(event: LeadEvent) -> dict:
    if demo_mode() != 'mock':
        raise RuntimeError('This verified release only enables DEMO_MODE=mock; live connector is gated')
    cfg = profile_for(event.client_key)
    if dry_run():
        return _dry_plan(event, cfg)

    fingerprint = hashlib.sha256(json.dumps(event.model_dump(mode='json', exclude={'received_at'}),
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with _lock:
        with store.session() as s:
            previous = s.scalar(select(store.Event).where(store.Event.client_key == event.client_key,
                store.Event.source == event.source, store.Event.external_event_id == event.event_id))
            if previous:
                if not previous.request_fingerprint or previous.request_fingerprint != fingerprint:
                    raise ReplayConflict('Event ID was already used with different or legacy-unverifiable content. Send a new event ID.')
                if previous.result_json:
                    past = json.loads(previous.result_json)
                    return {**past, 'duplicate_event': True, 'replayed': True}
                return {'event_id': event.event_id, 'status': previous.status,
                        'duplicate_event': True, 'message': 'Event already accepted; do not replay side effects'}

            eid = store.uid('evt')
            s.add(store.Event(id=eid, client_key=event.client_key, source=event.source,
                              external_event_id=event.event_id, request_fingerprint=fingerprint, status='processing'))
            s.flush()
            aid = store.audit(s, eid, 'receive', 'accepted', 'Schema validated; synthetic lead received')
            q = qualify(event.lead, cfg)
            store.audit(s, eid, 'qualification', q.label, q.reason)
            advisory = optional_ollama_advisory(event.lead)
            if advisory.get('enabled'):
                store.audit(s, eid, 'local_ai_advisory', advisory['status'], 'Local inference advisory; cannot book')

            result = {
                'event_id': event.event_id, 'audit_id': aid, 'connector_mode': 'MOCK / SYNTHETIC',
                'duplicate_event': False, 'qualification': q.model_dump(), 'ai_advisory': advisory,
                'contact_id': None, 'crm_action': 'none', 'appointment_id': None,
                'notification_status': 'not_requested', 'follow_up_status': 'none',
                'opportunity_stage': cfg.pipeline.new, 'status': 'processing'
            }
            e = s.get(store.Event, eid)
            try:
                _provider_step(event.simulate, 'crm', cfg, s, eid)
                match = _get_contact(s, event)
                if match:
                    match.first_name = event.lead.first_name
                    match.email = event.lead.email or match.email
                    match.phone = event.lead.phone or match.phone
                    match.service = event.lead.service
                    contact = match
                    result['crm_action'] = 'updated'
                else:
                    contact = store.Contact(id=store.uid('con'), client_key=event.client_key,
                        first_name=event.lead.first_name, email=event.lead.email,
                        phone=event.lead.phone, service=event.lead.service, stage=cfg.pipeline.new)
                    s.add(contact)
                    result['crm_action'] = 'created'
                s.flush()
                result['contact_id'] = contact.id
                e.contact_id = contact.id
                store.audit(s, eid, 'contact_upsert', result['crm_action'], f'CRM mock contact ID {contact.id}')
                stage = cfg.pipeline.qualified if q.label == 'qualified' else cfg.pipeline.review
                slot, issue = _slot_key(event, cfg)
                if q.label != 'qualified':
                    result['status'] = 'needs_review'
                elif not event.requested_slot:
                    result['status'] = 'qualified_no_booking_requested'
                elif issue:
                    result['status'] = 'slot_unavailable'
                    store.audit(s, eid, 'availability', 'unavailable', issue)
                else:
                    _provider_step(event.simulate, 'calendar', cfg, s, eid)
                    proposed_start = datetime.fromisoformat(slot)
                    proposed_end = proposed_start + timedelta(minutes=cfg.calendar.duration_minutes)
                    overlapping = False
                    for prior in s.scalars(select(store.Booking).where(store.Booking.client_key == event.client_key)).all():
                        old_start = datetime.fromisoformat(prior.start_at)
                        old_end = old_start + timedelta(minutes=prior.duration_minutes)
                        if proposed_start < old_end and old_start < proposed_end:
                            overlapping = True
                            break
                    if overlapping:
                        store.audit(s, eid, 'booking', 'conflict', 'Slot occupied; no second appointment created')
                        result['status'] = 'slot_unavailable'
                    else:
                        booking = store.Booking(id=store.uid('apt'), client_key=event.client_key,
                            contact_id=contact.id, event_id=eid, start_at=slot,
                            duration_minutes=cfg.calendar.duration_minutes)
                        s.add(booking)
                        s.flush()
                        result['appointment_id'] = booking.id
                        e.appointment_id = booking.id
                        stage = cfg.pipeline.booked
                        result['status'] = 'booked'
                        if event.simulate.get('calendar') == 'timeout_after_create':
                            store.audit(s, eid, 'booking', 'ambiguous_timeout',
                                'MOCK transport timed out after write; reconcile via event ID')
                            reconciled = s.scalar(select(store.Booking).where(store.Booking.event_id == eid))
                            if not reconciled:
                                raise ConnectorError(504)
                            store.audit(s, eid, 'booking', 'reconciled',
                                'Existing booking located by durable event ID; no second create')
                        store.audit(s, eid, 'booking', 'booked', f'Unique UTC slot {slot}; ID {booking.id}')
                # A fresh inquiry with no confirmed new booking must not accidentally
                # erase a prior *future* booked state for the same mock contact.
                if stage == cfg.pipeline.qualified and contact.stage == cfg.pipeline.booked:
                    future_booked = any(
                        datetime.fromisoformat(b.start_at) > datetime.now(timezone.utc)
                        for b in s.scalars(select(store.Booking).where(
                            store.Booking.client_key == event.client_key,
                            store.Booking.contact_id == contact.id)).all()
                    )
                    if future_booked:
                        stage = cfg.pipeline.booked
                        store.audit(s, eid, 'pipeline', 'preserved',
                            'Existing confirmed future booking preserved for this contact')
                contact.stage = stage
                result['opportunity_stage'] = stage
                store.audit(s, eid, 'pipeline', 'updated', f'MOCK stage: {stage}')
                s.flush()

                # Follow-up queue is an internal action item, not an outbound SMS/email.
                follow_type = 'confirmation_draft' if result['status'] == 'booked' else 'manual_follow_up'
                follow_reason = 'Booking confirmation for staff review' if result['status'] == 'booked' else result['status']
                s.add(store.FollowUp(id=store.uid('fu'), event_id=eid, type=follow_type,
                                     reason=follow_reason, status='queued_for_human_review'))
                result['follow_up_status'] = 'queued_for_human_review'
                store.audit(s, eid, 'follow_up', 'queued', 'Internal review queue only; external sending disabled')
                if cfg.notifications.internal_enabled:
                    try:
                        _provider_step(event.simulate, 'notification', cfg, s, eid)
                        address = (cfg.notifications.test_recipient_allowlist or ['team.demo@example.com'])[0]
                        delivery = send_test_mailpit(address,
                            f'{cfg.company_name}: synthetic lead event {event.event_id} -> {result["status"]}')
                        s.add(store.Notification(id=store.uid('ntf'), event_id=eid, audience='team',
                            channel='mailpit_capture' if delivery=='mailpit_test_captured' else 'local_test_log',
                            status=delivery, text=f'{cfg.company_name}: lead {event.event_id} -> {result["status"]}'))
                        result['notification_status'] = delivery
                    except (ConnectorError, OSError, ValueError, smtplib.SMTPException) as exc:
                        error_class = f'MOCK HTTP {exc.status}' if isinstance(exc, ConnectorError) else type(exc).__name__
                        s.add(store.Notification(id=store.uid('ntf'), event_id=eid, audience='team',
                            channel='local_test_log', status='failed', text=f'Test notification failure {error_class}'))
                        result['notification_status'] = 'failed_logged'
                        store.audit(s, eid, 'notification', 'failed',
                                    f'Internal test-only notification {error_class}; booking retained')
                # No external transport is connected. Consent does not override test-only policy.
                if cfg.notifications.lead_enabled:
                    store.audit(s, eid, 'external_communication', 'suppressed',
                                'Outbound disabled; consent check retained for future authorized adapter')
            except ConnectorError as exc:
                result['status'] = 'connector_failed'
                result['error'] = f'Mock provider HTTP {exc.status}; manual review required'
                result['retryable'] = exc.status in (429, 500, 502, 503, 504)
                store.audit(s, eid, 'error_policy', 'isolated', f'HTTP {exc.status}; no blind replay')
                if e.contact_id and not e.appointment_id:
                    previous_contact = s.get(store.Contact, e.contact_id)
                    if previous_contact:
                        previous_contact.stage = cfg.pipeline.review
                        result['opportunity_stage'] = cfg.pipeline.review
                # Even a CRM failure BEFORE contact creation must surface a human action.
                s.add(store.FollowUp(id=store.uid('fu'), event_id=eid,
                     type='manual_follow_up',reason='Connector failed during processing',
                     status='queued_for_human_review'))
                result['follow_up_status']='queued_for_human_review'
                store.audit(s, eid, 'follow_up', 'queued',
                            'Connector failure isolated for operator review; no blind replay')
            except ValueError as exc:
                result['status'] = 'needs_review'
                result['error'] = safe_detail(str(exc))
                store.audit(s, eid, 'identity', 'conflict', 'Ambiguous match; manual review required')
            e.status = result['status']
            e.result_json = json.dumps(result)
            s.commit()
            return result


def list_state(limit: int = 30) -> dict:
    with store.session() as s:
        events = s.scalars(select(store.Event).order_by(store.Event.created_at.desc()).limit(limit)).all()
        bookings = s.scalars(select(store.Booking).order_by(store.Booking.start_at.desc()).limit(limit)).all()
        contacts = s.scalars(select(store.Contact).order_by(store.Contact.updated_at.desc()).limit(limit)).all()
        notifications = s.scalars(select(store.Notification).limit(limit)).all()
        followups = s.scalars(select(store.FollowUp).limit(limit)).all()
        counts = {key: s.scalar(select(func.count()).select_from(model)) for key, model in {
            'contacts':store.Contact, 'bookings':store.Booking,'events':store.Event,
            'notifications':store.Notification,'followups':store.FollowUp, 'rejections':store.Rejection}.items()}
        return {
            'stats': counts,
            'events': [{'event_id': x.external_event_id,'source':x.source,'client_key':x.client_key,
                        'status': x.status,'id': x.id} for x in events],
            'contacts': [{'id':x.id,'client_key':x.client_key,'first_name':x.first_name,
                          'email_masked': ('***@'+x.email.split('@')[-1]) if x.email else None,
                          'stage':x.stage,'service':x.service} for x in contacts],
            'bookings': [{'id':x.id,'contact_id':x.contact_id,'start_at':x.start_at,
                          'client_key':x.client_key} for x in bookings],
            'notifications': [{'event_id':x.event_id,'status':x.status,'channel':x.channel} for x in notifications],
            'followups': [{'event_id':x.event_id,'type':x.type,'status':x.status} for x in followups],
            'rejections': [{'event_id':x.event_id,'reason':x.reason} for x in s.scalars(select(store.Rejection).order_by(store.Rejection.created_at.desc()).limit(limit)).all()]
        }


def event_trace(external_event_id: str, client_key: str | None = None, source: str | None = None) -> dict | None:
    with store.session() as s:
        stmt = select(store.Event).where(store.Event.external_event_id == external_event_id)
        if client_key:
            stmt = stmt.where(store.Event.client_key == client_key)
        if source:
            stmt = stmt.where(store.Event.source == source)
        matching = s.scalars(stmt.limit(2)).all()
        if not matching: return None
        if len(matching) > 1:
            raise ValueError('Ambiguous event ID across profiles or sources. Use the fully scoped audit route.')
        event = matching[0]
        lines = s.scalars(select(store.Audit).where(store.Audit.event_id == event.id)
                          .order_by(store.Audit.created_at, store.Audit.id)).all()
        return {'event_id':external_event_id, 'client_key':event.client_key, 'source':event.source, 'status':event.status,
                'result':json.loads(event.result_json) if event.result_json else None,
                'timeline':[{'step':a.step,'outcome':a.outcome,'detail':a.detail,
                             'attempts':a.attempts} for a in lines]}
