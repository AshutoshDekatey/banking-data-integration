import os

from psycopg.conninfo import make_conninfo


def dsn(database: str) -> str:
    prefix = database.upper()
    return make_conninfo(
        host=os.environ.get(f"{prefix}_HOST", database),
        port=os.environ.get(f"{prefix}_PORT", "5432"),
        user="bank",
        dbname=database,
        password=os.environ[f"{prefix}_PASSWORD"],
        connect_timeout=4,
        options="-c statement_timeout=10000 -c lock_timeout=5000 -c timezone=UTC",
    )
