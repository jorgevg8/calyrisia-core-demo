from contextlib import asynccontextmanager
from psycopg_pool import ConnectionPool

from app.core.config import get_settings


settings = get_settings()
pool = ConnectionPool(
    conninfo="",
    kwargs=settings.database_kwargs,
    min_size=0,
    max_size=10,
    open=False,
)


def open_pool() -> None:
    try:
        pool.open(wait=False)
    except Exception:
        pass


def close_pool() -> None:
    try:
        pool.close()
    except Exception:
        pass


@asynccontextmanager
async def get_connection():
    with pool.connection() as conn:
        yield conn
