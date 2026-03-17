# Chapter 11: The REST API Blueprint

## Two Doors to the Same Room

The web UI built in earlier chapters is designed for humans — forms, buttons, flash
messages. But machines need an interface too. A cron job that pushes a daily
weather summary, an external webhook, a mobile app, or the OpenClaw AI agent
(Chapter 14) all want to talk to the display without clicking through a browser.

That's what the API blueprint provides: a JSON-speaking door into the same message
queue that the web UI uses.

## Blueprint Setup

The API lives in its own package with a `url_prefix`:

```python
# app/api/__init__.py
bp = Blueprint('api', __name__, url_prefix='/api')
```

Every route registered on this blueprint is automatically mounted under `/api`.
This keeps the URL space clean — `/` is the HTML page, `/api/messages`
is the JSON endpoint — and lets us apply API-specific middleware (rate limiting,
token auth) without touching the web routes.

## Message Endpoints

### POST /api/messages — Send a message

```bash
curl -X POST http://localhost:5000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"body": "HELLO WORLD", "transition": "pop", "priority": 2}'
```

Three validation strategies at work:

1. **Body length** — hard reject. An empty or oversized message is always an error.
2. **Transition** — silent fallback. An unknown transition defaults to `righttoleft`
   rather than returning an error. API clients shouldn't need to know every effect.
3. **Priority** — clamping. Out-of-range values are pinned to [0, 10] instead of
   rejected. Friendlier than failing on `priority: 99`.

Returns `201 Created` with the message JSON.

### GET /api/messages — List messages (paginated)

```bash
curl 'http://localhost:5000/api/messages?page=2&per_page=10'
```

Flask-SQLAlchemy's `paginate()` does the heavy lifting. The `per_page` parameter
is capped at 100 to prevent a single request from dumping the entire database.

### GET /api/messages/\<id\> — Fetch one message

Returns `404` if the message doesn't exist, via `db.get_or_404()`.

## Display Endpoints

### GET /api/display/status

Returns a snapshot of the whole system in one call:

```json
{
  "transitions": ["righttoleft", "pop", "matrix_effect"],
  "connected": true,
  "queue_pending": 3,
  "webcam_present": false,
  "playlist_playing": null,
  "openclaw_enabled": true
}
```

This endpoint is how OpenClaw checks whether someone is nearby, whether a playlist
is already running, and what transitions it can use.

### POST /api/display/clear

Blanks the physical display immediately. Returns `{"status": "ok"}`.

## Playlist Endpoints

```bash
# List all playlists
curl http://localhost:5000/api/playlists

# Create a playlist
curl -X POST http://localhost:5000/api/playlists \
  -H 'Content-Type: application/json' \
  -d '{"name": "Demo", "messages": [{"body": "FIRST"}, {"body": "SECOND"}]}'

# Start playback
curl -X POST http://localhost:5000/api/playlists/demo.json/play

# Stop playback
curl -X POST http://localhost:5000/api/playlists/stop
```

The `play` endpoint starts a background loop that feeds playlist messages into
the queue at priority 0 — the lowest tier, so any human input preempts them.

## OpenClaw Endpoints

```bash
# Compose — ask the agent to create and send a message
curl -X POST http://localhost:5000/api/openclaw/compose \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Something about DNA"}'

# React — feed the agent a sensor event
curl -X POST http://localhost:5000/api/openclaw/react \
  -H 'Content-Type: application/json' \
  -d '{"event": "presence_detected", "data": {"time": "14:30"}}'

# Autonomous mode
curl -X POST http://localhost:5000/api/openclaw/auto/start
curl -X POST http://localhost:5000/api/openclaw/auto/stop
curl http://localhost:5000/api/openclaw/auto/status
```

All OpenClaw endpoints return `503 Service Unavailable` if the agent isn't
configured. This lets clients distinguish "not available" from "broken."

## The Convergence Point

The most important thing about the API is what it *doesn't* do differently.
`POST /api/messages` calls the same `message_queue.enqueue()` that the web form
does. So does the voice input module, the gesture handler, and OpenClaw:

```
Web form ──────┐
REST API ──────┤
Voice input ───┤──▶ message_queue.enqueue() ──▶ display
Gesture ───────┤
OpenClaw ──────┘
```

One queue, one set of rules, many doors in.

## What's Next

Chapter 12 introduces playlists — JSON files that define looping sequences of
messages, giving the display something to show when no one is talking to it.
