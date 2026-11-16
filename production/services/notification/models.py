from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from common import Base, utcnow


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("state IN ('QUEUED','SENT','EXPIRED')"),)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    recipient: Mapped[str] = mapped_column(String(254))
    request_hash: Mapped[str] = mapped_column(String(64))
    encrypted_payload: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claim_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))
