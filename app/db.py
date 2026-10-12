from contextlib import asynccontextmanager
from psycopg_pool import ConnectionPool

from app.core.config import get_settings


settings = get_settings()
pool = ConnectionPool(
    conninfo="",
    kwargs=settings.database_kwargs,
    min_size=1,
    max_size=5,
    open=False,
)


def open_pool() -> None:
    pool.open(wait=True)


def close_pool() -> None:
    pool.close()


@asynccontextmanager
async def get_connection():
    with pool.connection() as conn:
        yield conn
