"""Tests for Flask API routes and Message model.

Uses Flask test client with an in-memory SQLite database.
All display/hardware interactions are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    FLIPDOT_PORT = None
    FLIPDOT_BAUD = 38400
    VOSK_MODEL_PATH = '/nonexistent'
    WEBCAM_DEVICE = 0
    OPENCLAW_ENABLED = False


@pytest.fixture
def app():
    """Create a Flask app with mocked hardware for testing."""
    with patch('app.display.manager.DisplayManager') as MockDM, \
         patch('app.display.queue.MessageQueue') as MockMQ, \
         patch('app.inputs.voice.VoiceInput') as MockVoice, \
         patch('app.inputs.gesture.GestureInput') as MockGesture, \
         patch('app.inputs.webcam.WebcamInput') as MockWebcam, \
         patch('app.inputs.webhook.WebhookInput') as MockWebhook, \
         patch('app.display.playlist.PlaylistManager') as MockPL:

        mock_dm = MockDM.return_value
        mock_dm._core = None
        mock_dm.available_transitions.return_value = [
            'righttoleft', 'magichat', 'pop', 'dissolve', 'typewriter',
            'matrix_effect', 'bounce', 'plain',
        ]
        mock_dm.clear = MagicMock()

        mock_mq = MockMQ.return_value
        mock_mq.pending = 0
        mock_mq.start = MagicMock()
        mock_mq.enqueue = MagicMock()

        mock_pl = MockPL.return_value
        mock_pl.now_playing = None

        mock_webcam = MockWebcam.return_value
        mock_webcam.is_present = False
        mock_webcam.start = MagicMock()

        MockVoice.return_value.start = MagicMock()
        MockGesture.return_value.start = MagicMock()

        from app import create_app, db
        flask_app = create_app(TestConfig)

        with flask_app.app_context():
            db.create_all()
            yield flask_app
            db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ===================================================================
# Message model
# ===================================================================

class TestMessageModel:

    def test_defaults(self, app):
        with app.app_context():
            from app.models import Message
            from app import db
            msg = Message(body='TEST')
            db.session.add(msg)
            db.session.commit()

            assert msg.transition == 'righttoleft'
            assert msg.source == 'web'
            assert msg.priority == 0
            assert msg.played is False

    def test_to_dict_keys(self, app):
        with app.app_context():
            from app.models import Message
            from app import db
            msg = Message(body='HELLO')
            db.session.add(msg)
            db.session.commit()

            d = msg.to_dict()
            assert set(d.keys()) == {'id', 'body', 'transition', 'source', 'priority', 'played', 'created_at'}
            assert d['body'] == 'HELLO'
            assert isinstance(d['id'], int)
            assert d['created_at'].endswith('Z')

    def test_repr(self, app):
        with app.app_context():
            from app.models import Message
            from app import db
            msg = Message(body='REPR TEST')
            db.session.add(msg)
            db.session.commit()
            assert 'REPR TEST' in repr(msg)


# ===================================================================
# POST /api/messages
# ===================================================================

class TestCreateMessage:

    def test_valid_body_returns_201(self, client):
        resp = client.post('/api/messages', json={'body': 'HELLO'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['body'] == 'HELLO'
        assert 'id' in data

    def test_missing_body_returns_400(self, client):
        resp = client.post('/api/messages', json={})
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, client):
        resp = client.post('/api/messages', json={'body': ''})
        assert resp.status_code == 400

    def test_whitespace_body_returns_400(self, client):
        resp = client.post('/api/messages', json={'body': '   '})
        assert resp.status_code == 400

    def test_body_over_200_chars_returns_400(self, client):
        resp = client.post('/api/messages', json={'body': 'X' * 201})
        assert resp.status_code == 400

    def test_invalid_transition_falls_back(self, client):
        resp = client.post('/api/messages', json={
            'body': 'TEST', 'transition': 'nonexistent',
        })
        assert resp.status_code == 201
        assert resp.get_json()['transition'] == 'righttoleft'

    def test_priority_clamped_to_max_10(self, client):
        resp = client.post('/api/messages', json={'body': 'HI', 'priority': 99})
        assert resp.status_code == 201
        assert resp.get_json()['priority'] == 10

    def test_priority_clamped_to_min_0(self, client):
        resp = client.post('/api/messages', json={'body': 'HI', 'priority': -5})
        assert resp.status_code == 201
        assert resp.get_json()['priority'] == 0

    def test_no_json_content_type_returns_415(self, client):
        resp = client.post('/api/messages', data='not json',
                           content_type='text/plain')
        assert resp.status_code == 415


# ===================================================================
# GET /api/messages
# ===================================================================

class TestListMessages:

    def test_empty_db_returns_empty_list(self, client):
        resp = client.get('/api/messages')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['messages'] == []
        assert data['total'] == 0

    def test_returns_created_messages(self, client):
        client.post('/api/messages', json={'body': 'ONE'})
        client.post('/api/messages', json={'body': 'TWO'})
        resp = client.get('/api/messages')
        data = resp.get_json()
        assert data['total'] == 2
        assert len(data['messages']) == 2

    def test_pagination_keys(self, client):
        resp = client.get('/api/messages')
        data = resp.get_json()
        assert 'page' in data
        assert 'per_page' in data
        assert 'pages' in data

    def test_per_page_capped_at_100(self, client):
        resp = client.get('/api/messages?per_page=999')
        data = resp.get_json()
        assert data['per_page'] == 100


# ===================================================================
# GET /api/messages/<id>
# ===================================================================

class TestGetMessage:

    def test_found_by_id(self, client):
        resp = client.post('/api/messages', json={'body': 'FIND ME'})
        msg_id = resp.get_json()['id']
        resp = client.get(f'/api/messages/{msg_id}')
        assert resp.status_code == 200
        assert resp.get_json()['body'] == 'FIND ME'

    def test_404_for_missing_id(self, client):
        resp = client.get('/api/messages/99999')
        assert resp.status_code == 404


# ===================================================================
# GET /api/display/status
# ===================================================================

class TestDisplayStatus:

    def test_returns_expected_keys(self, client):
        resp = client.get('/api/display/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'transitions' in data
        assert 'connected' in data
        assert 'queue_pending' in data
        assert 'openclaw_enabled' in data


# ===================================================================
# POST /api/display/clear
# ===================================================================

class TestClearDisplay:

    def test_returns_ok(self, client):
        resp = client.post('/api/display/clear')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ok'
