# Chapter 12: Playlist-as-Data

## Messages as Data, Not Code

When you want the display to cycle through a set of messages — a welcome loop,
event announcements, ambient art — you shouldn't have to write Python code.
Playlists are JSON files that anyone can create and edit.

## The Format

```json
{
    "name": "Welcome Loop",
    "repeat": true,
    "delay_between": 5,
    "messages": [
        {"body": "WELCOME TO BIOPUNK LAB", "transition": "righttoleft"},
        {"body": "HACK THE PLANET", "transition": "matrix_effect"},
        {"body": "OPEN SOURCE HARDWARE", "transition": "typewriter"}
    ]
}
```

- **`repeat`** — loop forever or play once
- **`delay_between`** — seconds between messages (accounts for transition time)
- **`messages`** — each entry specifies text and transition

## The PlaylistManager

Playlists play in a background thread, feeding messages through the same queue
as everything else:

```python
def _play_loop(self, data):
    while self._running:
        for item in messages:
            if not self._running:
                return
            msg = Message(body=body, transition=transition,
                          source='playlist', priority=0)
            db.session.add(msg)
            db.session.commit()
            self._app.message_queue.enqueue(msg.body, msg.transition, ...)

            # Interruptible sleep
            for _ in range(int(delay * 10)):
                if not self._running:
                    return
                time.sleep(0.1)

        if not repeat:
            break
```

### Why priority 0?

Playlists are **ambient content** — the lowest priority. They should play when
nothing else is happening, but immediately yield to voice commands, presence
greetings, or API messages. The priority queue handles this automatically.

### Interruptible sleep

The delay between messages uses a loop of short sleeps instead of one long
`time.sleep()`. This ensures that `stop()` takes effect within 100ms, not
after waiting out a full 5-second delay.

## REST API

```bash
# List playlists
curl http://localhost:5000/api/playlists

# Play a playlist
curl -X POST http://localhost:5000/api/playlists/welcome.json/play

# Stop playback
curl -X POST http://localhost:5000/api/playlists/stop

# Create a new playlist
curl -X POST http://localhost:5000/api/playlists \
  -H 'Content-Type: application/json' \
  -d '{"name": "Demo", "messages": [{"body": "HELLO"}], "repeat": false}'
```

## Use Cases

- **Welcome loop** — greets visitors when the lab is open
- **Event mode** — cycle through event info, sponsors, schedule
- **Art mode** — abstract text patterns with varied transitions
- **Idle animation** — something interesting when nobody's interacting

## OpenClaw Integration

The OpenClaw AI agent has a `create_playlist` tool. You can say:
*"Create a playlist about space exploration"* and the AI will compose
appropriate messages, choose transitions, and save a JSON playlist file
that can be played immediately or later.

## What's Next

Chapter 14 is the capstone — OpenClaw, an AI agent that uses Claude to
autonomously compose and manage display content.
