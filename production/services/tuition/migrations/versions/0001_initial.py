from alembic import op
import sqlalchemy as sa

revision = "tuition_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("students",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("mssv", sa.String(20), nullable=False, unique=True),
        sa.Column("full_name", sa.String(200), nullable=False))
    op.create_table("invoices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False, unique=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reserved_payment_id", sa.Uuid(), unique=True),
        sa.Column("paid_payment_id", sa.Uuid(), unique=True),
        sa.CheckConstraint("amount > 0", name="tuition_invoice_amount_positive"),
        sa.CheckConstraint("status IN ('UNPAID', 'RESERVED', 'PAID')", name="tuition_invoice_status_valid"),
        sa.CheckConstraint("(status = 'UNPAID' AND reserved_payment_id IS NULL AND paid_payment_id IS NULL) OR (status = 'RESERVED' AND reserved_payment_id IS NOT NULL AND paid_payment_id IS NULL) OR (status = 'PAID' AND reserved_payment_id IS NULL)", name="tuition_invoice_owner_valid"))
    op.create_table("tuition_reservations",
        sa.Column("payment_id", sa.Uuid(), primary_key=True),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.CheckConstraint("amount > 0", name="tuition_reservation_amount_positive"),
        sa.CheckConstraint("state IN ('RESERVED', 'PAID', 'CANCELLED')", name="tuition_reservation_state_valid"))


def downgrade():
    op.drop_table("tuition_reservations")
    op.drop_table("invoices")
    op.drop_table("students")
