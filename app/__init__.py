import logging
import os

from flask import Flask, send_from_directory
from sqlalchemy.orm import scoped_session, sessionmaker

from app.auth.routes import create_auth_blueprint
from app.core.database import create_engine_with_pool
from app.core.error_handlers import register_error_handlers
from app.models import Base
from app.tasks.routes import create_tasks_blueprint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

_FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist')


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

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    app.register_blueprint(create_auth_blueprint(Session), url_prefix="/auth")
    app.register_blueprint(create_tasks_blueprint(Session), url_prefix="/tasks")

    # Serve React SPA — catch-all fires only when no API route matched
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        if not os.path.isdir(_FRONTEND_DIST):
            # Frontend not built — return plain API info
            return {"name": "task-flow API", "docs": "https://github.com/bythebug/task-flow"}, 200
        target = os.path.join(_FRONTEND_DIST, path)
        if path and os.path.isfile(target):
            return send_from_directory(_FRONTEND_DIST, path)
        return send_from_directory(_FRONTEND_DIST, "index.html")

    return app
