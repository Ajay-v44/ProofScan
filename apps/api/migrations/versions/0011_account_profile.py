"""Add account display names and local recovery."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(60)))
    op.add_column("users", sa.Column("recovery_hash", sa.String(64)))
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
    op.drop_column("users", "recovery_hash")
    op.drop_column("users", "display_name")
