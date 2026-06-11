import functools
import logging

from flask import g, jsonify, request

from app.auth.service import TokenError, decode_token
from app.core.error_handlers import AppError

logger = logging.getLogger(__name__)

_token_blocklist: set[str] = set()


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ", 1)[1]

        if token in _token_blocklist:
            return jsonify({"error": "Token has been revoked"}), 401

        try:
            g.user_id = decode_token(token)
        except TokenError as e:
            return jsonify({"error": str(e)}), 401

        return f(*args, **kwargs)

    return decorated


def handle_errors(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except AppError:
            raise
        except Exception:
            logger.exception("Unhandled exception in %s", f.__name__)
            return jsonify({"error": "Internal server error"}), 500

    return decorated


def check_task_access(session, task_id: int, user_id: int, required_level):
    """Return an error response tuple if access is denied, None if granted."""
    from app.models import Task
    from app.tasks.service import check_permission

    task = session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    if not check_permission(session, task_id, user_id, required_level):
        return jsonify({"error": "Access denied"}), 403
    return None
