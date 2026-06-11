import logging
import time
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)


def create_engine_with_pool(db_url: str):
    """Return a SQLAlchemy engine tuned for the target database.

    SQLite (tests / local dev): StaticPool so all requests share one
    in-memory connection.

    PostgreSQL (production): QueuePool with sane defaults and
    pool_pre_ping so stale connections are recycled before use.
    """
    if db_url == "sqlite:///:memory:":
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    kwargs = {}
    if db_url.startswith("postgresql"):
        kwargs = {
            "pool_size": 10,        # baseline connections kept open
            "max_overflow": 20,     # extra connections allowed under load
            "pool_timeout": 30,     # seconds to wait for a free connection
            "pool_recycle": 1800,   # recycle connections after 30 min
            "pool_pre_ping": True,  # test connection liveness before use
        }

    engine = create_engine(db_url, **kwargs)
    _register_slow_query_logger(engine)
    return engine


def _register_slow_query_logger(engine) -> None:
    """Log any query that takes longer than 200 ms."""
    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, params, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, params, context, executemany):
        elapsed_ms = (time.perf_counter() - conn.info["query_start_time"].pop()) * 1000
        if elapsed_ms > 200:
            logger.warning("slow query %.1fms: %.120s", elapsed_ms, statement)


@contextmanager
def timed_query(label: str):
    """Context manager that logs how long the block takes.

    Usage::

        with timed_query("list_tasks"):
            tasks = session.query(Task).all()
    """
    start = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("query [%s] %.1fms", label, elapsed_ms)


def explain_query(session, query):
    """Return the query plan for a SQLAlchemy query (PostgreSQL only).

    Example::

        plan = explain_query(session, session.query(Task).filter_by(user_id=1))
        print(plan)

    On SQLite this silently returns None — use EXPLAIN QUERY PLAN manually.
    """
    dialect = session.bind.dialect.name
    if dialect != "postgresql":
        return None

    sql = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
    result = session.execute(text(f"EXPLAIN ANALYZE {sql}"))
    return "\n".join(row[0] for row in result)
