import hashlib
import json
import os
from typing import Literal
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends
from pydantic import AwareDatetime, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from common import DTO, ApiError, Session, create_app, require_payment, utcnow
from notification.models import Message

app = create_app("Notification")


class Payload(DTO):
    paymentId: UUID
    amount: int = Field(gt=0, strict=True)
    studentName: str = Field(min_length=1, max_length=160)
    otp: str | None = Field(default=None, pattern=r"^\d{6}$")


class MessageIn(DTO):
    kind: Literal["OTP", "PAYMENT_SUCCEEDED"]
    recipient: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@<>]+@[^\s@<>]+$")
    encryptedPayload: str = Field(min_length=1, max_length=8192)
    expiresAt: AwareDatetime | None = None

    @model_validator(mode="after")
    def expiration(self):
        if (self.kind == "OTP") != (self.expiresAt is not None):
            raise ValueError("OTP requires an expiration time")
        return self


def decode_payload(kind, token):
    try:
        payload = Payload.model_validate_json(Fernet(os.environ["EMAIL_ENCRYPTION_KEY"].encode()).decrypt(token.encode()))
        if (kind == "OTP") != (payload.otp is not None):
            raise ValueError("Invalid payload kind")
        return payload.model_dump(mode="json")
    except (InvalidToken, ValidationError, ValueError, TypeError):
        raise ApiError(422, "MESSAGE_INVALID", "Nội dung email không hợp lệ.") from None


class MessageResponse(DTO):
    eventId: str
    status: Literal["QUEUED", "SENT", "EXPIRED"]


@app.put("/internal/messages/{event_id}", response_model=MessageResponse, dependencies=[Depends(require_payment)])
async def enqueue(event_id: UUID, body: MessageIn):
    decode_payload(body.kind, body.encryptedPayload)
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    expired = body.expiresAt is not None and body.expiresAt <= utcnow()
    async with Session.begin() as session:
        await session.execute(insert(Message).values(
            event_id=str(event_id), kind=body.kind, recipient=body.recipient, request_hash=fingerprint,
            encrypted_payload=None if expired else body.encryptedPayload, expires_at=body.expiresAt,
            state="EXPIRED" if expired else "QUEUED", attempts=0, next_attempt_at=utcnow(),
        ).on_conflict_do_nothing(index_elements=[Message.event_id]))
        message = await session.scalar(select(Message).where(Message.event_id == str(event_id)).with_for_update())
        if message.request_hash != fingerprint:
            raise ApiError(409, "MESSAGE_CONFLICT", "Mã sự kiện đã gắn với yêu cầu khác.")
        if message.state == "QUEUED" and expired:
            message.state, message.encrypted_payload = "EXPIRED", None
        result = {"eventId": message.event_id, "status": message.state}
    return result
