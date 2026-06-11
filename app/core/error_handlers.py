import logging

from flask import jsonify
from sqlalchemy.exc import OperationalError, SQLAlchemyError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for all application-level exceptions.

    Subclasses propagate through @handle_errors to Flask error handlers
    instead of being swallowed as 500s.
    """
    pass


class ValidationError(AppError):
    def __init__(self, errors: dict[str, str] | str):
        self.errors = errors if isinstance(errors, dict) else {"_": errors}
        super().__init__(str(self.errors))


class DatabaseError(AppError):
    pass


def error_json(message: str, **extra) -> dict:
    return {"error": message, **extra}


def register_error_handlers(app) -> None:
    from app.auth.service import AuthenticationError, EmailAlreadyExistsError, TokenError
    from app.tasks.service import PermissionDeniedError, TaskNotFoundError, UserNotFoundError

    app.register_error_handler(
        ValidationError,
        lambda e: (jsonify({"error": "Validation failed", "errors": e.errors}), 400),
    )
    app.register_error_handler(
        AuthenticationError,
        lambda e: (jsonify(error_json(str(e) or "Authentication failed")), 401),
    )
    app.register_error_handler(
        TokenError,
        lambda e: (jsonify(error_json(str(e))), 401),
    )
    app.register_error_handler(
        PermissionDeniedError,
        lambda e: (jsonify(error_json(str(e) or "Access denied")), 403),
    )
    app.register_error_handler(
        TaskNotFoundError,
        lambda e: (jsonify(error_json(str(e) or "Task not found")), 404),
    )
    app.register_error_handler(
        UserNotFoundError,
        lambda e: (jsonify(error_json(str(e) or "User not found")), 404),
    )
    app.register_error_handler(
        EmailAlreadyExistsError,
        lambda e: (jsonify(error_json("Email already registered")), 409),
    )

    def handle_db_error(e):
        logger.error("Database error: %s", e)
        return jsonify(error_json("Database error")), 500

    app.register_error_handler(OperationalError, handle_db_error)
    app.register_error_handler(SQLAlchemyError, handle_db_error)
    app.register_error_handler(DatabaseError, handle_db_error)
