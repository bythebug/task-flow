import pytest

from app import create_app
from middleware import _token_blocklist


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


# --- helpers ---

def _register_and_login(client, email, password="Password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    res = client.post("/auth/login", json={"email": email, "password": password})
    return res.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, headers, title="Buy milk", **kwargs):
    return client.post("/tasks/", json={"title": title, **kwargs}, headers=headers)


# --- create ---

def test_create_task(client):
    token = _register_and_login(client, "alice@example.com")
    res = _create_task(client, _auth(token), title="Write tests", priority="high", status="in_progress")
    assert res.status_code == 201
    data = res.get_json()
    assert data["title"] == "Write tests"
    assert data["priority"] == "high"
    assert data["status"] == "in_progress"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_task_missing_title(client):
    token = _register_and_login(client, "alice@example.com")
    res = client.post("/tasks/", json={"priority": "high"}, headers=_auth(token))
    assert res.status_code == 400


def test_create_task_invalid_status(client):
    token = _register_and_login(client, "alice@example.com")
    res = _create_task(client, _auth(token), status="flying")
    assert res.status_code == 400


# --- list ---

def test_list_tasks(client):
    token = _register_and_login(client, "alice@example.com")
    headers = _auth(token)
    _create_task(client, headers, title="Task 1")
    _create_task(client, headers, title="Task 2")

    res = client.get("/tasks/", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 2
    assert len(data["tasks"]) == 2
    assert "page" in data
    assert "pages" in data


def test_list_tasks_filtered_by_status(client):
    token = _register_and_login(client, "alice@example.com")
    headers = _auth(token)
    _create_task(client, headers, title="Todo task", status="todo")
    _create_task(client, headers, title="Done task", status="done")

    res = client.get("/tasks/?status=todo", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 1
    assert data["tasks"][0]["status"] == "todo"


def test_list_tasks_filtered_by_priority(client):
    token = _register_and_login(client, "alice@example.com")
    headers = _auth(token)
    _create_task(client, headers, title="Urgent task", priority="urgent")
    _create_task(client, headers, title="Low task", priority="low")

    res = client.get("/tasks/?priority=urgent", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["total"] == 1


def test_pagination(client):
    token = _register_and_login(client, "alice@example.com")
    headers = _auth(token)
    for i in range(5):
        _create_task(client, headers, title=f"Task {i}")

    res = client.get("/tasks/?page=1&limit=2", headers=headers)
    data = res.get_json()
    assert res.status_code == 200
    assert len(data["tasks"]) == 2
    assert data["total"] == 5
    assert data["pages"] == 3

    res2 = client.get("/tasks/?page=3&limit=2", headers=headers)
    assert len(res2.get_json()["tasks"]) == 1


# --- get single ---

def test_get_task(client):
    token = _register_and_login(client, "alice@example.com")
    headers = _auth(token)
    task_id = _create_task(client, headers, title="Single task").get_json()["id"]

    res = client.get(f"/tasks/{task_id}", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["id"] == task_id


def test_get_nonexistent_task(client):
    token = _register_and_login(client, "alice@example.com")
    res = client.get("/tasks/9999", headers=_auth(token))
    assert res.status_code == 404


# --- update ---

def test_update_task(client):
    token = _register_and_login(client, "alice@example.com")
    headers = _auth(token)
    task_id = _create_task(client, headers, title="Old title").get_json()["id"]

    res = client.put(
        f"/tasks/{task_id}",
        json={"title": "New title", "status": "done"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "done"


def test_update_task_empty_title(client):
    token = _register_and_login(client, "alice@example.com")
    headers = _auth(token)
    task_id = _create_task(client, headers).get_json()["id"]

    res = client.put(f"/tasks/{task_id}", json={"title": ""}, headers=headers)
    assert res.status_code == 400


# --- delete ---

def test_delete_task(client):
    token = _register_and_login(client, "alice@example.com")
    headers = _auth(token)
    task_id = _create_task(client, headers, title="To delete").get_json()["id"]

    res = client.delete(f"/tasks/{task_id}", headers=headers)
    assert res.status_code == 200

    res = client.get(f"/tasks/{task_id}", headers=headers)
    assert res.status_code == 404


# --- authorization ---

def test_unauthorized_access(client):
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")

    task_id = _create_task(client, _auth(token_a), title="Alice's secret").get_json()["id"]

    # Bob tries to read, update, and delete Alice's task
    assert client.get(f"/tasks/{task_id}", headers=_auth(token_b)).status_code == 403
    assert client.put(f"/tasks/{task_id}", json={"title": "Hacked"}, headers=_auth(token_b)).status_code == 403
    assert client.delete(f"/tasks/{task_id}", headers=_auth(token_b)).status_code == 403


def test_list_tasks_isolation(client):
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")

    _create_task(client, _auth(token_a), title="Alice task")
    _create_task(client, _auth(token_b), title="Bob task")

    res = client.get("/tasks/", headers=_auth(token_a))
    tasks = res.get_json()["tasks"]
    assert all(t["title"] == "Alice task" for t in tasks)
    assert res.get_json()["total"] == 1
