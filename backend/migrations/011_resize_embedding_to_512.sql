-- Resize knowledge_base.embedding from vector(1536) to vector(512)
-- pgvector does not support ALTER COLUMN TYPE for vectors, so we drop and recreate.
-- Existing embeddings are cleared; use the /api/v1/admin/kb/bulk-re-embed endpoint
-- to regenerate them after running this migration.

ALTER TABLE knowledge_base DROP COLUMN IF EXISTS embedding;
ALTER TABLE knowledge_base ADD COLUMN embedding vector(512);
