"""Add owner-scoped catalog and device-agent checkpoints."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_catalog_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("price", sa.Integer()),
        sa.Column("currency", sa.String(3)),
        sa.Column("source_url", sa.String(600)),
    )
    op.create_index(
        "ix_agent_catalog_owner_filter",
        "agent_catalog_items",
        ["owner_id", "category", "currency", "price"],
    )
    op.create_table(
        "agent_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scan_id", sa.Uuid(), sa.ForeignKey("scan_sessions.id"), unique=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
    )
    op.create_index("ix_agent_executions_owner_created", "agent_executions", ["owner_id", "created_at"])
    op.create_index("ix_agent_executions_expiry", "agent_executions", ["expires_at", "id"])
    for table in ("agent_catalog_items", "agent_executions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL ON TABLE {table} FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL ON TABLE {table} FROM authenticated;
                END IF;
            END $$;
        """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_catalog_vectors")
    op.drop_table("agent_executions")
    op.drop_table("agent_catalog_items")
