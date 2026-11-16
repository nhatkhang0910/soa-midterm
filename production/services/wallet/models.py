from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from common import Base, utcnow


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="wallet_balance_nonnegative"),
        CheckConstraint("reserved >= 0 AND reserved <= balance", name="wallet_reserved_valid"),
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    balance: Mapped[int] = mapped_column(BigInteger)
    reserved: Mapped[int] = mapped_column(BigInteger, default=0)


class Reservation(Base):
    __tablename__ = "wallet_reservations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="wallet_reservation_amount_positive"),
        CheckConstraint("state IN ('RESERVED', 'CAPTURED', 'CANCELLED')", name="wallet_reservation_state_valid"),
    )
    payment_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.user_id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(16))


class Debit(Base):
    __tablename__ = "wallet_debits"
    __table_args__ = (CheckConstraint("amount > 0", name="wallet_debit_amount_positive"),)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("wallet_reservations.payment_id"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.user_id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
