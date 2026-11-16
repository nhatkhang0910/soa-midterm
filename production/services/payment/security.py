import hashlib
import hmac
import json
import os

from cryptography.fernet import Fernet


def otp_hmac(code: str) -> str:
    return hmac.new(os.environ["OTP_HMAC_KEY"].encode(), code.encode(), hashlib.sha256).hexdigest()


def encrypt_payload(payload: dict) -> str:
    return Fernet(os.environ["EMAIL_ENCRYPTION_KEY"].encode()).encrypt(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    ).decode()


def request_fingerprint(invoice_id: str) -> str:
    return hashlib.sha256(f"{invoice_id}:acceptedTerms=true".encode()).hexdigest()
