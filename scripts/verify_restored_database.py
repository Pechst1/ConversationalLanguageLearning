"""Verify a restore in a database created by restore_drill.sh; print no content."""
from __future__ import annotations

import argparse
from pathlib import Path

import psycopg2
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg2 import sql

CRITICAL_COLUMNS = {
    "users": {"id", "email", "hashed_password", "auth_version"},
    "refresh_tokens": {"id", "user_id", "token_hash", "revoked_at"},
    "password_reset_deliveries": {"id", "user_id", "status", "encrypted_payload"},
    "user_vocabulary_progress": {"id", "user_id", "word_id"},
    "review_logs": {"id", "progress_id"},
    "daily_journeys": {"id", "user_id"},
    "daily_journey_steps": {"id", "journey_id"},
}
RELATIONS = (
    ("refresh_tokens", "user_id", "users"),
    ("password_reset_deliveries", "user_id", "users"),
    ("user_vocabulary_progress", "user_id", "users"),
    ("review_logs", "progress_id", "user_vocabulary_progress"),
    ("daily_journeys", "user_id", "users"),
    ("daily_journey_steps", "journey_id", "daily_journeys"),
)


def expected_heads() -> set[str]:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    return set(ScriptDirectory.from_config(config).get_heads())


def verify(connection, *, heads: set[str]) -> dict[str, int]:
    """Require the shipped schema, usable core tables and intact ownership links."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT version_num FROM public.alembic_version")
        current = {row[0] for row in cursor.fetchall()}
        if current != heads:
            raise ValueError(f"Restore schema mismatch: found {sorted(current)}, expected {sorted(heads)}")
        cursor.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'")
        columns: dict[str, set[str]] = {}
        for table, column in cursor.fetchall():
            columns.setdefault(table, set()).add(column)
        for table, required in CRITICAL_COLUMNS.items():
            missing = required - columns.get(table, set())
            if missing:
                raise ValueError(f"Restore is missing {table} columns: {sorted(missing)}")
        for child, fk, parent in RELATIONS:
            cursor.execute(sql.SQL(
                "SELECT count(*) FROM public.{} c LEFT JOIN public.{} p ON c.{} = p.id "
                "WHERE c.{} IS NOT NULL AND p.id IS NULL"
            ).format(sql.Identifier(child), sql.Identifier(parent), sql.Identifier(fk), sql.Identifier(fk)))
            if cursor.fetchone()[0]:
                raise ValueError(f"Restore has orphaned rows in {child}")
        counts = {}
        for table in sorted(columns):
            # Views are deliberately excluded; a broken view is not a dump row.
            cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s AND table_type = 'BASE TABLE'", (table,))
            if cursor.fetchone():
                cursor.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table)))
                counts[table] = cursor.fetchone()[0]
        return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    args = parser.parse_args()
    if not args.database.startswith("wp73_drill_"):
        parser.error("only a database created by restore_drill.sh may be verified")
    # libpq uses PGHOST/PGPORT/PGUSER/PGPASSWORD. Never loads the app's .env.
    with psycopg2.connect(dbname=args.database) as connection:
        counts = verify(connection, heads=expected_heads())
    for table, count in counts.items():
        print(f"{table}: {count}")
    print("Restore verified: migration heads, required columns and ownership links are intact.")


if __name__ == "__main__":
    main()
