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
    return client.post("/auth/login", json={"email": email, "password": password}).get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, token, title="Shared task"):
    res = client.post("/tasks/", json={"title": title}, headers=_auth(token))
    return res.get_json()["id"]


def _share(client, token, task_id, email, level="view"):
    return client.post(
        f"/tasks/{task_id}/share",
        json={"email": email, "permission_level": level},
        headers=_auth(token),
    )


# --- share ---

def test_share_task_with_user(client):
    alice = _register_and_login(client, "alice@example.com")
    _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice)

    res = _share(client, alice, task_id, "bob@example.com", "view")
    assert res.status_code == 200
    data = res.get_json()
    assert data["permission_level"] == "view"
    assert "user_id" in data


def test_share_nonexistent_user(client):
    alice = _register_and_login(client, "alice@example.com")
    task_id = _create_task(client, alice)

    res = _share(client, alice, task_id, "nobody@example.com")
    assert res.status_code == 404


def test_share_with_owner_is_rejected(client):
    alice = _register_and_login(client, "alice@example.com")
    task_id = _create_task(client, alice)

    res = _share(client, alice, task_id, "alice@example.com")
    assert res.status_code == 403


def test_non_owner_cannot_share(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    _register_and_login(client, "carol@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "bob@example.com", "view")

    # Bob only has view — cannot share with Carol
    res = _share(client, bob, task_id, "carol@example.com", "view")
    assert res.status_code == 403


# --- view permission ---

def test_view_shared_task(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice, title="Alice's task")

    _share(client, alice, task_id, "bob@example.com", "view")

    res = client.get(f"/tasks/{task_id}", headers=_auth(bob))
    assert res.status_code == 200
    assert res.get_json()["title"] == "Alice's task"


def test_cannot_view_unshared_task(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice)

    res = client.get(f"/tasks/{task_id}", headers=_auth(bob))
    assert res.status_code == 403


# --- edit permission ---

def test_edit_shared_task_with_edit_permission(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "bob@example.com", "edit")

    res = client.put(f"/tasks/{task_id}", json={"title": "Bob edited this"}, headers=_auth(bob))
    assert res.status_code == 200
    assert res.get_json()["title"] == "Bob edited this"


def test_cannot_edit_shared_task_with_view_only(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "bob@example.com", "view")

    res = client.put(f"/tasks/{task_id}", json={"title": "Trying to edit"}, headers=_auth(bob))
    assert res.status_code == 403


# --- delete permission ---

def test_cannot_delete_task_with_edit_permission(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "bob@example.com", "edit")

    res = client.delete(f"/tasks/{task_id}", headers=_auth(bob))
    assert res.status_code == 403


def test_delete_task_with_delete_permission(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "bob@example.com", "delete")

    res = client.delete(f"/tasks/{task_id}", headers=_auth(bob))
    assert res.status_code == 200


# --- revoke ---

def test_revoke_access(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "bob@example.com", "view")
    assert client.get(f"/tasks/{task_id}", headers=_auth(bob)).status_code == 200

    bob_id = client.get(f"/tasks/{task_id}/collaborators", headers=_auth(alice)).get_json()["collaborators"][0]["user_id"]
    res = client.delete(f"/tasks/{task_id}/share/{bob_id}", headers=_auth(alice))
    assert res.status_code == 200

    assert client.get(f"/tasks/{task_id}", headers=_auth(bob)).status_code == 403


# --- update permission ---

def test_update_permission_level(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "bob@example.com", "view")
    bob_id = client.get(f"/tasks/{task_id}/collaborators", headers=_auth(alice)).get_json()["collaborators"][0]["user_id"]

    # Upgrade Bob to edit
    res = client.put(
        f"/tasks/{task_id}/permissions/{bob_id}",
        json={"permission_level": "edit"},
        headers=_auth(alice),
    )
    assert res.status_code == 200

    # Bob can now edit
    assert client.put(f"/tasks/{task_id}", json={"title": "Edited"}, headers=_auth(bob)).status_code == 200


# --- collaborators ---

def test_list_collaborators(client):
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    _register_and_login(client, "carol@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "bob@example.com", "view")
    _share(client, alice, task_id, "carol@example.com", "edit")

    res = client.get(f"/tasks/{task_id}/collaborators", headers=_auth(alice))
    assert res.status_code == 200
    collaborators = res.get_json()["collaborators"]
    assert len(collaborators) == 2
    emails = {c["email"] for c in collaborators}
    assert emails == {"bob@example.com", "carol@example.com"}


# --- permission levels ---

def test_permission_levels(client):
    alice = _register_and_login(client, "alice@example.com")
    viewer = _register_and_login(client, "viewer@example.com")
    editor = _register_and_login(client, "editor@example.com")
    deleter = _register_and_login(client, "deleter@example.com")
    task_id = _create_task(client, alice)

    _share(client, alice, task_id, "viewer@example.com", "view")
    _share(client, alice, task_id, "editor@example.com", "edit")
    _share(client, alice, task_id, "deleter@example.com", "delete")

    # view: can read, cannot write or delete
    assert client.get(f"/tasks/{task_id}", headers=_auth(viewer)).status_code == 200
    assert client.put(f"/tasks/{task_id}", json={"title": "x"}, headers=_auth(viewer)).status_code == 403
    assert client.delete(f"/tasks/{task_id}", headers=_auth(viewer)).status_code == 403

    # edit: can read and write, cannot delete
    assert client.get(f"/tasks/{task_id}", headers=_auth(editor)).status_code == 200
    assert client.put(f"/tasks/{task_id}", json={"title": "edited"}, headers=_auth(editor)).status_code == 200
    assert client.delete(f"/tasks/{task_id}", headers=_auth(editor)).status_code == 403

    # delete: full access
    assert client.get(f"/tasks/{task_id}", headers=_auth(deleter)).status_code == 200
    assert client.put(f"/tasks/{task_id}", json={"title": "deleter edit"}, headers=_auth(deleter)).status_code == 200
    assert client.delete(f"/tasks/{task_id}", headers=_auth(deleter)).status_code == 200
