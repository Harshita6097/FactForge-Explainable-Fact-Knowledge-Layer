"""
Backfill extraction_failures for facts already in the DB.
Run once: python backfill_failures.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
import uuid
from datetime import datetime, timezone

conn = sqlite3.connect("factforge.db")
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")

# Facts with confidence < 0.72 that aren't already logged
rows = conn.execute("""
    SELECT f.id, f.document_id, f.entity, f.attribute, f.raw_value, f.confidence,
           e.page_number, e.snippet
    FROM facts f
    LEFT JOIN evidence e ON e.fact_id = f.id
    WHERE f.confidence < 0.72
      AND f.id NOT IN (SELECT DISTINCT raw_text FROM extraction_failures WHERE failure_reason='low_confidence')
    ORDER BY f.confidence ASC
    LIMIT 500
""").fetchall()

# Also get facts with Metric/Description attribute (unmapped)
noise_rows = conn.execute("""
    SELECT f.id, f.document_id, f.entity, f.attribute, f.raw_value, f.confidence,
           e.page_number, e.snippet
    FROM facts f
    LEFT JOIN evidence e ON e.fact_id = f.id
    WHERE f.attribute IN ('Metric', 'Description')
      AND f.id NOT IN (SELECT DISTINCT raw_text FROM extraction_failures WHERE failure_reason='unmapped_attribute')
    LIMIT 200
""").fetchall()

now = datetime.now(timezone.utc).isoformat()
inserted = 0

for r in rows:
    conn.execute("""
        INSERT OR IGNORE INTO extraction_failures
        (id, document_id, page_number, raw_text, failure_reason, chain_of_thought, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(uuid.uuid4()),
        r["document_id"],
        r["page_number"],
        r["snippet"][:500] if r["snippet"] else r["raw_value"][:500],
        "low_confidence",
        f"Entity='{r['entity']}' Attribute='{r['attribute']}' Value='{r['raw_value']}' "
        f"Confidence={r['confidence']:.2f} — below threshold 0.72; fact stored but flagged for review.",
        r["confidence"],
        now,
    ))
    inserted += 1

for r in noise_rows:
    conn.execute("""
        INSERT OR IGNORE INTO extraction_failures
        (id, document_id, page_number, raw_text, failure_reason, chain_of_thought, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(uuid.uuid4()),
        r["document_id"],
        r["page_number"],
        r["snippet"][:500] if r["snippet"] else r["raw_value"][:500],
        "unmapped_attribute",
        f"Entity='{r['entity']}' Attribute='{r['attribute']}' Value='{r['raw_value']}' — "
        f"attribute could not be mapped to a known financial/operational category.",
        r["confidence"],
        now,
    ))
    inserted += 1

conn.commit()
conn.close()
print(f"Backfilled {inserted} extraction failures.")
