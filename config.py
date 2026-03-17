import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'biopunk-flipdot-dev-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flipdot hardware
    FLIPDOT_PORT = os.environ.get('FLIPDOT_PORT')  # None = auto-detect
    FLIPDOT_BAUD = int(os.environ.get('FLIPDOT_BAUD', 38400))

    # Voice input (Chapter 7)
    VOSK_MODEL_PATH = os.environ.get('VOSK_MODEL_PATH',
                                      os.path.join(basedir, 'vosk-model'))
    VOSK_DEVICE = os.environ.get('VOSK_DEVICE')  # None = default mic
    VOSK_SAMPLE_RATE = int(os.environ.get('VOSK_SAMPLE_RATE', 16000))

    # Gesture input (Chapter 8)
    LEAP_WS_URL = os.environ.get('LEAP_WS_URL', 'ws://localhost:6437/v6.json')
    LEAP_COOLDOWN = float(os.environ.get('LEAP_COOLDOWN', 2.0))

    # Webcam input (Chapter 9)
    WEBCAM_DEVICE = int(os.environ.get('WEBCAM_DEVICE', 0))
    WEBCAM_MOTION_THRESHOLD = int(os.environ.get('WEBCAM_MOTION_THRESHOLD', 5000))
    WEBCAM_GREETING = os.environ.get('WEBCAM_GREETING', 'WELCOME')
    WEBCAM_FAREWELL = os.environ.get('WEBCAM_FAREWELL', 'GOODBYE')
    WEBCAM_COOLDOWN = int(os.environ.get('WEBCAM_COOLDOWN', 30))

    # Webhook
    WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')

    # Playlists (Chapter 12)
    PLAYLIST_DIR = os.environ.get('PLAYLIST_DIR',
                                   os.path.join(basedir, 'playlists'))

    # OpenClaw (Chapter 14)
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    OPENCLAW_MODEL = os.environ.get('OPENCLAW_MODEL', 'claude-sonnet-4-6')
    OPENCLAW_ENABLED = os.environ.get('OPENCLAW_ENABLED', 'false').lower() == 'true'
    OPENCLAW_INTERVAL = int(os.environ.get('OPENCLAW_INTERVAL', 300))

    # Generative art (Chapter 15)
    GENERATOR_TICK_RATE = float(os.environ.get('GENERATOR_TICK_RATE', 0.3))
