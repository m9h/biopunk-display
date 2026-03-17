# Chapter 5: The Priority Message Queue

## The Central Nervous System

The message queue is arguably the most important piece of architecture in this
project. Every input — web form, REST API, voice recognition, gesture detection,
webcam presence, webhooks, playlists, and the OpenClaw AI agent — feeds messages
into this single queue. It's the funnel that prevents chaos.

## Why a Priority Queue?

Imagine this scenario: a playlist is looping promotional messages. Someone walks
up to the display. The webcam detects them and wants to show "WELCOME." A voice
command says "show hello." All at the same time.

Without priorities, it's first-come-first-served. The playlist message plays,
and by the time the greeting appears, the person has walked away. With priorities:

| Source    | Priority | Behavior                        |
|-----------|----------|---------------------------------|
| playlist  | 0        | Background — plays when idle    |
| gesture   | 1        | Acknowledged, but not urgent    |
| voice     | 2        | Human spoke — respond promptly  |
| webcam    | 3        | Someone's here — greet them NOW |
| openclaw  | varies   | AI decides its own priority     |

## The Implementation

```python
@dataclass(order=True)
class QueuedMessage:
    sort_key: tuple = field(compare=True)     # (-priority, sequence)
    message_id: int = field(compare=False, default=0)
    body: str = field(compare=False, default='')
    transition: str = field(compare=False, default='righttoleft')
```

Python's `PriorityQueue` sorts items by their natural ordering. We use a tuple
`(-priority, sequence)` as the sort key:

- **Negate priority** so higher priority = lower sort value = dequeued first
- **Sequence number** breaks ties — same priority messages play in FIFO order

The `field(compare=False)` on body/transition means those fields don't affect
ordering — only `sort_key` matters.

## The Worker Thread

```python
def _run(self):
    while self._running:
        try:
            item = self._queue.get(timeout=1.0)
        except queue.Empty:
            continue

        self._display.send_message(item.body, item.transition)

        # Mark as played in DB
        if item.message_id and self._app:
            with self._app.app_context():
                msg = db.session.get(Message, item.message_id)
                if msg:
                    msg.played = True
                    db.session.commit()
```

Key details:

- **`timeout=1.0`** — the worker checks every second whether it should stop.
  Without a timeout, `queue.get()` blocks forever and the thread can't be
  cleanly shut down.

- **App context** — Flask requires an application context for database access.
  Since this runs in a background thread, we need `with self._app.app_context()`.

- **Mark as played** — closing the loop between queue and database. The web UI
  can show which messages have actually been displayed vs. still pending.

## Thread Safety

The queue itself (`queue.PriorityQueue`) is thread-safe by design. The sequence
counter uses its own lock:

```python
def enqueue(self, body, transition='righttoleft', priority=0, message_id=0):
    with self._seq_lock:
        self._seq += 1
        seq = self._seq
    item = QueuedMessage(sort_key=(-priority, seq), ...)
    self._queue.put(item)
```

This ensures that even if two inputs enqueue simultaneously, they get unique,
monotonically increasing sequence numbers.

## Clean Shutdown

```python
def stop(self):
    self._running = False
    self._queue.put(QueuedMessage(sort_key=(999, 999)))  # sentinel
```

The sentinel value `(999, 999)` has the lowest possible priority. When the worker
dequeues it, it knows to exit. This is a common pattern for stopping consumer
threads gracefully.

## What's Next

Chapter 6 polishes the Bootstrap UI with the biopunk dark theme — green on black,
monospace fonts, and custom button styles.
