import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, Header, Request
from fastapi.security import HTTPBearer
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from starlette.exceptions import HTTPException


class Base(DeclarativeBase):
    pass


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(DTO):
    code: str
    message: str
    requestId: str


bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, hide_parameters=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


def utcnow():
    return datetime.now(timezone.utc)


def secret(name):
    if path := os.getenv(name + "_FILE"):
        return Path(path).read_text(encoding="utf-8")
    return os.environ[name].replace("\\n", "\n")


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(code)


def require_payment(x_service_key: str | None = Header(default=None)):
    expected = os.environ["PAYMENT_SERVICE_KEY"]
    if not isinstance(x_service_key, str) or not secrets.compare_digest(x_service_key.encode(), expected.encode()):
        raise ApiError(403, "SERVICE_FORBIDDEN", "Không có quyền gọi API nội bộ.")


def current_user(request: Request, credentials=Depends(bearer)):
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise ApiError(401, "UNAUTHORIZED", "Vui lòng đăng nhập.")
    try:
        claims = jwt.decode(
            authorization[7:], secret("JWT_PUBLIC_KEY"), algorithms=["RS256"],
            issuer="ibanking", audience="ibanking-web",
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        return str(uuid.UUID(claims["sub"]))
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise ApiError(401, "TOKEN_INVALID", "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.") from None


def create_app(name):
    app = FastAPI(title=f"iBanking — {name}", version="1.0.0", responses={
        status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 409, 410, 422, 429, 500, 503)
    })

    def error(request, status, code, message):
        return JSONResponse(status_code=status, content={
            "code": code, "message": message,
            "requestId": getattr(request.state, "request_id", str(uuid.uuid4())),
        })

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = str(uuid.uuid4())
        try:
            response = await call_next(request)
        except Exception as exc:
            logging.getLogger(name).error("request_failed requestId=%s type=%s", request.state.request_id, type(exc).__name__)
            response = error(request, 500, "INTERNAL_ERROR", "Hệ thống tạm thời không xử lý được yêu cầu.")
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ApiError)
    async def api_error(request, exc):
        return error(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(request, 422, "VALIDATION_ERROR", "Dữ liệu không hợp lệ. Vui lòng kiểm tra các trường nhập.")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(request, exc.status_code, "HTTP_ERROR", "Yêu cầu không hợp lệ.")

    @app.get("/health", tags=["health"])
    async def health():
        async with Session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "service": name}

    return app
