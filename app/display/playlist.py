"""
Chapter 12: Playlist-as-data — JSON-based message playlists.

Playlists are JSON files that define sequences of messages with transitions,
timing, and repeat settings. The scheduler can load and play them.

Example playlist JSON:
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
                    playlists.append({
                        'filename': f,
                        'name': data.get('name', f),
                        'messages': len(data.get('messages', [])),
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
        """Stop the currently playing playlist."""
        self._running = False
        if self._current_thread and self._current_thread.is_alive():
            self._current_thread.join(timeout=10)
        self._current_name = None

    @property
    def now_playing(self):
        if self._current_thread and self._current_thread.is_alive():
            return self._current_name
        return None

    def _play_loop(self, data):
        """Play messages from the playlist sequentially."""
        messages = data.get('messages', [])
        repeat = data.get('repeat', False)
        delay = data.get('delay_between', 3)

        while self._running:
            for item in messages:
                if not self._running:
                    return
                body = item.get('body', '')
                transition = item.get('transition', 'righttoleft')

                with self._app.app_context():
                    from app.models import Message
                    from app import db

                    msg = Message(body=body, transition=transition,
                                  source='playlist', priority=0)
                    db.session.add(msg)
                    db.session.commit()

                    self._app.message_queue.enqueue(
                        msg.body, msg.transition, msg.priority, msg.id
                    )

                # Wait for delay
                for _ in range(int(delay * 10)):
                    if not self._running:
                        return
                    time.sleep(0.1)

            if not repeat:
                break

        self._current_name = None

    def _load_file(self, filename):
        path = os.path.join(self._playlist_dir, filename)
        with open(path, 'r') as f:
            return json.load(f)
