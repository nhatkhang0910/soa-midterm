from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from common import Base, utcnow


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("payer_id", "idempotency_key", name="uq_payment_idempotency"),
        CheckConstraint("amount > 0", name="ck_payment_amount"),
        CheckConstraint("status IN ('PENDING_OTP','PROCESSING','SUCCEEDED','FAILED','EXPIRED')", name="ck_payment_status"),
        CheckConstraint("saga_state IS NULL OR saga_state IN ('PREPARING','COMMITTING','ABORTING')", name="ck_payment_saga"),
        Index("ix_payment_history", "payer_id", "created_at", "id"),
        Index("ix_payment_work", "status", "next_attempt_at"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    payer_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    invoice_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(BigInteger)
    payer: Mapped[dict] = mapped_column(JSONB)
    student: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="PENDING_OTP")
    otp_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    saga_state: Mapped[str | None] = mapped_column(String(16))
    checkpoint: Mapped[int] = mapped_column(Integer, default=0)
    prepare_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claim_token: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(80))


class Challenge(Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_otp_attempts"),
        CheckConstraint("status IN ('ACTIVE','USED','EXPIRED','LOCKED')", name="ck_otp_status"),
        Index("uq_active_otp_hmac", "code_hmac", unique=True, postgresql_where=text("status = 'ACTIVE'")),
    )
    payment_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("payments.id"), primary_key=True)
    code_hmac: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE")


class Outbox(Base):
    __tablename__ = "payment_outbox"
    __table_args__ = (
        UniqueConstraint("payment_id", "kind", name="uq_payment_event_kind"),
        CheckConstraint("kind IN ('OTP','PAYMENT_SUCCEEDED')", name="ck_outbox_kind"),
        CheckConstraint("status IN ('PENDING','DELIVERED','EXPIRED')", name="ck_outbox_status"),
        Index("ix_outbox_work", "status", "next_attempt_at"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    payment_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("payments.id"))
    kind: Mapped[str] = mapped_column(String(24))
    recipient: Mapped[str] = mapped_column(String(320))
    encrypted_payload: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="PENDING")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claim_token: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(80))
