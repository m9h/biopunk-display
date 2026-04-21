"""
Chapter 12: Playlist-as-data — JSON-based message playlists.

Playlists are JSON files that define sequences of *items* with timing
and repeat settings. Each item can be a transition-based message, a
scrolling ticker (mixed-mode allowed), a video clip, or a cellular
automaton.  `delay_between` is used when an item omits its own
`duration`.

Item shapes
-----------
  message (default if `type` omitted — keeps legacy playlists working):
    {"type": "message", "body": "HELLO", "transition": "righttoleft"}

  ticker — single-mode:
    {"type": "ticker", "text": "HELLO", "mode": "double",
     "speed": 0.1, "duration": 12}

  ticker — mixed segments:
    {"type": "ticker",
     "segments": [
       {"text": "HELLO",   "mode": "single"},
       {"text": "WORLD",   "mode": "double"},
       {"text": "BIOPUNK", "mode": "wide"}
     ],
     "speed": 0.08, "duration": 20}

  video:
    {"type": "video", "clip": "demo-pulse", "fps": 12,
     "loop": true, "duration": 10}

  cellular automaton:
    {"type": "ca", "automaton": "life", "speed": 0.3,
     "duration": 20, "density": 0.4}
"""

import json
import os
import sys
import threading
import time


PLAYLIST_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'playlists')


class PlaylistManager:
    """Load and play JSON playlists on the flipdot display."""

    def __init__(self, app=None):
        self._app = None
        self._current_thread = None
        self._running = False
        self._current_name = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._playlist_dir = app.config.get('PLAYLIST_DIR', PLAYLIST_DIR)
        os.makedirs(self._playlist_dir, exist_ok=True)
        app.playlists = self

    def list_playlists(self):
        """Return list of available playlist names."""
        playlists = []
        if not os.path.isdir(self._playlist_dir):
            return playlists
        for f in sorted(os.listdir(self._playlist_dir)):
            if f.endswith('.json'):
                try:
                    data = self._load_file(f)
                    items = data.get('items') or data.get('messages') or []
                    playlists.append({
                        'filename': f,
                        'name': data.get('name', f),
                        'items': len(items),
                        'messages': len(items),  # legacy alias
                        'repeat': data.get('repeat', False),
                    })
                except (json.JSONDecodeError, OSError):
                    continue
        return playlists

    def get_playlist(self, filename):
        """Load and return a playlist by filename."""
        return self._load_file(filename)

    def save_playlist(self, filename, data):
        """Save a playlist to disk."""
        if not filename.endswith('.json'):
            filename += '.json'
        path = os.path.join(self._playlist_dir, filename)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return filename

    def play(self, filename):
        """Start playing a playlist in the background."""
        self.stop()
        data = self._load_file(filename)
        self._running = True
        self._current_name = data.get('name', filename)
        self._current_thread = threading.Thread(
            target=self._play_loop, args=(data,), daemon=True, name='playlist'
        )
        self._current_thread.start()
        print(f'[playlist] Playing: {self._current_name}', file=sys.stderr)

    def stop(self):
        """Stop the currently playing playlist.

        Also clears any display-owning mode (ticker/video/CA) that the
        playlist may have started, so the user doesn't see leftover
        content when they expect a stopped playlist.
        """
        self._running = False
        if self._current_thread and self._current_thread.is_alive():
            self._current_thread.join(timeout=10)
        self._current_name = None
        self._stop_owned_modes()

    @property
    def now_playing(self):
        if self._current_thread and self._current_thread.is_alive():
            return self._current_name
        return None

    def _play_loop(self, data):
        """Play items from the playlist sequentially."""
        # Accept both "messages" (legacy) and "items" keys.
        items = data.get('items') or data.get('messages') or []
        repeat = data.get('repeat', False)
        default_delay = data.get('delay_between', 3)

        while self._running:
            for item in items:
                if not self._running:
                    break
                try:
                    self._play_item(item)
                except Exception as e:
                    print(f'[playlist] Item error: {e}', file=sys.stderr)
                duration = item.get('duration', default_delay)
                if not self._sleep_interruptible(float(duration)):
                    break

            if not self._running or not repeat:
                break

        self._stop_owned_modes()
        self._current_name = None

    def _play_item(self, item):
        """Dispatch a single playlist item to the right subsystem."""
        kind = item.get('type', 'message')

        if kind == 'ticker':
            ticker = getattr(self._app, 'ticker', None)
            if ticker is None:
                return
            self._stop_owned_modes(except_ticker=True)
            segments = item.get('segments')
            speed = float(item.get('speed', 0.12))
            if segments:
                ticker.start_segments(segments, speed=speed)
            else:
                ticker.start(
                    item.get('text', ''),
                    speed=speed,
                    mode=item.get('mode', 'single'),
                )
            return

        if kind == 'video':
            video = getattr(self._app, 'video', None)
            clip = item.get('clip')
            if video is None or not clip:
                return
            self._stop_owned_modes(except_video=True)
            video.play(
                clip,
                fps=float(item.get('fps', 12.0)),
                loop=bool(item.get('loop', True)),
            )
            return

        if kind == 'ca':
            from app.display.automata import AutomataPlayer
            self._stop_owned_modes(except_ca=True)
            automaton = item.get('automaton', 'life')
            speed = float(item.get('speed', 0.3))
            kwargs = {k: item[k] for k in
                      ('density', 'rule', 'num_states', 'threshold', 'cells')
                      if k in item}
            player = AutomataPlayer(
                self._app, automaton=automaton, speed=speed, **kwargs
            )
            player.start()
            self._app._automata_player = player
            return

        # Default: message via the transition queue (legacy path).
        body = item.get('body', '')
        transition = item.get('transition', 'righttoleft')
        with self._app.app_context():
            from app.models import Message
            from app import db
            msg = Message(
                body=body, transition=transition,
                source='playlist', priority=0,
            )
            db.session.add(msg)
            db.session.commit()
            self._app.message_queue.enqueue(
                msg.body, msg.transition, msg.priority, msg.id
            )

    def _stop_owned_modes(self, except_ticker=False,
                          except_video=False, except_ca=False):
        """Stop display-owning modes so the next item can take over cleanly."""
        if not except_ca:
            player = getattr(self._app, '_automata_player', None)
            if player and player.is_running:
                player.stop()
                self._app._automata_player = None
        if not except_ticker:
            ticker = getattr(self._app, 'ticker', None)
            if ticker and ticker.is_running:
                ticker.stop()
        if not except_video:
            video = getattr(self._app, 'video', None)
            if video and video.is_running:
                video.stop()

    def _sleep_interruptible(self, duration):
        """Sleep up to `duration` seconds; returns False if interrupted."""
        end = time.monotonic() + duration
        while self._running:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return True
            time.sleep(min(0.1, remaining))
        return False

    def _load_file(self, filename):
        path = os.path.join(self._playlist_dir, filename)
        with open(path, 'r') as f:
            return json.load(f)
