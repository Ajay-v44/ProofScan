"""Index evidence awaiting the retention worker."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_evidence_pending_purge",
        "evidence_items",
        ["expires_at", "id"],
        postgresql_where=sa.text("jpeg IS NOT NULL"),
    )
    op.create_index(
        "ix_checkpoint_pending_purge",
        "handoff_checkpoints",
        ["photo_expires_at", "id"],
        postgresql_where=sa.text("jpeg IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_checkpoint_pending_purge", table_name="handoff_checkpoints")
    op.drop_index("ix_evidence_pending_purge", table_name="evidence_items")
