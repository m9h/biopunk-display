"""
Stream engine — manages live data source plugins.

Each data source is a class with:
  - name: str
  - description: str
  - interval: int (seconds between fetches)
  - fetch() -> dict with 'text', 'transition', optionally 'bar_value' (0-7)
  - Optional: render_bar(value) -> 7×30 grid for bar graph mode

The engine runs active streams in background threads, feeding results
into the message queue or rendering directly to the display buffer.
"""

import threading
import sys
import time


class StreamEngine:
    """Manages live data stream plugins."""

    def __init__(self, app=None):
        self._app = None
        self._sources = {}
        self._active = {}  # name -> thread
        self._running_flags = {}  # name -> bool
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app

        # Register built-in sources
        from app.streams.sources import (
            SystemStats, ClockStream, CountdownStream, SensorSimulator
        )
        self.register(SystemStats())
        self.register(ClockStream())
        self.register(CountdownStream())
        self.register(SensorSimulator())

        # Optional sources that need network
        try:
            from app.streams.sources import WeatherStream, ISSTracker
            self.register(WeatherStream())
            self.register(ISSTracker())
        except Exception:
            pass

        app.streams = self

    def register(self, source):
        """Register a data source plugin."""
        self._sources[source.name] = source

    def list_sources(self):
        """Return available and active data sources."""
        return [
            {
                'name': s.name,
                'description': s.description,
                'interval': s.interval,
                'active': s.name in self._active and self._active[s.name].is_alive(),
            }
            for s in self._sources.values()
        ]

    def start_stream(self, name):
        """Start a data source stream."""
        source = self._sources.get(name)
        if source is None:
            raise ValueError(f'Unknown source: {name}')

        # Stop if already running
        self.stop_stream(name)

        self._running_flags[name] = True
        t = threading.Thread(
            target=self._stream_loop, args=(source,),
            daemon=True, name=f'stream-{name}'
        )
        self._active[name] = t
        t.start()
        print(f'[stream] Started: {name} (every {source.interval}s)', file=sys.stderr)

    def stop_stream(self, name):
        """Stop a running data source stream."""
        self._running_flags[name] = False
        t = self._active.pop(name, None)
        if t and t.is_alive():
            t.join(timeout=5)

    def stop_all(self):
        """Stop all active streams."""
        for name in list(self._active.keys()):
            self.stop_stream(name)

    def _stream_loop(self, source):
        """Fetch data and send to display on interval."""
        while self._running_flags.get(source.name, False):
            try:
                result = source.fetch()
                if result and result.get('text'):
                    self._send(result)
                elif result and result.get('bar_value') is not None:
                    self._render_bar(result)
            except Exception as e:
                print(f'[stream:{source.name}] Error: {e}', file=sys.stderr)

            # Interruptible sleep
            for _ in range(source.interval * 10):
                if not self._running_flags.get(source.name, False):
                    return
                time.sleep(0.1)

    def _send(self, result):
        """Send a text result to the message queue."""
        text = result['text']
        transition = result.get('transition', 'righttoleft')
        priority = result.get('priority', 0)

        with self._app.app_context():
            from app.models import Message
            from app import db

            msg = Message(body=text, transition=transition,
                          source='stream', priority=priority)
            db.session.add(msg)
            db.session.commit()

            self._app.message_queue.enqueue(
                msg.body, msg.transition, msg.priority, msg.id
            )

    def _render_bar(self, result):
        """Render a bar graph value (0-7) directly to display."""
        value = max(0, min(7, int(result['bar_value'])))
        label = result.get('label', '')

        # Build a simple bar: filled columns from bottom
        buf = [0] * 105
        bar_width = 8
        label_start = bar_width + 2

        # Bar (columns 0-7)
        for col in range(bar_width):
            byte_val = 0
            for row in range(7):
                if (6 - row) < value:  # fill from bottom
                    byte_val |= (1 << row)
            buf[col] = byte_val

        # Label text (simplified — use core's character dict if available)
        # For now, just send as a message
        if label:
            text = f'{label}: {"#" * value}{"." * (7 - value)}'
            with self._app.app_context():
                from app.models import Message
                from app import db
                msg = Message(body=text, transition='plain', source='stream')
                db.session.add(msg)
                db.session.commit()
                self._app.message_queue.enqueue(msg.body, msg.transition, 0, msg.id)
