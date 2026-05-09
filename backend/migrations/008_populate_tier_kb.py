"""
Migration: 008_populate_tier_kb.py
Purpose: One-time migration to populate KB with sample data from tier_kb_samples.json
"""

import os
import json
from pathlib import Path

from dotenv import load_dotenv
import openai
import psycopg2
from psycopg2.extras import execute_values

# =========================================================
# LOAD .env FILE
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

print("Loaded ENV from:", ENV_PATH)

# =========================================================
# CONFIG
# =========================================================


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", 5432),
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "sslmode": "require"
}

print("DB_CONFIG:", DB_CONFIG)

openai.api_key = OPENAI_API_KEY
SAMPLES_PATH = os.path.join(os.path.dirname(__file__), '../data/tier_kb_samples.json')

BATCH_SIZE = 100
from dotenv import load_dotenv

def load_samples(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_embeddings_batch(texts):
    resp = openai.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in resp.data]

def kb_has_tier_entries(cur):
    cur.execute("SELECT COUNT(*) FROM knowledge_base WHERE tier_level IS NOT NULL")
    return cur.fetchone()[0] > 0

def insert_kb_entries(cur, entries, embeddings):
    values = [
        (
            e['tier_level'],
            e['tier_scope'],
            e['category'],
            e['issue_type'],
            e['resolution_text'],
            e['quality_score'],
            e['verified'],
            0,
            emb
        )
        for e, emb in zip(entries, embeddings)
    ]
    execute_values(cur, """
        INSERT INTO knowledge_base (
            tier_level, tier_scope, category, issue_type, resolution_text,
            quality_score, verified, usage_count, embedding
        ) VALUES %s
    """, values)


def main():
    samples = load_samples(SAMPLES_PATH)
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        print(f"Populating KB with {len(samples)} entries...")

        for i in range(0, len(samples), BATCH_SIZE):
            batch = samples[i:i + BATCH_SIZE]
            texts = [e['resolution_text'] for e in batch]
            embeddings = get_embeddings_batch(texts)
            insert_kb_entries(cur, batch, embeddings)

        conn.commit()

        print("Migration committed.")

        cur.execute("""
            SELECT tier_level, COUNT(*)
            FROM knowledge_base
            GROUP BY tier_level
            ORDER BY tier_level
        """)

        for row in cur.fetchall():
            print(f"Tier {row[0]}: {row[1]} entries")

    except Exception as e:
        print(f"Error: {e}. Rolling back.")
        conn.rollback()

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()