"""Durable single-checkpoint Saga and outbox workers; no HTTP inside transactions."""
import asyncio
import logging
import random
from datetime import timedelta
from uuid import uuid4

import httpx
from sqlalchemy import and_, or_, select, update

from common import Session, utcnow
from payment.app import expire_pending
from payment.gateway import RemoteFailure, request
from payment.models import Outbox, Payment
from payment.security import encrypt_payload

logger = logging.getLogger("payment.worker")


def retry_at(attempt):
    return utcnow() + timedelta(seconds=min(30, 2 ** min(attempt, 5)) + random.random())


async def claim(model):
    now = utcnow()
    due = model.next_attempt_at <= now
    if model is Payment:
        due = or_(due, and_(Payment.saga_state == "PREPARING", Payment.prepare_deadline <= now))
    async with Session.begin() as session:
        row = await session.scalar(select(model).where(
            model.status == ("PROCESSING" if model is Payment else "PENDING"),
            due,
            or_(model.lease_until.is_(None), model.lease_until <= now),
        ).order_by(model.next_attempt_at, model.id).limit(1).with_for_update(skip_locked=True))
        if row:
            row.claim_token = str(uuid4())
            row.lease_until = now + timedelta(seconds=30)
        return row


async def fenced(session, model, row):
    return await session.scalar(select(model).where(model.id == row.id,
                    model.claim_token == row.claim_token, model.lease_until > utcnow()).with_for_update())


def release(row):
    row.claim_token = None
    row.lease_until = None
    row.next_attempt_at = utcnow()
    row.attempt = 0
    row.last_error = None


async def saga_error(row, error):
    async with Session.begin() as session:
        current = await fenced(session, Payment, row)
        if not current:
            return
        current.claim_token = None
        current.lease_until = None
        current.attempt += 1
        current.last_error = error.code
        if current.saga_state == "PREPARING" and (error.business or current.prepare_deadline <= utcnow()):
            current.saga_state = "ABORTING"
            current.checkpoint = 0
            current.failure_code = error.code if error.business else "PREPARE_TIMEOUT"
            current.next_attempt_at = utcnow()
        else:
            current.next_attempt_at = retry_at(current.attempt - 1)
        logger.warning("saga_retry paymentId=%s state=%s code=%s attempt=%s", current.id,
                       current.saga_state, current.last_error, current.attempt)


async def saga_once(client: httpx.AsyncClient | None = None) -> bool:
    """Claim and perform one durable Saga checkpoint; returns whether work was claimed."""
    if client is None:
        async with httpx.AsyncClient(timeout=5.0) as owned:
            return await saga_once(owned)
    row = await claim(Payment)
    if not row:
        return False
    if row.saga_state == "PREPARING" and row.prepare_deadline <= utcnow():
        await saga_error(row, RemoteFailure("PREPARE_TIMEOUT", business=True))
        return True
    target = None
    if row.saga_state == "PREPARING":
        if row.checkpoint == 0:
            target = ("tuition", {"invoiceId": row.invoice_id, "amount": row.amount, "state": "RESERVED"})
        elif row.checkpoint == 1:
            target = ("wallet", {"userId": row.payer_id, "amount": row.amount, "state": "RESERVED"})
    elif row.saga_state == "COMMITTING":
        if row.checkpoint == 0:
            target = ("wallet", {"userId": row.payer_id, "amount": row.amount, "state": "CAPTURED"})
        elif row.checkpoint == 1:
            target = ("tuition", {"invoiceId": row.invoice_id, "amount": row.amount, "state": "PAID"})
    elif row.saga_state == "ABORTING":
        if row.checkpoint == 0:
            target = ("wallet", {"userId": row.payer_id, "amount": row.amount, "state": "CANCELLED"})
        elif row.checkpoint == 1:
            target = ("tuition", {"invoiceId": row.invoice_id, "amount": row.amount, "state": "CANCELLED"})
    try:
        if target:
            result = await request(client, target[0], "PUT", f"/internal/reservations/{row.id}", target[1])
            if result != {"paymentId": row.id, **target[1]}:
                raise RemoteFailure("RESERVATION_ACK_MISMATCH")
        elif row.checkpoint != 2:
            raise RemoteFailure("SAGA_INVARIANT")
        async with Session.begin() as session:
            current = await fenced(session, Payment, row)
            if not current:
                return True
            if target:
                current.checkpoint += 1
            elif current.saga_state == "PREPARING":
                if current.prepare_deadline <= utcnow():
                    current.saga_state = "ABORTING"
                    current.failure_code = "PREPARE_TIMEOUT"
                else:
                    current.saga_state = "COMMITTING"
                current.checkpoint = 0
            elif current.saga_state == "ABORTING":
                current.status = "FAILED"
            elif current.saga_state == "COMMITTING":
                current.status = "SUCCEEDED"
                session.add(Outbox(id=str(uuid4()), payment_id=current.id, kind="PAYMENT_SUCCEEDED",
                    recipient=current.payer["email"], encrypted_payload=encrypt_payload({"paymentId": current.id,
                        "amount": current.amount, "studentName": current.student["fullName"]})))
            release(current)
    except RemoteFailure as exc:
        await saga_error(row, exc)
    return True


async def outbox_once(client: httpx.AsyncClient | None = None) -> bool:
    """Claim one email event; erase ciphertext only after durable ACK or expiry."""
    if client is None:
        async with httpx.AsyncClient(timeout=5.0) as owned:
            return await outbox_once(owned)
    row = await claim(Outbox)
    if not row:
        return False
    expired = row.expires_at is not None and row.expires_at <= utcnow()
    error = None
    if not expired:
        try:
            result = await request(client, "notification", "PUT", f"/internal/messages/{row.id}", {
                "kind": row.kind, "recipient": row.recipient, "encryptedPayload": row.encrypted_payload,
                "expiresAt": row.expires_at.isoformat() if row.expires_at else None})
            if result.get("eventId") != row.id or result.get("status") not in ("QUEUED", "SENT", "EXPIRED"):
                raise RemoteFailure("NOTIFICATION_ACK_MISMATCH")
            expired = result["status"] == "EXPIRED"
        except RemoteFailure as exc:
            error = exc
    async with Session.begin() as session:
        current = await fenced(session, Outbox, row)
        if not current:
            return True
        if current.expires_at and current.expires_at <= utcnow():
            expired = True
            error = None
        current.claim_token = None
        current.lease_until = None
        if error:
            current.attempt += 1
            current.last_error = error.code
            current.next_attempt_at = retry_at(current.attempt - 1)
            logger.warning("outbox_retry eventId=%s code=%s attempt=%s", current.id, current.last_error, current.attempt)
        else:
            current.status = "EXPIRED" if expired else "DELIVERED"
            current.encrypted_payload = None
            current.last_error = None
    return True


async def cleanup_once():
    async with Session.begin() as session:
        now = utcnow()
        await expire_pending(session, now)
        await session.execute(update(Outbox).where(Outbox.status == "PENDING", Outbox.expires_at <= now).values(
            status="EXPIRED", encrypted_payload=None, claim_token=None, lease_until=None))


async def run_once(client: httpx.AsyncClient | None = None) -> bool:
    """Apply OTP expiry, one Saga checkpoint, then one outbox event."""
    await cleanup_once()
    saga_work = await saga_once(client)
    outbox_work = await outbox_once(client)
    return saga_work or outbox_work


async def main():
    logging.basicConfig(level=logging.INFO)
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                busy = await run_once(client)
            except Exception as exc:
                logger.error("worker_failed type=%s", type(exc).__name__)
                busy = False
            if not busy:
                await asyncio.sleep(0.5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
