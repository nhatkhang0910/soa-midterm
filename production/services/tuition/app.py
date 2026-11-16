from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import Field
from sqlalchemy import select, text

from common import ApiError, DTO, Session, create_app, current_user, require_payment
from tuition.models import Invoice, Reservation, Student

app = create_app("Tuition")


class StudentResponse(DTO):
    id: UUID
    mssv: str
    fullName: str


class InvoiceResponse(DTO):
    id: UUID
    amount: int
    currency: Literal["VND"] = "VND"
    status: Literal["UNPAID", "RESERVED", "PAID"]


class TuitionResponse(DTO):
    student: StudentResponse
    invoice: InvoiceResponse | None


class InternalInvoiceResponse(InvoiceResponse):
    student: StudentResponse


class ReservationCommand(DTO):
    invoiceId: UUID
    amount: Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
    state: Literal["RESERVED", "PAID", "CANCELLED"]


class ReservationResponse(ReservationCommand):
    paymentId: UUID


def student_response(student):
    return StudentResponse(id=student.id, mssv=student.mssv, fullName=student.full_name)


def reservation_response(reservation):
    return ReservationResponse(paymentId=reservation.payment_id, invoiceId=reservation.invoice_id, amount=reservation.amount, state=reservation.state)


@app.get("/api/v1/students/{mssv}/tuition", response_model=TuitionResponse, dependencies=[Depends(current_user)])
async def student_tuition(mssv: str):
    async with Session() as session:
        student = await session.scalar(select(Student).where(Student.mssv == mssv))
        if student is None:
            raise ApiError(404, "STUDENT_NOT_FOUND", "Không tìm thấy sinh viên.")
        invoice = await session.scalar(select(Invoice).where(Invoice.student_id == student.id))
        return TuitionResponse(student=student_response(student), invoice=InvoiceResponse(id=invoice.id, amount=invoice.amount, status=invoice.status) if invoice else None)


@app.get("/internal/invoices/{invoiceId}", response_model=InternalInvoiceResponse, dependencies=[Depends(require_payment)])
async def internal_invoice(invoiceId: UUID):
    async with Session() as session:
        invoice = await session.get(Invoice, invoiceId)
        if invoice is None:
            raise ApiError(404, "INVOICE_NOT_FOUND", "Không tìm thấy khoản học phí.")
        student = await session.get(Student, invoice.student_id)
        return InternalInvoiceResponse(id=invoice.id, amount=invoice.amount, status=invoice.status, student=student_response(student))


@app.get("/internal/reservations/{paymentId}", response_model=ReservationResponse, dependencies=[Depends(require_payment)])
async def get_reservation(paymentId: UUID):
    async with Session() as session:
        reservation = await session.get(Reservation, paymentId)
        if reservation is None:
            raise ApiError(404, "RESERVATION_NOT_FOUND", "Không tìm thấy lệnh giữ học phí.")
        return reservation_response(reservation)


@app.put("/internal/reservations/{paymentId}", response_model=ReservationResponse, dependencies=[Depends(require_payment)])
async def put_reservation(paymentId: UUID, command: ReservationCommand):
    async with Session.begin() as session:
        # Serialize the payment before invoice locks, including commands that disagree on their invoice.
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "tuition:" + str(paymentId)})
        existing = await session.get(Reservation, paymentId)
        if existing and (existing.invoice_id != command.invoiceId or existing.amount != command.amount):
            raise ApiError(409, "RESERVATION_MISMATCH", "Thông tin lệnh giữ học phí không khớp.")
        invoice = await session.scalar(select(Invoice).where(Invoice.id == command.invoiceId).with_for_update())
        if invoice is None:
            raise ApiError(404, "INVOICE_NOT_FOUND", "Không tìm thấy khoản học phí.")
        if invoice.amount != command.amount:
            raise ApiError(409, "AMOUNT_MISMATCH", "Số tiền không khớp khoản học phí.")
        if existing and existing.state == command.state:
            return reservation_response(existing)
        if existing and existing.state in ("PAID", "CANCELLED"):
            raise ApiError(409, "RESERVATION_FINAL", "Lệnh giữ học phí đã kết thúc.")
        if command.state == "RESERVED":
            if invoice.status != "UNPAID":
                raise ApiError(409, "INVOICE_UNAVAILABLE", "Khoản học phí đã thanh toán hoặc đang được giữ.")
            invoice.status = "RESERVED"
            invoice.reserved_payment_id = paymentId
            existing = Reservation(payment_id=paymentId, invoice_id=command.invoiceId, amount=command.amount, state="RESERVED")
            session.add(existing)
        elif command.state == "PAID":
            if existing is None or invoice.status != "RESERVED" or invoice.reserved_payment_id != paymentId:
                raise ApiError(409, "RESERVATION_REQUIRED", "Cần giữ đúng khoản học phí trước khi thanh toán.")
            invoice.status = "PAID"
            invoice.reserved_payment_id = None
            invoice.paid_payment_id = paymentId
            existing.state = "PAID"
        else:
            if existing:
                if invoice.status != "RESERVED" or invoice.reserved_payment_id != paymentId:
                    raise ApiError(409, "RESERVATION_MISMATCH", "Lệnh giữ không sở hữu khoản học phí.")
                invoice.status = "UNPAID"
                invoice.reserved_payment_id = None
                existing.state = "CANCELLED"
            else:
                existing = Reservation(payment_id=paymentId, invoice_id=command.invoiceId, amount=command.amount, state="CANCELLED")
                session.add(existing)
        await session.flush()
        return reservation_response(existing)
