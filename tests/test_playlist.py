"""Tests for playlist manager (app/display/playlist.py).

Uses tmp_path fixtures — no hardware, no Flask app required.
"""

import json
import os
from unittest.mock import MagicMock

import pytest

from app.display.playlist import PlaylistManager


@pytest.fixture
def pm(tmp_path):
    """A PlaylistManager wired to a temp directory."""
    app = MagicMock()
    app.config.get = lambda key, default=None: {
        'PLAYLIST_DIR': str(tmp_path),
    }.get(key, default)
    app.message_queue = MagicMock()

    mgr = PlaylistManager()
    mgr.init_app(app)
    return mgr


def _write_playlist(directory, filename, data):
    path = os.path.join(str(directory), filename)
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# list_playlists
# ---------------------------------------------------------------------------

class TestListPlaylists:

    def test_empty_directory(self, pm):
        assert pm.list_playlists() == []

    def test_returns_playlist_metadata(self, pm):
        data = {
            'name': 'Welcome Loop',
            'repeat': True,
            'messages': [
                {'body': 'HELLO', 'transition': 'pop'},
                {'body': 'WORLD', 'transition': 'dissolve'},
            ],
        }
        _write_playlist(pm._playlist_dir, 'welcome.json', data)

        playlists = pm.list_playlists()
        assert len(playlists) == 1
        assert playlists[0]['filename'] == 'welcome.json'
        assert playlists[0]['name'] == 'Welcome Loop'
        assert playlists[0]['messages'] == 2
        assert playlists[0]['repeat'] is True

    def test_ignores_non_json_files(self, pm):
        with open(os.path.join(pm._playlist_dir, 'notes.txt'), 'w') as f:
            f.write('not a playlist')
        assert pm.list_playlists() == []

    def test_ignores_invalid_json(self, pm):
        with open(os.path.join(pm._playlist_dir, 'bad.json'), 'w') as f:
            f.write('not valid json {{{')
        assert pm.list_playlists() == []

    def test_multiple_playlists_sorted(self, pm):
        _write_playlist(pm._playlist_dir, 'b.json', {'name': 'B', 'messages': []})
        _write_playlist(pm._playlist_dir, 'a.json', {'name': 'A', 'messages': []})
        playlists = pm.list_playlists()
        assert [p['filename'] for p in playlists] == ['a.json', 'b.json']


# ---------------------------------------------------------------------------
# save_playlist
# ---------------------------------------------------------------------------

class TestSavePlaylist:

    def test_writes_valid_json(self, pm):
        data = {'name': 'Test', 'messages': [{'body': 'HI'}]}
        filename = pm.save_playlist('test', data)
        assert filename == 'test.json'

        path = os.path.join(pm._playlist_dir, 'test.json')
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_appends_json_extension(self, pm):
        filename = pm.save_playlist('mylist', {'name': 'X', 'messages': []})
        assert filename == 'mylist.json'

    def test_does_not_double_extension(self, pm):
        filename = pm.save_playlist('mylist.json', {'name': 'X', 'messages': []})
        assert filename == 'mylist.json'

    def test_overwrites_existing(self, pm):
        pm.save_playlist('x', {'name': 'V1', 'messages': []})
        pm.save_playlist('x', {'name': 'V2', 'messages': [{'body': 'NEW'}]})

        data = pm.get_playlist('x.json')
        assert data['name'] == 'V2'
        assert len(data['messages']) == 1


# ---------------------------------------------------------------------------
# get_playlist / _load_file
# ---------------------------------------------------------------------------

class TestGetPlaylist:

    def test_loads_json_data(self, pm):
        data = {'name': 'Idle', 'repeat': False, 'messages': [{'body': 'ZZZ'}]}
        _write_playlist(pm._playlist_dir, 'idle.json', data)

        loaded = pm.get_playlist('idle.json')
        assert loaded == data

    def test_raises_for_missing_file(self, pm):
        with pytest.raises(FileNotFoundError):
            pm.get_playlist('nonexistent.json')


# ---------------------------------------------------------------------------
# now_playing
# ---------------------------------------------------------------------------

class TestNowPlaying:

    def test_none_when_not_playing(self, pm):
        assert pm.now_playing is None

    def test_none_when_thread_dead(self, pm):
        pm._current_name = 'old'
        pm._current_thread = MagicMock()
        pm._current_thread.is_alive.return_value = False
        assert pm.now_playing is None

    def test_returns_name_when_thread_alive(self, pm):
        pm._current_name = 'Welcome'
        pm._current_thread = MagicMock()
        pm._current_thread.is_alive.return_value = True
        assert pm.now_playing == 'Welcome'
