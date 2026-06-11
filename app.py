import logging
import os

from flask import Blueprint, Flask, g, jsonify, request
from sqlalchemy.orm import scoped_session, sessionmaker

from auth import login, register
from config import TOKEN_EXPIRY_HOURS
from database import create_engine_with_pool
from error_handlers import ValidationError, register_error_handlers
from middleware import _token_blocklist, handle_errors, require_auth
from models import Base
from tasks import create_tasks_blueprint
from validators import validate_email, validate_password

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(database_url: str | None = None) -> Flask:
    app = Flask(__name__)

    db_url = database_url or os.getenv("DATABASE_URL", "sqlite:///taskflow.db")
    engine = create_engine_with_pool(db_url)

    Base.metadata.create_all(engine)
    Session = scoped_session(sessionmaker(bind=engine))

    register_error_handlers(app)

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
        email = validate_email(data.get("email"))
        password = validate_password(data.get("password"))

        user = register(Session, email, password)
        logger.info("register success email=%s user_id=%s", email, user.id)
        return jsonify({"user_id": user.id, "message": "Registration successful"}), 201

    @auth_bp.route("/login", methods=["POST"])
    @handle_errors
    def login_endpoint():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        if not email or not password:
            raise ValidationError({"email": "Email and password are required"})

        token = login(Session, email, password)
        logger.info("login success email=%s", email)
        return jsonify({"token": token, "expires_in": TOKEN_EXPIRY_HOURS * 3600}), 200

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
