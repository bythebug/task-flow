from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

from config import JWT_ALGORITHM, JWT_SECRET_KEY, TOKEN_EXPIRY_HOURS
from models import User


class EmailAlreadyExistsError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class TokenError(Exception):
    pass


# --- password helpers ---

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# --- auth functions ---

def register(session: Session, email: str, password: str) -> User:
    if session.query(User).filter_by(email=email).first():
        raise EmailAlreadyExistsError(f"Email already registered")

    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login(session: Session, email: str, password: str) -> str:
    user = session.query(User).filter_by(email=email).first()

    # Always run bcrypt even when user is not found to prevent timing attacks
    # that could reveal whether an email exists in the database.
    dummy_hash = "$2b$12$KIXtTnKQMmkNqGBFjmRzZuXyI4Y0e8WfI/7CvQjxQZfQjxQjxQjxQ"
    check_hash = user.password_hash if user else dummy_hash

    if not verify_password(password, check_hash) or not user:
        raise AuthenticationError("Invalid email or password")

    payload = {
        "sub": str(user.id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise TokenError("Token has expired")
    except jwt.InvalidTokenError:
        raise TokenError("Invalid token")
