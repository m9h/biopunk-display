from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.display.manager import DisplayManager
    app.display = DisplayManager(app)

    from app.display.queue import MessageQueue
    app.message_queue = MessageQueue(app)
    app.message_queue.start()

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.api import bp as api_bp
    app.register_blueprint(api_bp)

    return app

from app import models  # noqa: E402, F401
