"""
Priority message queue for the flipdot display.

All inputs (web, API, voice, gesture, webhook) enqueue messages here.
A background thread dequeues and plays them in priority order.
Higher priority number = played first. Same priority = FIFO.
"""

import threading
import queue
import time
from dataclasses import dataclass, field


@dataclass(order=True)
class QueuedMessage:
    """Wrapper for priority queue ordering. Lower sort_key = higher priority."""
    sort_key: tuple = field(compare=True)   # (-priority, sequence)
    message_id: int = field(compare=False, default=0)
    body: str = field(compare=False, default='')
    transition: str = field(compare=False, default='righttoleft')


class MessageQueue:
    """Thread-safe priority queue that feeds the flipdot display."""

    def __init__(self, app=None):
        self._queue = queue.PriorityQueue()
        self._seq = 0
        self._seq_lock = threading.Lock()
        self._worker = None
        self._running = False
        self._display = None
        self._app = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._display = app.display
        app.message_queue = self

    def start(self):
        """Start the background worker thread."""
        if self._worker is not None and self._worker.is_alive():
            return
        self._running = True
        self._worker = threading.Thread(
            target=self._run, daemon=True, name='flipdot-queue'
        )
        self._worker.start()

    def stop(self):
        self._running = False
        # Put a sentinel to unblock the queue
        self._queue.put(QueuedMessage(sort_key=(999, 999)))
        if self._worker:
            self._worker.join(timeout=5)

    def enqueue(self, body, transition='righttoleft', priority=0, message_id=0):
        """Add a message to the queue."""
        with self._seq_lock:
            self._seq += 1
            seq = self._seq
        item = QueuedMessage(
            sort_key=(-priority, seq),  # negate so higher priority = lower sort key
            message_id=message_id,
            body=body,
            transition=transition,
        )
        self._queue.put(item)

    @property
    def pending(self):
        return self._queue.qsize()

    def _run(self):
        """Worker loop: dequeue and play messages."""
        while self._running:
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # Check sentinel
            if item.sort_key == (999, 999):
                break

            try:
                self._display.send_message(item.body, item.transition)
                # Mark as played in DB if we have an ID
                if item.message_id and self._app:
                    with self._app.app_context():
                        from app.models import Message
                        from app import db
                        msg = db.session.get(Message, item.message_id)
                        if msg:
                            msg.played = True
                            db.session.commit()
            except Exception as e:
                import sys
                print(f'[queue] Error playing message: {e}', file=sys.stderr)

            self._queue.task_done()
