"""A throwaway Postgres 17 for the store's tests, never Supabase.

It starts once per test run in Docker, with the migrations applied, and every test
starts from empty tables.
"""

from collections.abc import Iterator

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer

from backend import migrate
from backend.store import MemoryStore, PostgresStore, Store


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver=None) as container:
        url = container.get_connection_url()
        with psycopg.connect(url, autocommit=True) as conn:
            migrate.apply(conn)
        yield url


@pytest.fixture
def empty_postgres(postgres_url: str) -> str:
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute(
            "truncate events, reviews, decisions, tickets, batches"
            " restart identity cascade"
        )
    return postgres_url


@pytest.fixture
def postgres_store(empty_postgres: str) -> Iterator[PostgresStore]:
    store = PostgresStore(empty_postgres)
    yield store
    store.close()


@pytest.fixture(params=["memory", "postgres"])
def store(request: pytest.FixtureRequest) -> Store:
    """Each test of the store runs against both versions, which must agree."""
    if request.param == "memory":
        return MemoryStore()
    return request.getfixturevalue("postgres_store")
