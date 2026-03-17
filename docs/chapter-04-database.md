# Chapter 4: SQLite Database with Flask-SQLAlchemy

## Why a Database?

Every message sent to the flipdot display gets logged. This gives us:
- **History** — see what's been shown
- **Queue persistence** — messages survive a restart
- **Analytics** — which sources send the most messages? Which transitions are popular?

## The Message Model

```python
# app/models.py
from datetime import datetime, timezone
from app import db

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(200), nullable=False)
    transition = db.Column(db.String(30), default='righttoleft')
    source = db.Column(db.String(20), default='web')
    priority = db.Column(db.Integer, default=0)
    played = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, index=True,
                           default=lambda: datetime.now(timezone.utc))
```

### Design choices:

- **`source` field** — tracks where the message came from: `web`, `api`, `voice`,
  `gesture`, `webcam`, `webhook`, `playlist`, or `openclaw`. This is essential for
  understanding how the display is being used.

- **`priority` field** — higher priority messages jump the queue. Voice commands
  (priority 2) and presence greetings (priority 3) get shown before web submissions
  (priority 0). This prevents the display from ignoring someone standing in front of
  it because a playlist is running.

- **`played` boolean** — the queue worker marks this `True` after the message has
  been displayed. This lets us distinguish pending vs. completed messages.

- **`created_at` with index** — we query by time constantly (recent messages for
  the web UI), so an index here is a no-brainer.

- **Timezone-aware UTC** — `datetime.now(timezone.utc)` instead of `datetime.utcnow()`
  (which is deprecated in Python 3.12+).

## Flask-Migrate

Schema changes are managed by Alembic (via Flask-Migrate):

```bash
flask db init          # one-time setup (creates migrations/)
flask db migrate -m "Initial message model"
flask db upgrade       # apply migration to create the table
```

The migration files in `migrations/versions/` are version-controlled. This means
anyone cloning the repo can run `flask db upgrade` to get the exact same schema.

## Serialization

The `to_dict()` method on the model converts a Message to a JSON-friendly dict:

```python
def to_dict(self):
    return {
        'id': self.id,
        'body': self.body,
        'transition': self.transition,
        'source': self.source,
        'priority': self.priority,
        'played': self.played,
        'created_at': self.created_at.isoformat() + 'Z',
    }
```

This is used by both the REST API and the OpenClaw agent when it queries recent
messages. The `+ 'Z'` suffix explicitly marks the timestamp as UTC.

## SQLite for Embedded Systems

SQLite is perfect for this project:
- **Zero configuration** — it's a file (`app.db`)
- **No server process** — one fewer thing to manage on the Pi
- **Concurrent reads** — multiple threads can read simultaneously
- **WAL mode** — enables concurrent reads even during writes

For a display that processes maybe a few hundred messages per day, SQLite is more
than sufficient.

## What's Next

Chapter 5 builds the priority message queue — the thread-safe system that takes
messages from the database and plays them on the hardware in the right order.
