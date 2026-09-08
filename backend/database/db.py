import sqlite3
from contextlib import contextmanager
from utils.config import get_settings

settings = get_settings()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_url, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                page_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                uploaded_at TEXT NOT NULL,
                processed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                entity TEXT NOT NULL,
                attribute TEXT NOT NULL,
                canonical_value TEXT,
                raw_value TEXT NOT NULL,
                unit TEXT,
                period TEXT,
                confidence REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                fact_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                snippet TEXT NOT NULL,
                FOREIGN KEY (fact_id) REFERENCES facts(id),
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS document_pages (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                text TEXT NOT NULL,
                char_count INTEGER DEFAULT 0,
                processed INTEGER DEFAULT 0,
                UNIQUE(document_id, page_number),
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS attribute_registry (
                attribute TEXT NOT NULL,
                canonical_attribute TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 1,
                PRIMARY KEY (attribute)
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT PRIMARY KEY,
                source_fact_id TEXT NOT NULL,
                target_fact_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                explanation TEXT,
                confidence REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_fact_id) REFERENCES facts(id),
                FOREIGN KEY (target_fact_id) REFERENCES facts(id)
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                title TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                facts_used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS canonical_facts (
                id TEXT PRIMARY KEY,
                entity TEXT NOT NULL,
                canonical_entity TEXT NOT NULL,
                attribute TEXT NOT NULL,
                canonical_attribute TEXT NOT NULL,
                canonical_value TEXT,
                canonical_unit TEXT,
                period TEXT,
                confidence REAL DEFAULT 0.5,
                supporting_count INTEGER DEFAULT 1,
                conflicting_count INTEGER DEFAULT 0,
                source_fact_ids TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entity_aliases (
                raw_name TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attribute_aliases (
                raw_attribute TEXT PRIMARY KEY,
                canonical_attribute TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                verified INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS relationship_reasoning (
                relationship_id TEXT PRIMARY KEY,
                steps TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (relationship_id) REFERENCES relationships(id)
            );
        """)
        # Migrations — safe to run on existing DBs
        _migrate(conn)


def _migrate(conn):
    """Apply additive schema migrations to existing databases."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(facts)").fetchall()}
    if "canonical_unit" not in existing:
        conn.execute("ALTER TABLE facts ADD COLUMN canonical_unit TEXT")
    if "facts_count" not in {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}:
        pass  # placeholder for future document migrations
