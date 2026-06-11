import logging
import os
import re

from flask import Blueprint, Flask, g, jsonify, request
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from auth import AuthenticationError, EmailAlreadyExistsError, login, register
from config import TOKEN_EXPIRY_HOURS
from middleware import _token_blocklist, handle_errors, require_auth
from models import Base
from tasks import create_tasks_blueprint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_register_body(data: dict) -> tuple[str, str, list[str]]:
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    errors: list[str] = []
    if not _EMAIL_RE.match(email):
        errors.append("A valid email address is required.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    return email, password, errors


def create_app(database_url: str | None = None) -> Flask:
    app = Flask(__name__)

    db_url = database_url or os.getenv("DATABASE_URL", "sqlite:///taskflow.db")

    # StaticPool keeps a single in-memory SQLite connection alive across
    # all requests — required so test fixtures and request handlers share
    # the same database rather than each getting an empty one.
    if db_url == "sqlite:///:memory:":
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(db_url)

    Base.metadata.create_all(engine)
    Session = scoped_session(sessionmaker(bind=engine))

    @app.teardown_appcontext
    def shutdown_session(exception: BaseException | None = None) -> None:
        Session.remove()

    # ------------------------------------------------------------------ #
    # Auth blueprint
    # ------------------------------------------------------------------ #
    auth_bp = Blueprint("auth", __name__)

    @auth_bp.route("/register", methods=["POST"])
    @handle_errors
    def register_endpoint():
        data = request.get_json(silent=True) or {}
        email, password, errors = _validate_register_body(data)
        if errors:
            return jsonify({"error": errors[0]}), 400

        try:
            user = register(Session, email, password)
            logger.info("register success email=%s user_id=%s", email, user.id)
            return jsonify({"user_id": user.id, "message": "Registration successful"}), 201
        except EmailAlreadyExistsError:
            logger.warning("register failed duplicate email=%s", email)
            return jsonify({"error": "Email already registered"}), 409

    @auth_bp.route("/login", methods=["POST"])
    @handle_errors
    def login_endpoint():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        try:
            token = login(Session, email, password)
            logger.info("login success email=%s", email)
            return jsonify({"token": token, "expires_in": TOKEN_EXPIRY_HOURS * 3600}), 200
        except AuthenticationError:
            logger.warning("login failed email=%s", email)
            return jsonify({"error": "Invalid email or password"}), 401

    @auth_bp.route("/logout", methods=["POST"])
    @require_auth
    @handle_errors
    def logout_endpoint():
        token = request.headers["Authorization"].split(" ", 1)[1]
        _token_blocklist.add(token)
        logger.info("logout user_id=%s", g.user_id)
        return jsonify({"message": "Logged out successfully"}), 200

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(create_tasks_blueprint(Session), url_prefix="/tasks")

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
