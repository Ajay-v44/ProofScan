"""Support deterministic keyset pagination on owner collections."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

OWNER_INDEXES = (
    ("ix_verification_owner_created", "verification_requests"),
    ("ix_notifications_owner_created", "notifications"),
    ("ix_handoff_owner_created", "handoffs"),
)


def upgrade() -> None:
    for index, table in OWNER_INDEXES:
        op.drop_index(index, table_name=table)
        op.create_index(index, table, ["owner_id", "created_at", "id"])


def downgrade() -> None:
    for index, table in OWNER_INDEXES:
        op.drop_index(index, table_name=table)
        op.create_index(index, table, ["owner_id", "created_at"])
