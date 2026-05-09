import json
import os
import openai
import psycopg2
from psycopg2.extras import execute_values

# CONFIGURATION
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SAMPLES_PATH = os.path.join(os.path.dirname(__file__), '../../data/tier_kb_samples.json')
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', 5432),
    'dbname': os.getenv('DB_NAME', 'postgres'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
}

openai.api_key = OPENAI_API_KEY

def load_samples(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_embedding(text):
    resp = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding

def upsert_kb_entry(cur, entry, embedding):
    # Check for duplicate
    cur.execute("""
        SELECT id, resolution_text FROM knowledge_base
        WHERE tier_level = %s AND tier_scope IS NOT DISTINCT FROM %s AND issue_type = %s
    """, (entry['tier_level'], entry['tier_scope'], entry['issue_type']))
    row = cur.fetchone()
    if row:
        # Update if content changed
        if row[1] != entry['resolution_text']:
            cur.execute("""
                UPDATE knowledge_base SET
                    category = %s,
                    resolution_text = %s,
                    quality_score = %s,
                    verified = %s,
                    embedding = %s
                WHERE id = %s
            """, (
                entry['category'],
                entry['resolution_text'],
                entry['quality_score'],
                entry['verified'],
                embedding,
                row[0]
            ))
            print(f"Updated: {entry['issue_type']} (tier {entry['tier_level']})")
        else:
            print(f"Skipped (no change): {entry['issue_type']} (tier {entry['tier_level']})")
    else:
        # Insert new
        cur.execute("""
            INSERT INTO knowledge_base (
                tier_level, tier_scope, category, issue_type, resolution_text,
                quality_score, verified, usage_count, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            entry['tier_level'],
            entry['tier_scope'],
            entry['category'],
            entry['issue_type'],
            entry['resolution_text'],
            entry['quality_score'],
            entry['verified'],
            0,
            embedding
        ))
        print(f"Inserted: {entry['issue_type']} (tier {entry['tier_level']})")

def main():
    samples = load_samples(SAMPLES_PATH)
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    for entry in samples:
        try:
            embedding = get_embedding(entry['resolution_text'])
            upsert_kb_entry(cur, entry, embedding)
            conn.commit()
        except Exception as e:
            print(f"Error processing {entry.get('issue_type')}: {e}")
            conn.rollback()
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()