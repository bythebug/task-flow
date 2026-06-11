import json
import logging
import os

import redis as redis_lib

logger = logging.getLogger(__name__)

_TASK_CACHE_TTL = 300  # 5 minutes
_client: redis_lib.Redis | None = None


def get_client() -> redis_lib.Redis:
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _client = redis_lib.from_url(url, decode_responses=True)
    return _client


def set_client(client) -> None:
    """Inject an alternative Redis client (e.g. fakeredis in tests)."""
    global _client
    _client = client


def _key(user_id: int) -> str:
    return f"tasks:user:{user_id}"


def get_cached_tasks(user_id: int) -> list | None:
    """Return cached task list or None on miss / Redis unavailable."""
    try:
        data = get_client().get(_key(user_id))
        if data is None:
            return None
        logger.debug("cache hit user_id=%s", user_id)
        return json.loads(data)
    except Exception as exc:
        logger.warning("cache read failed: %s", exc)
        return None


def cache_user_tasks(user_id: int, tasks_data: list) -> None:
    """Store serialised task list; silently skips on Redis failure."""
    try:
        get_client().set(_key(user_id), json.dumps(tasks_data), ex=_TASK_CACHE_TTL)
        logger.debug("cache write user_id=%s count=%s", user_id, len(tasks_data))
    except Exception as exc:
        logger.warning("cache write failed: %s", exc)


def invalidate_user_cache(user_id: int) -> None:
    """Delete cached tasks for a user after any mutation."""
    try:
        deleted = get_client().delete(_key(user_id))
        if deleted:
            logger.debug("cache invalidated user_id=%s", user_id)
    except Exception as exc:
        logger.warning("cache invalidation failed: %s", exc)
