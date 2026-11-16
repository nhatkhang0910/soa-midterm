"""Generate local-only credentials; existing environments are never overwritten."""
import argparse
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / ".env").exists():
        print("Existing .env kept. Edit SMTP settings there when needed.")
        return
    keys = folder / ".secrets"
    keys.mkdir(exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (keys / "private.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (keys / "public.pem").write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    values = {name: secrets.token_hex(32) for name in (
        "POSTGRES_PASSWORD", "AUTH_DB_PASSWORD", "WALLET_DB_PASSWORD", "TUITION_DB_PASSWORD",
        "PAYMENT_DB_PASSWORD", "NOTIFICATION_DB_PASSWORD", "PAYMENT_SERVICE_KEY", "OTP_HMAC_KEY",
    )}
    values.update(EMAIL_ENCRYPTION_KEY=Fernet.generate_key().decode(), WEB_PORT="8080",
                  DEMO_PASSWORD="Demo@123456", DEMO_EMAIL_AN="an@example.test", DEMO_EMAIL_BINH="binh@example.test",
                  SMTP_HOST="mailpit", SMTP_PORT="1025", SMTP_STARTTLS="false", SMTP_USERNAME="", SMTP_PASSWORD="",
                  SMTP_FROM="iBanking <noreply@ibanking.test>")
    (folder / ".env").write_text("\n".join(f'{name}="{value}"' for name, value in values.items()) + "\n", encoding="utf-8")
    print("Created .env and .secrets for local simulation. No credentials printed.")


if __name__ == "__main__":
    main()
