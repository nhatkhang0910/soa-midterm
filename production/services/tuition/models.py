from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from common import Base


class Student(Base):
    __tablename__ = "students"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    mssv: Mapped[str] = mapped_column(String(20), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("amount > 0", name="tuition_invoice_amount_positive"),
        CheckConstraint("status IN ('UNPAID', 'RESERVED', 'PAID')", name="tuition_invoice_status_valid"),
        CheckConstraint("(status = 'UNPAID' AND reserved_payment_id IS NULL AND paid_payment_id IS NULL) OR (status = 'RESERVED' AND reserved_payment_id IS NOT NULL AND paid_payment_id IS NULL) OR (status = 'PAID' AND reserved_payment_id IS NULL)", name="tuition_invoice_owner_valid"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), unique=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16))
    reserved_payment_id: Mapped[UUID | None] = mapped_column(unique=True)
    paid_payment_id: Mapped[UUID | None] = mapped_column(unique=True)


class Reservation(Base):
    __tablename__ = "tuition_reservations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="tuition_reservation_amount_positive"),
        CheckConstraint("state IN ('RESERVED', 'PAID', 'CANCELLED')", name="tuition_reservation_state_valid"),
    )
    payment_id: Mapped[UUID] = mapped_column(primary_key=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(16))
