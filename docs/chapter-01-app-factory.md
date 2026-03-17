# Chapter 1: The Flask App Factory

## What We're Building

A web-controlled flipdot display — an electromagnetic grid where each dot physically
clicks between black and yellow. Unlike pixels on a screen, these dots have *presence*.
They make sound. They're tactile. And we're going to give one a brain.

This first chapter sets up the foundation: a Flask application factory that can
grow from a simple "hello world" to an autonomous AI-controlled display system.

## Why an App Factory?

Flask's app factory pattern (`create_app()`) solves a fundamental problem: how do
you configure an app differently for development, testing, and production?

```python
# biopunk.py — the entry point
from app import create_app
app = create_app()
```

That's it. One line creates the entire application. The factory lives in
`app/__init__.py`:

```python
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.display.manager import DisplayManager
    app.display = DisplayManager(app)

    # ... register blueprints, start services ...
    return app
```

### Key decisions:

1. **Extensions are initialized outside the factory** (`db = SQLAlchemy()`) but
   connected to the app inside it (`db.init_app(app)`). This lets us import `db`
   from anywhere without circular imports.

2. **The display hardware is wrapped**, not imported directly. `DisplayManager`
   provides a Flask-friendly interface around the proven `WorkingFlipdotCore` class
   without modifying the original code.

3. **Configuration comes from a class**, not hardcoded values. Environment variables
   override defaults, so the same code runs on the Pi with hardware and on a laptop
   without it.

## The Display Manager

The display is our most important peripheral, so it gets first-class treatment:

```python
class DisplayManager:
    def __init__(self, app=None):
        self._core = None       # Lazy — no serial port opened until needed
        self._lock = threading.Lock()  # Thread-safe for queue + web access
```

**Lazy initialization** is critical here. The serial port to the flipdot display
might not exist on a developer's laptop. By deferring the hardware connection to
first use, the app starts cleanly everywhere. The actual connection happens in
the `core` property:

```python
@property
def core(self):
    if self._core is None:
        from core.core import WorkingFlipdotCore
        self._core = WorkingFlipdotCore(port=self._port, baud=self._baud)
    return self._core
```

**Thread safety** matters because multiple inputs (web form, API, voice, gesture)
will all try to write to the display simultaneously. The `threading.Lock` ensures
only one message plays at a time.

## Running It

```bash
# Set up
pip install -r requirements.txt
flask db upgrade       # create the SQLite database
flask run              # start on http://localhost:5000
```

The `.flaskenv` file tells Flask where to find the app:
```
FLASK_APP=biopunk.py
FLASK_DEBUG=1
```

## What's Next

Chapter 2 adds Jinja2 templates — the biopunk-themed web interface where you'll
type messages and watch them queue up for the display.
