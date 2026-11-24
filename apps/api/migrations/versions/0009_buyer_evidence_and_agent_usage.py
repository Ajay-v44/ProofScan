"""Scope buyer retrieval to shared evidence and record repeatable exterior views."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "verification_requests",
        sa.Column("require_exterior", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("verification_requests", "require_exterior", server_default=sa.true())
    op.add_column("verification_requests", sa.Column("baseline_report_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_verification_baseline_report",
        "verification_requests",
        "reports",
        ["baseline_report_id"],
        ["id"],
    )
    op.add_column("evidence_items", sa.Column("descriptor", JSONB(none_as_null=True)))
    op.add_column("agent_catalog_items", sa.Column("report_id", sa.Uuid()))
    op.add_column("agent_catalog_items", sa.Column("facts", JSONB(none_as_null=True)))
    op.create_foreign_key("fk_catalog_report", "agent_catalog_items", "reports", ["report_id"], ["id"])
    op.create_unique_constraint("uq_catalog_report", "agent_catalog_items", ["report_id"])
    op.create_table(
        "agent_daily_usage",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("kind", sa.String(24), primary_key=True),
        *(
            sa.Column(name, sa.BigInteger(), nullable=False)
            for name in ("requests", "accepted", "model_calls", "input_tokens", "output_tokens")
        ),
    )
    op.create_table(
        "handoff_checkpoint_photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("checkpoint_id", sa.Uuid(), sa.ForeignKey("handoff_checkpoints.id"), nullable=False),
        sa.Column("angle", sa.String(8), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("jpeg", sa.LargeBinary()),
        sa.Column("descriptor", JSONB(none_as_null=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("checkpoint_id", "angle"),
    )
    op.create_index(
        "ix_handoff_checkpoint_photos_expires_at", "handoff_checkpoint_photos", ["expires_at"]
    )
    for table in ("agent_daily_usage", "handoff_checkpoint_photos"):
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
    op.drop_table("handoff_checkpoint_photos")
    op.drop_table("agent_daily_usage")
    op.drop_constraint("uq_catalog_report", "agent_catalog_items", type_="unique")
    op.drop_constraint("fk_catalog_report", "agent_catalog_items", type_="foreignkey")
    op.drop_column("agent_catalog_items", "facts")
    op.drop_column("agent_catalog_items", "report_id")
    op.drop_column("evidence_items", "descriptor")
    op.drop_constraint("fk_verification_baseline_report", "verification_requests", type_="foreignkey")
    op.drop_column("verification_requests", "baseline_report_id")
    op.drop_column("verification_requests", "require_exterior")
