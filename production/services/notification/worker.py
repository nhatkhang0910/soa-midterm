import asyncio
import logging
import os
import random
import smtplib
import ssl
import uuid
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import or_, select, update
from common import Session, utcnow
from notification.app import decode_payload
from notification.models import Message

log = logging.getLogger("notification-worker")


def send_email(kind, recipient, payload):
    mail = EmailMessage()
    mail["From"] = os.environ["SMTP_FROM"]
    mail["To"] = recipient
    amount = f'{payload["amount"]:,}'.replace(",", ".") + " VND"
    if kind == "OTP":
        mail["Subject"] = "Mã OTP xác nhận thanh toán học phí"
        content = f'Mã OTP: {payload["otp"]}\nMã giao dịch: {payload["paymentId"]}\nSinh viên: {payload["studentName"]}\nSố tiền: {amount}\nMã chỉ có hiệu lực tối đa 5 phút. Không chia sẻ mã này.'
    else:
        mail["Subject"] = "Thanh toán học phí thành công"
        content = f'Thanh toán thành công.\nMã giao dịch: {payload["paymentId"]}\nSinh viên: {payload["studentName"]}\nSố tiền: {amount}'
    mail.set_content(content)
    host = os.environ["SMTP_HOST"]
    tls = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
    if not tls and host not in {"mailpit", "localhost", "127.0.0.1"}:
        raise ValueError("STARTTLS is required for external SMTP")
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
        smtp.ehlo()
        if tls:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if username := os.getenv("SMTP_USERNAME"):
            smtp.login(username, os.environ["SMTP_PASSWORD"])
        smtp.send_message(mail)


async def run_once():
    now = utcnow()
    async with Session.begin() as session:
        await session.execute(update(Message).where(Message.state == "QUEUED", Message.expires_at <= now).values(
            state="EXPIRED", encrypted_payload=None, claim_token=None, lease_until=None))
        job = await session.scalar(select(Message).where(
            Message.state == "QUEUED", Message.next_attempt_at <= now,
            or_(Message.lease_until.is_(None), Message.lease_until <= now),
        ).order_by(Message.next_attempt_at, Message.event_id).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return False
        token = str(uuid.uuid4())
        job.claim_token, job.lease_until = token, now + timedelta(seconds=30)
        event_id, kind, recipient, ciphertext, expires = job.event_id, job.kind, job.recipient, job.encrypted_payload, job.expires_at
        attempts = job.attempts
    try:
        if expires is not None and expires <= utcnow():
            state = "EXPIRED"
        else:
            payload = decode_payload(kind, ciphertext)
            await asyncio.to_thread(send_email, kind, recipient, payload)
            state = "SENT"
        values = dict(state=state, encrypted_payload=None, lease_until=None, claim_token=None, last_error=None)
    except Exception as exc:
        delay = min(30, 2 ** min(attempts, 5)) + random.random()
        values = dict(attempts=attempts + 1, next_attempt_at=utcnow() + timedelta(seconds=delay),
                      lease_until=None, claim_token=None, last_error=type(exc).__name__[:64])
        log.warning("email_retry eventId=%s attempt=%s errorType=%s", event_id, attempts + 1, type(exc).__name__)
    async with Session.begin() as session:
        await session.execute(update(Message).where(Message.event_id == event_id, Message.claim_token == token,
                                                     Message.state == "QUEUED").values(**values))
    return True


async def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            worked = await run_once()
        except Exception as exc:
            log.error("worker_retry errorType=%s", type(exc).__name__)
            worked = False
        if not worked:
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
