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
