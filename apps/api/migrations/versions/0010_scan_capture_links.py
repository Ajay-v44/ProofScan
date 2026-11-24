"""Add short-lived, photo-only access to a scan."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_capture_links",
        sa.Column(
            "scan_id", sa.Uuid(), sa.ForeignKey("scan_sessions.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scan_capture_links_expires_at", "scan_capture_links", ["expires_at"])
    op.execute("ALTER TABLE scan_capture_links ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE scan_capture_links FROM PUBLIC")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON TABLE scan_capture_links FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON TABLE scan_capture_links FROM authenticated;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_table("scan_capture_links")
