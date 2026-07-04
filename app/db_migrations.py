import os
import re
import glob
import logging
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations')


def _split_statements(sql_content):
    """Split SQL file into individual executable statements.
    Handles DO $$ ... $$; dollar-quoted blocks and plain SQL."""
    if '$$;' in sql_content:
        parts = re.split(r'(?<=\$\$;)', sql_content)
        return [p.strip() for p in parts if p.strip()]
    parts = sql_content.split(';')
    return [p.strip() + ';' for p in parts if p.strip()]


def run_migrations(db):
    is_postgres = db.engine.dialect.name == 'postgresql'
    with db.engine.connect() as conn:
        if is_postgres:
            conn.execute(text("SELECT pg_advisory_lock(202406191)"))
        try:
            if is_postgres:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename   VARCHAR(255) PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT NOW()
                    )
                """))
            else:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename   VARCHAR(255) PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
            conn.commit()

            result = conn.execute(text("SELECT filename FROM schema_migrations"))
            applied = {row[0] for row in result}

            sql_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, '*.sql')))
            for filepath in sql_files:
                filename = os.path.basename(filepath)
                if filename in applied:
                    continue
                logger.info("Running migration: %s", filename)
                if is_postgres:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    for stmt in _split_statements(content):
                        conn.execute(text(stmt))
                try:
                    conn.execute(
                        text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
                        {"f": filename},
                    )
                    conn.commit()
                    logger.info("Migration applied: %s", filename)
                except IntegrityError:
                    # Another worker already recorded this migration
                    conn.rollback()
        finally:
            if is_postgres:
                conn.execute(text("SELECT pg_advisory_unlock(202406191)"))
