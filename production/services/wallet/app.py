from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import Field
from sqlalchemy import select, text

from common import ApiError, DTO, Session, create_app, current_user, require_payment
from wallet.models import Debit, Reservation, Wallet

app = create_app("Wallet")


class WalletResponse(DTO):
    balance: int
    reserved: int
    available: int
    currency: Literal["VND"] = "VND"


class ReservationCommand(DTO):
    userId: UUID
    amount: Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
    state: Literal["RESERVED", "CAPTURED", "CANCELLED"]


class ReservationResponse(ReservationCommand):
    paymentId: UUID


def reservation_response(reservation):
    return ReservationResponse(paymentId=reservation.payment_id, userId=reservation.user_id, amount=reservation.amount, state=reservation.state)


async def read_wallet(user_id):
    async with Session() as session:
        wallet = await session.get(Wallet, user_id)
        if wallet is None:
            raise ApiError(404, "WALLET_NOT_FOUND", "Không tìm thấy ví.")
        return WalletResponse(balance=wallet.balance, reserved=wallet.reserved, available=wallet.balance - wallet.reserved)


@app.get("/api/v1/wallet", response_model=WalletResponse)
async def my_wallet(user_id: str = Depends(current_user)):
    return await read_wallet(UUID(user_id))


@app.get("/internal/wallets/{userId}", response_model=WalletResponse, dependencies=[Depends(require_payment)])
async def internal_wallet(userId: UUID):
    return await read_wallet(userId)


@app.get("/internal/reservations/{paymentId}", response_model=ReservationResponse, dependencies=[Depends(require_payment)])
async def get_reservation(paymentId: UUID):
    async with Session() as session:
        reservation = await session.get(Reservation, paymentId)
        if reservation is None:
            raise ApiError(404, "RESERVATION_NOT_FOUND", "Không tìm thấy lệnh giữ tiền.")
        return reservation_response(reservation)


@app.put("/internal/reservations/{paymentId}", response_model=ReservationResponse, dependencies=[Depends(require_payment)])
async def put_reservation(paymentId: UUID, command: ReservationCommand):
    async with Session.begin() as session:
        # Serialize the payment before resource locks, including conflicting payloads targeting different wallets.
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "wallet:" + str(paymentId)})
        existing = await session.get(Reservation, paymentId)
        if existing and (existing.user_id != command.userId or existing.amount != command.amount):
            raise ApiError(409, "RESERVATION_MISMATCH", "Thông tin lệnh giữ tiền không khớp.")
        wallet = await session.scalar(select(Wallet).where(Wallet.user_id == command.userId).with_for_update())
        if wallet is None:
            raise ApiError(404, "WALLET_NOT_FOUND", "Không tìm thấy ví.")
        if existing and existing.state == command.state:
            return reservation_response(existing)
        if existing and existing.state in ("CAPTURED", "CANCELLED"):
            raise ApiError(409, "RESERVATION_FINAL", "Lệnh giữ tiền đã kết thúc.")
        if command.state == "RESERVED":
            if wallet.balance - wallet.reserved < command.amount:
                raise ApiError(409, "INSUFFICIENT_FUNDS", "Số dư khả dụng không đủ.")
            wallet.reserved += command.amount
            existing = Reservation(payment_id=paymentId, user_id=command.userId, amount=command.amount, state="RESERVED")
            session.add(existing)
        elif command.state == "CAPTURED":
            if existing is None:
                raise ApiError(409, "RESERVATION_REQUIRED", "Cần giữ tiền trước khi ghi nợ.")
            wallet.balance -= command.amount
            wallet.reserved -= command.amount
            existing.state = "CAPTURED"
            session.add(Debit(payment_id=paymentId, user_id=command.userId, amount=command.amount))
        else:
            if existing:
                wallet.reserved -= command.amount
                existing.state = "CANCELLED"
            else:
                existing = Reservation(payment_id=paymentId, user_id=command.userId, amount=command.amount, state="CANCELLED")
                session.add(existing)
        await session.flush()
        return reservation_response(existing)
