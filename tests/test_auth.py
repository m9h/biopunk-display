"""Tests for user authentication (Chapter 10).

Tests registration, login, logout, and route protection
using an in-memory SQLite database with mocked hardware.
"""

from unittest.mock import MagicMock, patch

import pytest

from config import TestConfig


@pytest.fixture
def app():
    with patch('app.display.manager.DisplayManager') as MockDM, \
         patch('app.display.queue.MessageQueue') as MockMQ, \
         patch('app.inputs.voice.VoiceInput') as MockVoice, \
         patch('app.inputs.gesture.GestureInput') as MockGesture, \
         patch('app.inputs.webcam.WebcamInput') as MockWebcam, \
         patch('app.inputs.webhook.WebhookInput') as MockWebhook, \
         patch('app.display.playlist.PlaylistManager') as MockPL:

        mock_dm = MockDM.return_value
        mock_dm._core = None
        mock_dm.available_transitions.return_value = ['righttoleft', 'pop']
        mock_dm.clear = MagicMock()

        mock_mq = MockMQ.return_value
        mock_mq.pending = 0
        mock_mq.start = MagicMock()
        mock_mq.enqueue = MagicMock()

        mock_pl = MockPL.return_value
        mock_pl.now_playing = None

        MockVoice.return_value.start = MagicMock()
        MockGesture.return_value.start = MagicMock()
        MockWebcam.return_value.start = MagicMock()
        MockWebcam.return_value.is_present = False

        from app import create_app, db
        flask_app = create_app(TestConfig)

        with flask_app.app_context():
            db.create_all()
            yield flask_app
            db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username='testuser', password='testpass'):
    return client.post('/register', data={
        'username': username,
        'password': password,
        'password2': password,
    }, follow_redirects=True)


def login(client, username='testuser', password='testpass'):
    return client.post('/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=True)


# ===================================================================
# User model
# ===================================================================

class TestUserModel:

    def test_set_and_check_password(self, app):
        with app.app_context():
            from app.models import User
            u = User(username='alice')
            u.set_password('secret123')
            assert u.check_password('secret123')
            assert not u.check_password('wrong')

    def test_password_hash_not_plaintext(self, app):
        with app.app_context():
            from app.models import User
            u = User(username='bob')
            u.set_password('mypassword')
            assert u.password_hash != 'mypassword'

    def test_repr(self, app):
        with app.app_context():
            from app.models import User
            u = User(username='charlie')
            assert 'charlie' in repr(u)


# ===================================================================
# Registration
# ===================================================================

class TestRegistration:

    def test_register_creates_user(self, client, app):
        resp = register(client)
        assert resp.status_code == 200
        with app.app_context():
            from app.models import User
            assert User.query.filter_by(username='testuser').first() is not None

    def test_register_shows_success_flash(self, client):
        resp = register(client)
        assert b'Welcome' in resp.data

    def test_duplicate_username_rejected(self, client):
        register(client, username='dupe')
        resp = register(client, username='dupe')
        assert b'Username already taken' in resp.data

    def test_password_mismatch_rejected(self, client):
        resp = client.post('/register', data={
            'username': 'mismatch',
            'password': 'pass1',
            'password2': 'pass2',
        }, follow_redirects=True)
        assert b'Field must be equal to' in resp.data

    def test_register_page_loads(self, client):
        resp = client.get('/register')
        assert resp.status_code == 200
        assert b'Register' in resp.data


# ===================================================================
# Login / Logout
# ===================================================================

class TestLogin:

    def test_login_with_correct_password(self, client):
        register(client)
        resp = login(client)
        assert resp.status_code == 200
        assert b'testuser' in resp.data  # username in navbar

    def test_login_with_wrong_password(self, client):
        register(client)
        resp = login(client, password='wrong')
        assert b'Invalid username or password' in resp.data

    def test_login_nonexistent_user(self, client):
        resp = login(client, username='nobody')
        assert b'Invalid username or password' in resp.data

    def test_logout(self, client):
        register(client)
        login(client)
        resp = client.get('/logout', follow_redirects=True)
        assert b'Login' in resp.data  # login link back in navbar

    def test_login_page_loads(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'Log In' in resp.data

    def test_authenticated_user_redirected_from_login(self, client):
        register(client)
        login(client)
        resp = client.get('/login')
        assert resp.status_code == 302  # redirect to index


# ===================================================================
# Route protection
# ===================================================================

class TestRouteProtection:

    def test_clear_requires_login(self, client):
        resp = client.post('/clear', follow_redirects=False)
        assert resp.status_code == 302
        assert '/login' in resp.location

    def test_send_message_prompts_login(self, client):
        resp = client.post('/', data={
            'message': 'HELLO',
            'transition': 'righttoleft',
        }, follow_redirects=True)
        assert b'log in' in resp.data.lower()

    def test_logged_in_user_can_send_message(self, client):
        register(client)
        login(client)
        resp = client.post('/', data={
            'message': 'HELLO',
            'transition': 'righttoleft',
        }, follow_redirects=True)
        assert b'Queued' in resp.data

    def test_index_visible_without_login(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'Recent Messages' in resp.data

    def test_message_form_hidden_when_not_logged_in(self, client):
        resp = client.get('/')
        assert b'Send to Display' not in resp.data
        assert b'Log in' in resp.data
