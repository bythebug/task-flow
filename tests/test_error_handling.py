from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from app import create_app
from app.core.middleware import _token_blocklist


@pytest.fixture
def client():
    app = create_app("sqlite:///:memory:")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clear_blocklist():
    _token_blocklist.clear()
    yield
    _token_blocklist.clear()


def _register_and_login(client, email="alice@example.com", password="Password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    return client.post("/auth/login", json={"email": email, "password": password}).get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, token, title="Test task"):
    return client.post("/tasks/", json={"title": title}, headers=_auth(token)).get_json()["id"]


# --- input validation ---

def test_invalid_email_format(client):
    for bad_email in ["notanemail", "missing@", "@nodomain", "two@@at.com", ""]:
        res = client.post("/auth/register", json={"email": bad_email, "password": "Password123"})
        assert res.status_code == 400, f"Expected 400 for email={bad_email!r}"
        body = res.get_json()
        assert "errors" in body
        assert "email" in body["errors"]


def test_weak_password(client):
    cases = [
        ("short", "too short"),
        ("alllowercase1", "no uppercase"),
        ("ALLUPPERCASE1", "no lowercase"),
        ("NoDigitsHere", "no digit"),
        ("", "empty"),
    ]
    for password, reason in cases:
        res = client.post("/auth/register", json={"email": "test@example.com", "password": password})
        assert res.status_code == 400, f"Expected 400 for password={password!r} ({reason})"
        body = res.get_json()
        assert "errors" in body
        assert "password" in body["errors"]


def test_missing_required_fields(client):
    token = _register_and_login(client)

    # No body at all
    res = client.post("/tasks/", json={}, headers=_auth(token))
    assert res.status_code == 400
    assert "errors" in res.get_json()
    assert "title" in res.get_json()["errors"]

    # Empty title
    res = client.post("/tasks/", json={"title": "   "}, headers=_auth(token))
    assert res.status_code == 400

    # Login with missing fields
    res = client.post("/auth/login", json={"email": "alice@example.com"})
    assert res.status_code == 400


def test_invalid_task_status(client):
    token = _register_and_login(client)

    res = client.post("/tasks/", json={"title": "Task", "status": "flying"}, headers=_auth(token))
    assert res.status_code == 400
    body = res.get_json()
    assert "errors" in body
    assert "status" in body["errors"]


def test_invalid_task_priority(client):
    token = _register_and_login(client)

    res = client.post("/tasks/", json={"title": "Task", "priority": "critical"}, headers=_auth(token))
    assert res.status_code == 400
    body = res.get_json()
    assert "errors" in body
    assert "priority" in body["errors"]


def test_multiple_validation_errors(client):
    token = _register_and_login(client)

    res = client.post(
        "/tasks/",
        json={"title": "", "status": "invalid", "priority": "invalid"},
        headers=_auth(token),
    )
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert "title" in errors
    assert "status" in errors
    assert "priority" in errors


# --- database error ---

def test_database_connection_error(client):
    token = _register_and_login(client)
    task_id = _create_task(client, token)

    # Task exists; simulate DB failing inside check_permission
    with patch("app.tasks.service.check_permission", side_effect=OperationalError("DB down", None, None)):
        res = client.get(f"/tasks/{task_id}", headers=_auth(token))

    assert res.status_code == 500
    assert "error" in res.get_json()


# --- concurrent modification ---

def test_concurrent_modification(client):
    """Rapid sequential updates to the same task both succeed (last-write-wins).
    No data corruption — the final state reflects the last write."""
    token = _register_and_login(client)
    task_id = _create_task(client, token, "Original title")

    res1 = client.put(f"/tasks/{task_id}", json={"title": "Update one"}, headers=_auth(token))
    res2 = client.put(f"/tasks/{task_id}", json={"title": "Update two"}, headers=_auth(token))

    assert res1.status_code == 200
    assert res2.status_code == 200

    final = client.get(f"/tasks/{task_id}", headers=_auth(token)).get_json()
    assert final["title"] == "Update two"


# --- sanitize_input ---

def test_control_characters_stripped(client):
    token = _register_and_login(client)

    # Null byte and other control chars should be stripped silently
    res = client.post(
        "/tasks/",
        json={"title": "Hello\x00World", "description": "Clean\x07text"},
        headers=_auth(token),
    )
    assert res.status_code == 201
    data = res.get_json()
    assert "\x00" not in data["title"]
    assert data["title"] == "HelloWorld"


# --- error response shape ---

def test_error_response_has_error_key(client):
    """Every error response must include an 'error' key for consistent client handling."""
    cases = [
        client.post("/auth/register", json={"email": "bad", "password": "Password123"}),
        client.post("/auth/login", json={"email": "nobody@x.com", "password": "Password123"}),
        client.get("/tasks/9999", headers=_auth(_register_and_login(client))),
    ]
    for res in cases:
        assert "error" in res.get_json(), f"Missing 'error' key in: {res.get_json()}"
