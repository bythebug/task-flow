import logging

from flask import Blueprint, g, jsonify, request

from app.auth.service import login, register
from app.config import TOKEN_EXPIRY_HOURS
from app.core.error_handlers import ValidationError
from app.core.middleware import _token_blocklist, handle_errors, require_auth
from app.core.validators import validate_email, validate_password

logger = logging.getLogger(__name__)


def create_auth_blueprint(Session):
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

    return auth_bp
