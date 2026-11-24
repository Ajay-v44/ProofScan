BEGIN;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE TABLE IF NOT EXISTS agent_catalog_vectors (
    item_id uuid PRIMARY KEY REFERENCES agent_catalog_items (id) ON DELETE CASCADE,
    embedding public.vector(384) NOT NULL,
    model text NOT NULL
);

ALTER TABLE agent_catalog_vectors ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE agent_catalog_vectors FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE agent_catalog_vectors FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE agent_catalog_vectors FROM authenticated;
    END IF;
END $$;

COMMIT;
