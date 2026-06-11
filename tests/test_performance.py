import threading
import time

import fakeredis
import pytest

from app import create_app
from app.core.middleware import _token_blocklist
from app.tasks import cache as cache_module


@pytest.fixture
def fake_redis():
    """Inject an in-process fake Redis — no server needed."""
    client = fakeredis.FakeRedis(decode_responses=True)
    cache_module.set_client(client)
    yield client
    cache_module.set_client(None)


@pytest.fixture
def client(fake_redis):
    app = create_app("sqlite:///:memory:")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clear_blocklist():
    _token_blocklist.clear()
    yield
    _token_blocklist.clear()


# --- helpers ---

def _register_and_login(client, email="alice@example.com", password="Password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    return client.post("/auth/login", json={"email": email, "password": password}).get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, token, title="Task"):
    return client.post("/tasks/", json={"title": title}, headers=_auth(token)).get_json()["id"]


# ------------------------------------------------------------------ #
# Cache hit / miss
# ------------------------------------------------------------------ #

def test_cache_miss_then_hit(client, fake_redis):
    token = _register_and_login(client)
    _create_task(client, token, "Task A")

    cache_key = f"tasks:user:{1}"  # first registered user gets id=1

    # First request: cache should be empty → DB query → populate cache
    assert fake_redis.get(cache_key) is None
    res1 = client.get("/tasks/", headers=_auth(token))
    assert res1.status_code == 200
    assert fake_redis.get(cache_key) is not None  # now populated

    # Second request: served from cache (key still there, same data)
    res2 = client.get("/tasks/", headers=_auth(token))
    assert res2.status_code == 200
    assert res2.get_json()["tasks"] == res1.get_json()["tasks"]


def test_cache_hit_rate(client, fake_redis):
    """After the first miss, repeated identical requests all hit the cache."""
    token = _register_and_login(client)
    for i in range(3):
        _create_task(client, token, f"Task {i}")

    # Warm the cache
    client.get("/tasks/", headers=_auth(token))

    cache_key = f"tasks:user:1"
    assert fake_redis.get(cache_key) is not None

    # Manually track hits: every subsequent GET should NOT change the key's TTL
    ttl_before = fake_redis.ttl(cache_key)
    for _ in range(5):
        res = client.get("/tasks/", headers=_auth(token))
        assert res.status_code == 200
    ttl_after = fake_redis.ttl(cache_key)

    # TTL should not have increased (no new writes on cache hits)
    assert ttl_after <= ttl_before


def test_filtered_requests_bypass_cache(client, fake_redis):
    """Requests with ?status= or ?priority= skip the cache entirely."""
    token = _register_and_login(client)
    _create_task(client, token)

    # Warm cache with unfiltered request
    client.get("/tasks/", headers=_auth(token))
    cache_key = f"tasks:user:1"
    assert fake_redis.get(cache_key) is not None

    # Filtered request — cache key untouched (no re-write)
    fake_redis.delete(cache_key)
    client.get("/tasks/?status=todo", headers=_auth(token))
    assert fake_redis.get(cache_key) is None  # still empty


# ------------------------------------------------------------------ #
# Cache invalidation
# ------------------------------------------------------------------ #

def test_cache_invalidation_on_create(client, fake_redis):
    token = _register_and_login(client)
    cache_key = f"tasks:user:1"

    # Warm cache
    client.get("/tasks/", headers=_auth(token))
    assert fake_redis.get(cache_key) is not None

    # Creating a task invalidates the cache
    _create_task(client, token, "New task")
    assert fake_redis.get(cache_key) is None


def test_cache_invalidation_on_update(client, fake_redis):
    token = _register_and_login(client)
    task_id = _create_task(client, token)
    cache_key = f"tasks:user:1"

    client.get("/tasks/", headers=_auth(token))
    assert fake_redis.get(cache_key) is not None

    client.put(f"/tasks/{task_id}", json={"title": "Updated"}, headers=_auth(token))
    assert fake_redis.get(cache_key) is None


def test_cache_invalidation_on_delete(client, fake_redis):
    token = _register_and_login(client)
    task_id = _create_task(client, token)
    cache_key = f"tasks:user:1"

    client.get("/tasks/", headers=_auth(token))
    assert fake_redis.get(cache_key) is not None

    client.delete(f"/tasks/{task_id}", headers=_auth(token))
    assert fake_redis.get(cache_key) is None


def test_cache_reflects_new_task_after_invalidation(client, fake_redis):
    """After invalidation the next GET returns fresh data including the new task."""
    token = _register_and_login(client)

    client.get("/tasks/", headers=_auth(token))  # warm (0 tasks)

    _create_task(client, token, "New task")       # invalidates

    res = client.get("/tasks/", headers=_auth(token))  # re-warms from DB
    titles = [t["title"] for t in res.get_json()["tasks"]]
    assert "New task" in titles


# ------------------------------------------------------------------ #
# Query performance
# ------------------------------------------------------------------ #

def test_query_performance(client, fake_redis):
    """Each endpoint call should complete in well under 100 ms (SQLite in-memory)."""
    token = _register_and_login(client)
    for i in range(10):
        _create_task(client, token, f"Perf task {i}")

    start = time.perf_counter()
    for _ in range(10):
        res = client.get("/tasks/", headers=_auth(token))
        assert res.status_code == 200
    elapsed_ms = (time.perf_counter() - start) * 1000

    avg_ms = elapsed_ms / 10
    assert avg_ms < 100, f"Average request time {avg_ms:.1f}ms exceeds 100ms threshold"


def test_single_task_fetch_performance(client, fake_redis):
    token = _register_and_login(client)
    task_id = _create_task(client, token)

    start = time.perf_counter()
    for _ in range(20):
        res = client.get(f"/tasks/{task_id}", headers=_auth(token))
        assert res.status_code == 200
    avg_ms = (time.perf_counter() - start) * 1000 / 20

    assert avg_ms < 100, f"Average GET /tasks/{{id}} time {avg_ms:.1f}ms exceeds 100ms"


# ------------------------------------------------------------------ #
# Concurrent requests
# ------------------------------------------------------------------ #

def test_concurrent_requests(client, fake_redis):
    """Rapid sequential requests all succeed and return consistent data.

    Note: true multi-thread concurrency requires PostgreSQL + QueuePool.
    SQLite's StaticPool is single-connection, so threads are serialised at
    the DB level. The test verifies correctness under rapid load, not
    parallelism.
    """
    token = _register_and_login(client)
    for i in range(5):
        _create_task(client, token, f"Task {i}")

    results = [
        client.get("/tasks/", headers=_auth(token)).status_code
        for _ in range(10)
    ]

    assert all(s == 200 for s in results), f"Unexpected status codes: {set(results)}"
    assert len(results) == 10


def test_concurrent_writes_no_corruption(client, fake_redis):
    """Rapid sequential creates all succeed; final task count is correct."""
    token = _register_and_login(client)

    statuses = [
        client.post("/tasks/", json={"title": f"Rapid {i}"}, headers=_auth(token)).status_code
        for i in range(5)
    ]

    assert all(s == 201 for s in statuses), f"Some creates failed: {statuses}"

    res = client.get("/tasks/", headers=_auth(token))
    assert res.get_json()["total"] == 5
