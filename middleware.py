import functools
import logging

from flask import g, jsonify, request

from auth import TokenError, decode_token

logger = logging.getLogger(__name__)

# In-memory blocklist for revoked tokens (logout).
# Production replacement: Redis SET with TTL matching token expiry.
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
        except Exception:
            logger.exception("Unhandled exception in %s", f.__name__)
            return jsonify({"error": "Internal server error"}), 500

    return decorated
