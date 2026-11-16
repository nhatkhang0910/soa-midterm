import secrets
from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, Header, Query, Response
from pydantic import Field, StrictBool, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from common import ApiError, DTO, Session, create_app, current_user, utcnow
from payment.gateway import RemoteFailure, internal_client, public_dependency_error, request
from payment.models import Challenge, Outbox, Payment
from payment.security import encrypt_payload, otp_hmac, request_fingerprint

app = create_app("payment")


class CreatePayment(DTO):
    invoiceId: UUID
    acceptedTerms: StrictBool

    @field_validator("acceptedTerms")
    @classmethod
    def accepted(cls, value):
        if not value:
            raise ValueError("terms required")
        return value


class ConfirmPayment(DTO):
    otp: Annotated[str, Field(pattern=r"^[0-9]{6}$", min_length=6, max_length=6)]


class PayerSnapshot(DTO):
    id: UUID
    fullName: str
    phone: str
    email: str


class StudentSnapshot(DTO):
    id: UUID
    mssv: str
    fullName: str


class PaymentResponse(DTO):
    id: UUID
    status: Literal["PENDING_OTP", "PROCESSING", "SUCCEEDED", "FAILED", "EXPIRED"]
    amount: int
    currency: Literal["VND"]
    otpExpiresAt: datetime
    payer: PayerSnapshot
    student: StudentSnapshot
    createdAt: datetime
    failureCode: str | None


class HistoryResponse(DTO):
    items: list[PaymentResponse]
    page: int
    pageSize: int
    total: int


class ErrorResponse(DTO):
    code: str
    message: str
    requestId: str


ERRORS = {code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 409, 410, 422, 429, 503)}


def payment_json(payment: Payment):
    return {"id": payment.id, "status": payment.status, "amount": payment.amount, "currency": "VND",
            "otpExpiresAt": payment.otp_expires_at, "payer": payment.payer, "student": payment.student,
            "createdAt": payment.created_at, "failureCode": payment.failure_code}


async def expire_payment(session, payment: Payment, now):
    if payment.status != "PENDING_OTP" or payment.otp_expires_at > now:
        return False
    challenge = await session.scalar(select(Challenge).where(Challenge.payment_id == payment.id).with_for_update())
    if challenge and challenge.status == "ACTIVE":
        challenge.status = "EXPIRED"
    payment.status = "EXPIRED"
    payment.failure_code = "OTP_EXPIRED"
    await session.execute(update(Outbox).where(Outbox.payment_id == payment.id, Outbox.kind == "OTP",
                                             Outbox.status == "PENDING").values(
        status="EXPIRED", encrypted_payload=None, claim_token=None, lease_until=None))
    return True


async def expire_pending(session, now):
    payments = (await session.scalars(select(Payment).where(Payment.status == "PENDING_OTP",
                            Payment.otp_expires_at <= now).order_by(Payment.id).with_for_update(skip_locked=True))).all()
    for payment in payments:
        await expire_payment(session, payment, now)
    await session.flush()


def check_existing(payment, fingerprint):
    if payment.fingerprint != fingerprint:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "Khóa yêu cầu đã được dùng cho nội dung khác.")
    return payment_json(payment)


@app.post("/api/v1/payments", status_code=201, tags=["payments"], response_model=PaymentResponse,
          responses={**ERRORS, 200: {"model": PaymentResponse, "description": "Idempotent replay"}})
async def create_payment(body: CreatePayment, response: Response,
                         idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
                         user_id: str = Depends(current_user), client: httpx.AsyncClient = Depends(internal_client)):
    invoice_id = str(body.invoiceId)
    fingerprint = request_fingerprint(invoice_id)
    async with Session.begin() as session:
        existing = await session.scalar(select(Payment).where(Payment.payer_id == user_id, Payment.idempotency_key == idempotency_key).with_for_update())
        if existing:
            await expire_payment(session, existing, utcnow())
            response.status_code = 200
            return check_existing(existing, fingerprint)
    try:
        profile = await request(client, "auth", "GET", f"/internal/users/{user_id}")
        invoice = await request(client, "tuition", "GET", f"/internal/invoices/{invoice_id}")
        wallet = await request(client, "wallet", "GET", f"/internal/wallets/{user_id}")
    except RemoteFailure as exc:
        async with Session.begin() as session:
            existing = await session.scalar(select(Payment).where(Payment.payer_id == user_id, Payment.idempotency_key == idempotency_key).with_for_update())
            if existing:
                await expire_payment(session, existing, utcnow())
                response.status_code = 200
                return check_existing(existing, fingerprint)
        raise public_dependency_error(exc) from None
    now = utcnow()
    payment = Payment(id=str(uuid4()), payer_id=user_id, invoice_id=invoice_id,
                      idempotency_key=idempotency_key, fingerprint=fingerprint,
                      amount=invoice["amount"], payer=profile, student=invoice["student"],
                      otp_expires_at=now + timedelta(minutes=5), created_at=now)
    try:
        async with Session.begin() as session:
            existing = await session.scalar(select(Payment).where(Payment.payer_id == user_id, Payment.idempotency_key == idempotency_key).with_for_update())
            if existing:
                await expire_payment(session, existing, utcnow())
                response.status_code = 200
                return check_existing(existing, fingerprint)
            if invoice["status"] != "UNPAID":
                raise ApiError(409, "INVOICE_UNAVAILABLE", "Khoản học phí không còn có thể thanh toán.")
            if not isinstance(invoice["amount"], int) or isinstance(invoice["amount"], bool) or invoice["amount"] <= 0:
                raise ApiError(503, "DEPENDENCY_INVALID_RESPONSE", "Dữ liệu học phí không hợp lệ.")
            if wallet["available"] < invoice["amount"]:
                raise ApiError(409, "INSUFFICIENT_FUNDS", "Số dư khả dụng không đủ.")
            await expire_pending(session, now)
            session.add(payment)
            await session.flush()
            for _ in range(20):
                code = f"{secrets.randbelow(1_000_000):06d}"
                try:
                    async with session.begin_nested():
                        session.add(Challenge(payment_id=payment.id, code_hmac=otp_hmac(code), expires_at=payment.otp_expires_at))
                        await session.flush()
                    break
                except IntegrityError as exc:
                    if getattr(exc.orig.diag, "constraint_name", None) != "uq_active_otp_hmac":
                        raise
            else:
                raise ApiError(503, "OTP_UNAVAILABLE", "Chưa thể cấp mã OTP. Vui lòng thử lại.")
            session.add(Outbox(id=str(uuid4()), payment_id=payment.id, kind="OTP", recipient=profile["email"],
                               encrypted_payload=encrypt_payload({"otp": code, "paymentId": payment.id,
                                       "amount": payment.amount, "studentName": payment.student["fullName"]}),
                               expires_at=payment.otp_expires_at))
    except IntegrityError as exc:
        if getattr(exc.orig.diag, "constraint_name", None) != "uq_payment_idempotency":
            raise
        async with Session.begin() as session:
            existing = await session.scalar(select(Payment).where(Payment.payer_id == user_id, Payment.idempotency_key == idempotency_key).with_for_update())
            await expire_payment(session, existing, utcnow())
            response.status_code = 200
            return check_existing(existing, fingerprint)
    return payment_json(payment)


async def owned_payment(session, payment_id, user_id):
    payment = await session.scalar(select(Payment).where(Payment.id == str(payment_id)).with_for_update())
    if not payment:
        raise ApiError(404, "PAYMENT_NOT_FOUND", "Không tìm thấy giao dịch.")
    if payment.payer_id != user_id:
        raise ApiError(403, "PAYMENT_FORBIDDEN", "Bạn không có quyền xem giao dịch này.")
    return payment


@app.post("/api/v1/payments/{payment_id}/confirm", status_code=202, tags=["payments"], response_model=PaymentResponse,
          responses={**ERRORS, 200: {"model": PaymentResponse, "description": "Already succeeded"}})
async def confirm_payment(payment_id: UUID, body: ConfirmPayment, response: Response, user_id: str = Depends(current_user)):
    error = None
    async with Session.begin() as session:
        payment = await owned_payment(session, payment_id, user_id)
        now = utcnow()
        if payment.status == "SUCCEEDED":
            response.status_code = 200
        elif payment.status == "PROCESSING":
            pass
        elif payment.status in ("FAILED", "EXPIRED"):
            error = ApiError(409, "PAYMENT_FINAL", "Giao dịch đã kết thúc. Vui lòng tạo giao dịch mới.")
        elif await expire_payment(session, payment, now):
            error = ApiError(410, "OTP_EXPIRED", "Mã OTP đã hết hạn.")
        else:
            challenge = await session.scalar(select(Challenge).where(Challenge.payment_id == payment.id).with_for_update())
            if not secrets.compare_digest(challenge.code_hmac, otp_hmac(body.otp)):
                challenge.attempts += 1
                if challenge.attempts == 5:
                    challenge.status = "LOCKED"
                    payment.status = "FAILED"
                    payment.failure_code = "OTP_LOCKED"
                    error = ApiError(429, "OTP_LOCKED", "Mã OTP đã bị khóa sau 5 lần nhập sai.")
                    await session.execute(update(Outbox).where(Outbox.payment_id == payment.id, Outbox.kind == "OTP", Outbox.status == "PENDING").values(status="EXPIRED", encrypted_payload=None, claim_token=None, lease_until=None))
                else:
                    error = ApiError(400, "OTP_INVALID", "Mã OTP không đúng.")
            else:
                challenge.status = "USED"
                payment.status = "PROCESSING"
                payment.saga_state = "PREPARING"
                payment.prepare_deadline = now + timedelta(seconds=30)
                payment.next_attempt_at = now
        result = payment_json(payment)
    if error:
        raise error
    return result


@app.get("/api/v1/payments", tags=["payments"], response_model=HistoryResponse, responses=ERRORS)
async def list_payments(page: Annotated[int, Query(ge=1)] = 1,
                        pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
                        user_id: str = Depends(current_user)):
    async with Session.begin() as session:
        rows = (await session.scalars(select(Payment).where(Payment.payer_id == user_id)
                    .order_by(Payment.created_at.desc(), Payment.id.desc()).offset((page - 1) * pageSize)
                    .limit(pageSize).with_for_update())).all()
        for payment in rows:
            await expire_payment(session, payment, utcnow())
        total = await session.scalar(select(func.count()).select_from(Payment).where(Payment.payer_id == user_id))
        return {"items": [payment_json(payment) for payment in rows], "page": page, "pageSize": pageSize, "total": total}


@app.get("/api/v1/payments/{payment_id}", tags=["payments"], response_model=PaymentResponse, responses=ERRORS)
async def get_payment(payment_id: UUID, user_id: str = Depends(current_user)):
    async with Session.begin() as session:
        payment = await owned_payment(session, payment_id, user_id)
        await expire_payment(session, payment, utcnow())
        return payment_json(payment)
