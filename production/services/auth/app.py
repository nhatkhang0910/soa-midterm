import asyncio
from datetime import timedelta

import jwt
from fastapi import Depends
from pydantic import Field
from pwdlib import PasswordHash
from sqlalchemy import select

from common import DTO, ApiError, Session, create_app, current_user, require_payment, secret, utcnow
from auth.models import User

app = create_app("Auth")
passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("not-a-real-user-password")


class Login(DTO):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ProfileResponse(DTO):
    id: str
    fullName: str
    phone: str
    email: str


class TokenResponse(DTO):
    accessToken: str
    tokenType: str
    expiresIn: int


def issue_token(user_id):
    now = utcnow()
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=1),
                       "iss": "ibanking", "aud": "ibanking-web"}, secret("JWT_PRIVATE_KEY"), algorithm="RS256")


def profile(user):
    return {"id": user.id, "fullName": user.full_name, "phone": user.phone, "email": user.email}


@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(body: Login):
    async with Session() as session:
        user = await session.scalar(select(User).where(User.username == body.username))
    valid = await asyncio.to_thread(passwords.verify, body.password, user.password_hash if user else DUMMY_HASH)
    if not valid or user is None:
        raise ApiError(401, "LOGIN_INVALID", "Tên đăng nhập hoặc mật khẩu không đúng.")
    return {"accessToken": issue_token(user.id), "tokenType": "bearer", "expiresIn": 3600}


async def get_profile(user_id):
    async with Session() as session:
        user = await session.get(User, user_id)
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "Không tìm thấy tài khoản.")
    return profile(user)


@app.get("/api/v1/me", response_model=ProfileResponse)
async def me(user_id: str = Depends(current_user)):
    return await get_profile(user_id)


@app.get("/internal/users/{user_id}", response_model=ProfileResponse, dependencies=[Depends(require_payment)])
async def internal_user(user_id: str):
    return await get_profile(user_id)
