"""Track deleted accounts and permit only owner-scoped signed record removal."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deleted_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider_retry_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_deleted_accounts_provider_retry_at", "deleted_accounts", ["provider_retry_at"])
    op.execute("ALTER TABLE deleted_accounts ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE deleted_accounts FROM PUBLIC")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON TABLE deleted_accounts FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON TABLE deleted_accounts FROM authenticated;
            END IF;
        END $$;
    """)
    op.drop_constraint("admin_audit_logs_actor_id_fkey", "admin_audit_logs", type_="foreignkey")
    op.execute("""
        CREATE OR REPLACE FUNCTION proofscan_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            account_id uuid;
            checked_report_id uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                CASE TG_TABLE_NAME
                    WHEN 'reports' THEN
                        SELECT owner_id INTO account_id FROM verification_requests
                        WHERE id = OLD.verification_id;
                    WHEN 'report_signatures', 'report_invalidations' THEN
                        checked_report_id := OLD.report_id;
                        SELECT v.owner_id INTO account_id FROM reports r
                        JOIN verification_requests v ON v.id = r.verification_id
                        WHERE r.id = checked_report_id;
                    WHEN 'comparison_results' THEN
                        SELECT owner_id INTO account_id FROM handoffs WHERE id = OLD.handoff_id;
                    WHEN 'comparison_invalidations' THEN
                        checked_report_id := OLD.report_id;
                        SELECT h.owner_id INTO account_id FROM comparison_results c
                        JOIN handoffs h ON h.id = c.handoff_id WHERE c.id = checked_report_id;
                    ELSE
                        NULL;
                END CASE;
                IF EXISTS (SELECT 1 FROM deleted_accounts WHERE id = account_id) THEN
                    RETURN OLD;
                END IF;
            END IF;
            RAISE EXCEPTION 'ProofScan signed report records and audit entries are append-only'
                USING ERRCODE = '23514';
        END;
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION proofscan_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'ProofScan signed report records and audit entries are append-only'
                USING ERRCODE = '23514';
        END;
        $$;
    """)
    # Existing operator audit entries may refer to accounts erased since this upgrade.
    op.execute("""
        ALTER TABLE admin_audit_logs ADD CONSTRAINT admin_audit_logs_actor_id_fkey
        FOREIGN KEY (actor_id) REFERENCES users (id) NOT VALID
    """)
    op.drop_table("deleted_accounts")
