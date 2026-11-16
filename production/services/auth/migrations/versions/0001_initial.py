from alembic import op
import sqlalchemy as sa
revision = "auth_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("username", sa.String(64), nullable=False, unique=True),
                    sa.Column("password_hash", sa.Text(), nullable=False),
                    sa.Column("full_name", sa.String(160), nullable=False),
                    sa.Column("phone", sa.String(24), nullable=False),
                    sa.Column("email", sa.String(254), nullable=False))


def downgrade():
    op.drop_table("users")
