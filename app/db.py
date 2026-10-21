from contextlib import asynccontextmanager

from psycopg_pool import ConnectionPool

from app.core.config import get_settings

settings = get_settings()
pool = ConnectionPool(
    conninfo="",
    min_size=0,
    max_size=10,
    timeout=10,
    kwargs={**settings.database_kwargs, "connect_timeout": 8, "prepare_threshold": None},
    open=False,
)


def open_pool() -> None:
    """Start the connection pool without blocking API startup on PostgreSQL."""
    if pool.closed:
        pool.open(wait=False)


def close_pool() -> None:
    """Close the pool only if it is currently open."""
    if not pool.closed:
        pool.close()


@asynccontextmanager
async def get_connection():
    with pool.connection() as conn:
        yield conn
