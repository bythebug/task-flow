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


def _register(client, email="alice@example.com", password="password123"):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client, email="alice@example.com", password="password123"):
    return client.post("/auth/login", json={"email": email, "password": password})


# --- register ---

def test_register_endpoint(client):
    res = _register(client)
    assert res.status_code == 201
    data = res.get_json()
    assert "user_id" in data
    assert data["message"] == "Registration successful"


def test_register_duplicate_email(client):
    _register(client)
    res = _register(client)
    assert res.status_code == 409
    assert "already registered" in res.get_json()["error"].lower()


def test_register_invalid_email(client):
    res = _register(client, email="not-an-email")
    assert res.status_code == 400


def test_register_short_password(client):
    res = _register(client, password="short")
    assert res.status_code == 400


# --- login ---

def test_login_endpoint(client):
    _register(client)
    res = _login(client)
    assert res.status_code == 200
    data = res.get_json()
    assert "token" in data
    assert data["expires_in"] == 86400


def test_login_wrong_password(client):
    _register(client)
    res = _login(client, password="wrongpassword")
    assert res.status_code == 401
    assert "Invalid" in res.get_json()["error"]


# --- protected endpoint ---

def test_protected_endpoint_without_token(client):
    res = client.post("/auth/logout")
    assert res.status_code == 401


def test_protected_endpoint_with_invalid_token(client):
    res = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer this.is.invalid"},
    )
    assert res.status_code == 401


# --- logout ---

def test_logout_revokes_token(client):
    _register(client)
    token = _login(client).get_json()["token"]

    res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

    # Same token should now be rejected
    res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
