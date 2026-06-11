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

    app.register_blueprint(create_auth_blueprint(Session), url_prefix="/auth")
    app.register_blueprint(create_tasks_blueprint(Session), url_prefix="/tasks")

    return app
