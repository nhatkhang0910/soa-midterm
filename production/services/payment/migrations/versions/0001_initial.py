"""Payment, OTP and durable Saga/outbox work queues."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payments",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("payer_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("invoice_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("payer", JSONB(), nullable=False),
        sa.Column("student", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("saga_state", sa.String(16)),
        sa.Column("checkpoint", sa.Integer(), nullable=False),
        sa.Column("prepare_deadline", sa.DateTime(timezone=True)),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.Uuid(as_uuid=False)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(80)),
        sa.UniqueConstraint("payer_id", "idempotency_key", name="uq_payment_idempotency"),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount"),
        sa.CheckConstraint("status IN ('PENDING_OTP','PROCESSING','SUCCEEDED','FAILED','EXPIRED')", name="ck_payment_status"),
        sa.CheckConstraint("saga_state IS NULL OR saga_state IN ('PREPARING','COMMITTING','ABORTING')", name="ck_payment_saga"))
    op.create_index("ix_payment_history", "payments", ["payer_id", "created_at", "id"])
    op.create_index("ix_payment_work", "payments", ["status", "next_attempt_at"])
    op.create_table("otp_challenges",
        sa.Column("payment_id", sa.Uuid(as_uuid=False), sa.ForeignKey("payments.id"), primary_key=True),
        sa.Column("code_hmac", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_otp_attempts"),
        sa.CheckConstraint("status IN ('ACTIVE','USED','EXPIRED','LOCKED')", name="ck_otp_status"))
    op.create_index("uq_active_otp_hmac", "otp_challenges", ["code_hmac"], unique=True, postgresql_where=sa.text("status = 'ACTIVE'"))
    op.create_table("payment_outbox",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("payment_id", sa.Uuid(as_uuid=False), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("encrypted_payload", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.Uuid(as_uuid=False)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(80)),
        sa.UniqueConstraint("payment_id", "kind", name="uq_payment_event_kind"),
        sa.CheckConstraint("kind IN ('OTP','PAYMENT_SUCCEEDED')", name="ck_outbox_kind"),
        sa.CheckConstraint("status IN ('PENDING','DELIVERED','EXPIRED')", name="ck_outbox_status"))
    op.create_index("ix_outbox_work", "payment_outbox", ["status", "next_attempt_at"])


def downgrade():
    op.drop_table("payment_outbox")
    op.drop_table("otp_challenges")
    op.drop_table("payments")
