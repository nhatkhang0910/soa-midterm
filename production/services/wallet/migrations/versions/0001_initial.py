from alembic import op
import sqlalchemy as sa

revision = "wallet_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("wallets",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("balance", sa.BigInteger(), nullable=False),
        sa.Column("reserved", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("balance >= 0", name="wallet_balance_nonnegative"),
        sa.CheckConstraint("reserved >= 0 AND reserved <= balance", name="wallet_reserved_valid"))
    op.create_table("wallet_reservations",
        sa.Column("payment_id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("wallets.user_id"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.CheckConstraint("amount > 0", name="wallet_reservation_amount_positive"),
        sa.CheckConstraint("state IN ('RESERVED', 'CAPTURED', 'CANCELLED')", name="wallet_reservation_state_valid"))
    op.create_table("wallet_debits",
        sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("wallet_reservations.payment_id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("wallets.user_id"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="wallet_debit_amount_positive"))


def downgrade():
    op.drop_table("wallet_debits")
    op.drop_table("wallet_reservations")
    op.drop_table("wallets")
