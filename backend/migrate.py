"""Apply the Supabase migrations that haven't been applied yet.

    uv run -m backend.migrate
    uv run -m backend.migrate --record 20261108120000_system_of_record.sql

Each file in `supabase/migrations/` runs once, in name order, in its own transaction,
and is recorded in `schema_migrations`. A second run changes nothing. `--record` marks a
file applied without running it, for one that was applied by hand.

LangGraph's checkpoint tables are created by LangGraph's own migrations, then closed to
Supabase's public API like every other table.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import LiteralString, cast

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import sql
from psycopg.rows import DictRow, dict_row

from agent import config

MIGRATIONS_DIR = config.ROOT / "supabase" / "migrations"

LEDGER = """
create table if not exists schema_migrations (
  name text primary key,
  applied_at timestamptz not null default now()
);
alter table schema_migrations enable row level security;
"""


def files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def applied(conn: psycopg.Connection) -> set[str]:
    conn.execute(LEDGER)
    return {row[0] for row in conn.execute("select name from schema_migrations")}


def pending(conn: psycopg.Connection) -> list[Path]:
    done = applied(conn)
    return [path for path in files() if path.name not in done]


def apply(conn: psycopg.Connection) -> list[str]:
    """Run each pending file with its record, so a failed file leaves no trace."""
    names = []
    for path in pending(conn):
        with conn.transaction():
            # The files are ours, from the repository, never from a user.
            conn.execute(cast(LiteralString, path.read_text()))
            conn.execute(
                "insert into schema_migrations (name) values (%s)", [path.name]
            )
        names.append(path.name)
    return names


CHECKPOINT_TABLES = (
    "checkpoint_migrations",
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
)


def checkpoint_tables(url: str) -> None:
    """Create or update LangGraph's tables, and turn row-level security on."""
    with psycopg.Connection[DictRow].connect(
        url, autocommit=True, row_factory=dict_row
    ) as conn:
        PostgresSaver(conn).setup()
        for table in CHECKPOINT_TABLES:
            conn.execute(
                sql.SQL("alter table {} enable row level security").format(
                    sql.Identifier(table)
                )
            )


def record(conn: psycopg.Connection, name: str) -> None:
    if name not in {path.name for path in files()}:
        raise SystemExit(f"No migration called {name} in {MIGRATIONS_DIR}.")
    applied(conn)
    conn.execute(
        "insert into schema_migrations (name) values (%s) on conflict do nothing",
        [name],
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Apply the Supabase migrations.")
    parser.add_argument("--record", metavar="FILE", help="mark a file applied")
    args = parser.parse_args(argv)
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        raise SystemExit("Set SUPABASE_DB_URL in .env first.")
    with psycopg.connect(url, autocommit=True) as conn:
        if args.record:
            record(conn, args.record)
            print(f"Recorded {args.record} as applied.")
            return
        names = apply(conn)
    checkpoint_tables(url)
    print("\n".join(f"Applied {name}" for name in names) or "Nothing to apply.")
    print("LangGraph's checkpoint tables are ready.")


if __name__ == "__main__":
    main(sys.argv[1:])
