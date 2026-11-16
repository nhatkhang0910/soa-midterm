from alembic import op
import sqlalchemy as sa
revision = "notification_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("messages", sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False), sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("encrypted_payload", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36)), sa.Column("lease_until", sa.DateTime(timezone=True)), sa.Column("last_error", sa.String(64)),
        sa.CheckConstraint("state IN ('QUEUED','SENT','EXPIRED')"))


def downgrade():
    op.drop_table("messages")
