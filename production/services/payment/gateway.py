import os

import httpx

from common import ApiError


async def internal_client():
    async with httpx.AsyncClient(timeout=5.0) as client:
        yield client


class RemoteFailure(Exception):
    def __init__(self, code: str, business: bool = False):
        self.code = code[:80]
        self.business = business
        super().__init__(self.code)


async def request(client: httpx.AsyncClient, service: str, method: str, path: str, payload=None):
    base = os.getenv(service.upper() + "_URL", f"http://{service}:8000")
    try:
        response = await client.request(method, base + path, json=payload,
                                        headers={"X-Service-Key": os.environ["PAYMENT_SERVICE_KEY"]}, timeout=5.0)
    except httpx.HTTPError:
        raise RemoteFailure("DEPENDENCY_UNAVAILABLE") from None
    if response.is_error:
        # Only bounded error codes cross the trust boundary; never log response bodies.
        code = "DEPENDENCY_UNAVAILABLE"
        try:
            candidate = response.json().get("code", "")
            if isinstance(candidate, str) and candidate and len(candidate) <= 80 and all(c.isupper() or c.isdigit() or c == "_" for c in candidate):
                code = candidate
        except (ValueError, AttributeError):
            pass
        raise RemoteFailure(code, business=response.status_code in (400, 404, 409, 422))
    try:
        return response.json()
    except ValueError:
        raise RemoteFailure("DEPENDENCY_INVALID_RESPONSE") from None


def public_dependency_error(exc: RemoteFailure):
    return ApiError(409 if exc.business else 503, exc.code,
                    "Thông tin thanh toán đã thay đổi." if exc.business else "Dịch vụ tạm thời chưa sẵn sàng.")
