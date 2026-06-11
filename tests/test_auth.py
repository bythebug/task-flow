from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth import (
    AuthenticationError,
    EmailAlreadyExistsError,
    TokenError,
    decode_token,
    login,
    register,
)
from config import JWT_ALGORITHM, JWT_SECRET_KEY
from models import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture
def registered_user(session):
    return register(session, "alice@example.com", "password123")


# --- register ---

def test_register_success(session):
    user = register(session, "bob@example.com", "securepass")
    assert user.id is not None
    assert user.email == "bob@example.com"
    assert user.password_hash != "securepass"  # must be hashed


def test_register_duplicate_email(session, registered_user):
    with pytest.raises(EmailAlreadyExistsError):
        register(session, "alice@example.com", "differentpass")


# --- login ---

def test_login_success(session, registered_user):
    token = login(session, "alice@example.com", "password123")
    assert isinstance(token, str)
    assert len(token) > 0


def test_login_wrong_password(session, registered_user):
    with pytest.raises(AuthenticationError):
        login(session, "alice@example.com", "wrongpassword")


def test_login_unknown_email_same_error(session):
    # Must raise the same error as wrong password — no hint that email doesn't exist
    with pytest.raises(AuthenticationError):
        login(session, "nobody@example.com", "password123")


# --- token ---

def test_token_validation(session, registered_user):
    token = login(session, "alice@example.com", "password123")
    user_id = decode_token(token)
    assert user_id == registered_user.id


def test_token_expiration(session, registered_user):
    expired_payload = {
        "sub": registered_user.id,
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=25),
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    with pytest.raises(TokenError, match="expired"):
        decode_token(expired_token)


def test_token_invalid_signature(session):
    with pytest.raises(TokenError):
        decode_token("not.a.valid.token")
