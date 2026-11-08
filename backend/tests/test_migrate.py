"""The migration command, on a throwaway Postgres that starts with nothing."""

from collections.abc import Iterator

import psycopg
import pytest

from backend import migrate

NAMES = [path.name for path in migrate.files()]


@pytest.fixture
def blank(postgres_url) -> Iterator[str]:
    """A new, empty database beside the shared one."""
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("drop database if exists blank")
        conn.execute("create database blank")
    yield postgres_url.rsplit("/", 1)[0] + "/blank"
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("drop database blank with (force)")


def test_the_migrations_run_in_order_once(blank):
    with psycopg.connect(blank, autocommit=True) as conn:
        assert migrate.apply(conn) == NAMES
        assert migrate.apply(conn) == []
        kind = conn.execute(
            "select data_type from information_schema.columns"
            " where table_name = 'decisions' and column_name = 'retrieved'"
        ).fetchone()
    assert kind == ("jsonb",)


def test_a_file_applied_by_hand_can_be_recorded(blank):
    with psycopg.connect(blank, autocommit=True) as conn:
        conn.execute(migrate.files()[0].read_text().encode())
        migrate.record(conn, NAMES[0])
        assert migrate.apply(conn) == NAMES[1:]


def test_an_unknown_file_cannot_be_recorded(blank):
    with psycopg.connect(blank, autocommit=True) as conn, pytest.raises(SystemExit):
        migrate.record(conn, "nothing.sql")


def test_the_ledger_is_closed_to_the_public_key(blank):
    with psycopg.connect(blank, autocommit=True) as conn:
        migrate.apply(conn)
        (secured,) = conn.execute(
            "select relrowsecurity from pg_class where relname = 'schema_migrations'"
        ).fetchone() or (None,)
    assert secured is True


def test_the_command_needs_a_database(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    with pytest.raises(SystemExit, match="SUPABASE_DB_URL"):
        migrate.main([])


def test_the_command_records_applies_and_reports(blank, monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_DB_URL", blank)
    migrate.main(["--record", NAMES[0]])
    assert f"Recorded {NAMES[0]}" in capsys.readouterr().out
    with psycopg.connect(blank, autocommit=True) as conn:
        conn.execute(migrate.files()[0].read_text().encode())
    migrate.main([])
    assert f"Applied {NAMES[1]}" in capsys.readouterr().out
    migrate.main([])
    assert "Nothing to apply." in capsys.readouterr().out
