import logging
import os

from flask import Flask
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

    @app.route("/")
    def index():
        return {
            "name": "task-flow API",
            "version": "1.0",
            "status": "running",
            "docs": "https://github.com/bythebug/task-flow",
            "endpoints": {
                "auth":   ["/auth/register", "/auth/login", "/auth/logout"],
                "tasks":  ["/tasks/", "/tasks/<id>"],
                "sharing": ["/tasks/<id>/share", "/tasks/<id>/collaborators"],
            },
        }, 200

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    app.register_blueprint(create_auth_blueprint(Session), url_prefix="/auth")
    app.register_blueprint(create_tasks_blueprint(Session), url_prefix="/tasks")

    return app
