from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'main.login'
login.login_message_category = 'info'


@login.user_loader
def load_user(id):
    from app.models import User
    return db.session.get(User, int(id))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    # Display manager (always active)
    from app.display.manager import DisplayManager
    app.display = DisplayManager(app)

    # Message queue (always active)
    from app.display.queue import MessageQueue
    app.message_queue = MessageQueue(app)
    app.message_queue.start()

    # Playlist manager (always active)
    from app.display.playlist import PlaylistManager
    app.playlists = PlaylistManager(app)

    # Input modules (start gracefully — each handles missing deps)
    from app.inputs.voice import VoiceInput
    app.voice_input = VoiceInput(app)

    from app.inputs.gesture import GestureInput
    app.gesture_input = GestureInput(app)

    from app.inputs.webcam import WebcamInput
    app.webcam_input = WebcamInput(app)

    from app.inputs.webhook import WebhookInput
    app.webhook_input = WebhookInput(app)

    # Start optional inputs (won't start if deps missing)
    app.voice_input.start()
    app.gesture_input.start()
    app.webcam_input.start()

    # OpenClaw agent (Chapter 14 — optional)
    if app.config.get('OPENCLAW_ENABLED'):
        try:
            from app.openclaw.agent import OpenClawAgent
            app.openclaw = OpenClawAgent(app)

            from app.openclaw.autonomous import AutonomousLoop
            app.openclaw_auto = AutonomousLoop(app)
        except Exception as e:
            import sys
            print(f'[openclaw] Failed to initialize: {e}', file=sys.stderr)
            app.openclaw = None
            app.openclaw_auto = None
    else:
        app.openclaw = None
        app.openclaw_auto = None

    # Blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.api import bp as api_bp
    app.register_blueprint(api_bp)

    return app

from app import models  # noqa: E402, F401
