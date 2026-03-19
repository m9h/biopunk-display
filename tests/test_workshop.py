"""Tests for Workshop mode routes and models.

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
    WTF_CSRF_ENABLED = False


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


@pytest.fixture
def auth_client(app):
    """A test client logged in as a test user."""
    from app import db
    from app.models import User

    with app.app_context():
        user = User(username='facilitator')
        user.set_password('testpass')
        db.session.add(user)
        db.session.commit()

    c = app.test_client()
    # Log in via the login form
    c.post('/login', data={
        'username': 'facilitator',
        'password': 'testpass',
    }, follow_redirects=True)
    return c


def _create_submission(app, body='HELLO FLIPDOT', nickname='TESTER', status='pending'):
    """Helper: create a Submission directly in the database."""
    from app import db
    from app.workshop.models import Submission

    with app.app_context():
        sub = Submission(body=body, nickname=nickname, status=status)
        db.session.add(sub)
        db.session.commit()
        return sub.id


# ===================================================================
# Submission model
# ===================================================================

class TestSubmissionModel:

    def test_creation_with_required_fields(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission

            sub = Submission(body='TEST MESSAGE')
            db.session.add(sub)
            db.session.commit()

            assert sub.id is not None
            assert sub.body == 'TEST MESSAGE'
            assert sub.created_at is not None

    def test_default_status_is_pending(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission

            sub = Submission(body='PENDING CHECK')
            db.session.add(sub)
            db.session.commit()

            assert sub.status == 'pending'

    def test_default_nickname_is_anon(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission

            sub = Submission(body='ANON CHECK')
            db.session.add(sub)
            db.session.commit()

            assert sub.nickname == 'ANON'

    def test_default_vote_count_is_zero(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission

            sub = Submission(body='VOTE CHECK')
            db.session.add(sub)
            db.session.commit()

            assert sub.vote_count == 0

    def test_default_played_is_false(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission

            sub = Submission(body='PLAYED CHECK')
            db.session.add(sub)
            db.session.commit()

            assert sub.played is False

    def test_to_dict_keys(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission

            sub = Submission(body='DICT CHECK')
            db.session.add(sub)
            db.session.commit()

            d = sub.to_dict()
            expected_keys = {'id', 'body', 'nickname', 'status',
                             'vote_count', 'played', 'created_at'}
            assert set(d.keys()) == expected_keys
            assert d['body'] == 'DICT CHECK'
            assert d['created_at'].endswith('Z')

    def test_repr(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission

            sub = Submission(body='REPR TEST')
            db.session.add(sub)
            db.session.commit()

            assert 'REPR TEST' in repr(sub)


# ===================================================================
# Vote model
# ===================================================================

class TestVoteModel:

    def test_vote_creation(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission, Vote

            sub = Submission(body='VOTE TARGET', status='approved')
            db.session.add(sub)
            db.session.commit()

            vote = Vote(submission_id=sub.id, voter_id='abc123')
            db.session.add(vote)
            db.session.commit()

            assert vote.id is not None
            assert vote.submission_id == sub.id
            assert vote.voter_id == 'abc123'

    def test_vote_unique_constraint(self, app):
        with app.app_context():
            from app import db
            from app.workshop.models import Submission, Vote
            from sqlalchemy.exc import IntegrityError

            sub = Submission(body='UNIQUE TARGET', status='approved')
            db.session.add(sub)
            db.session.commit()

            v1 = Vote(submission_id=sub.id, voter_id='same_voter')
            db.session.add(v1)
            db.session.commit()

            v2 = Vote(submission_id=sub.id, voter_id='same_voter')
            db.session.add(v2)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()


# ===================================================================
# Public endpoints (no auth required)
# ===================================================================

class TestSubmitEndpoint:

    def test_get_submit_returns_200(self, client):
        resp = client.get('/workshop/submit')
        assert resp.status_code == 200

    def test_post_submit_creates_submission(self, client, app):
        resp = client.post('/workshop/submit', data={
            'message': 'MY MESSAGE',
            'nickname': 'ALICE',
        }, follow_redirects=False)
        # Should redirect back to submit page
        assert resp.status_code == 302

        with app.app_context():
            from app.workshop.models import Submission
            sub = Submission.query.first()
            assert sub is not None
            assert sub.body == 'MY MESSAGE'
            assert sub.nickname == 'ALICE'
            assert sub.status == 'pending'

    def test_post_submit_empty_message_rejected(self, client, app):
        resp = client.post('/workshop/submit', data={
            'message': '',
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            from app.workshop.models import Submission
            assert Submission.query.count() == 0

    def test_post_submit_too_long_rejected(self, client, app):
        resp = client.post('/workshop/submit', data={
            'message': 'X' * 201,
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            from app.workshop.models import Submission
            assert Submission.query.count() == 0

    def test_post_submit_default_nickname(self, client, app):
        resp = client.post('/workshop/submit', data={
            'message': 'NO NAME',
        }, follow_redirects=False)
        assert resp.status_code == 302

        with app.app_context():
            from app.workshop.models import Submission
            sub = Submission.query.first()
            assert sub.nickname == 'ANON'


class TestBoardEndpoint:

    def test_get_board_returns_200(self, client):
        resp = client.get('/workshop/board')
        assert resp.status_code == 200


class TestQrEndpoint:

    def test_get_qr_returns_200(self, client):
        resp = client.get('/workshop/qr')
        assert resp.status_code == 200


class TestVoteEndpoint:

    def test_vote_with_cookie(self, client, app):
        sub_id = _create_submission(app, status='approved')

        resp = client.post(f'/workshop/api/vote/{sub_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'voted'
        assert data['votes'] == 1
        # Should set a cookie
        assert 'workshop_voter' in resp.headers.get('Set-Cookie', '')

    def test_duplicate_vote_returns_409(self, client, app):
        sub_id = _create_submission(app, status='approved')

        # First vote
        resp1 = client.post(f'/workshop/api/vote/{sub_id}')
        assert resp1.status_code == 200

        # Second vote with same cookie (client preserves cookies)
        resp2 = client.post(f'/workshop/api/vote/{sub_id}')
        assert resp2.status_code == 409
        data = resp2.get_json()
        assert 'Already voted' in data['error']

    def test_vote_on_pending_returns_400(self, client, app):
        sub_id = _create_submission(app, status='pending')

        resp = client.post(f'/workshop/api/vote/{sub_id}')
        assert resp.status_code == 400


class TestListSubmissionsEndpoint:

    def test_empty_returns_empty_list(self, client):
        resp = client.get('/workshop/api/submissions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['submissions'] == []

    def test_returns_created_submissions(self, client, app):
        _create_submission(app, body='ONE')
        _create_submission(app, body='TWO')

        resp = client.get('/workshop/api/submissions')
        data = resp.get_json()
        assert len(data['submissions']) == 2

    def test_filter_by_status(self, client, app):
        _create_submission(app, body='PENDING', status='pending')
        _create_submission(app, body='APPROVED', status='approved')

        resp = client.get('/workshop/api/submissions?status=approved')
        data = resp.get_json()
        assert len(data['submissions']) == 1
        assert data['submissions'][0]['body'] == 'APPROVED'


# ===================================================================
# Protected endpoints (require login)
# ===================================================================

class TestModerateEndpoint:

    def test_moderate_redirects_when_not_authenticated(self, client):
        resp = client.get('/workshop/moderate')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_moderate_accessible_when_authenticated(self, auth_client, app):
        _create_submission(app, body='PENDING MSG')
        resp = auth_client.get('/workshop/moderate')
        assert resp.status_code == 200


class TestApproveEndpoint:

    def test_approve_requires_auth(self, client, app):
        sub_id = _create_submission(app)
        resp = client.post(f'/workshop/api/approve/{sub_id}')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_approve_works_when_authenticated(self, auth_client, app):
        sub_id = _create_submission(app)
        resp = auth_client.post(f'/workshop/api/approve/{sub_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'approved'
        assert data['id'] == sub_id


class TestRejectEndpoint:

    def test_reject_requires_auth(self, client, app):
        sub_id = _create_submission(app)
        resp = client.post(f'/workshop/api/reject/{sub_id}')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_reject_works_when_authenticated(self, auth_client, app):
        sub_id = _create_submission(app)
        resp = auth_client.post(f'/workshop/api/reject/{sub_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'rejected'
        assert data['id'] == sub_id


class TestSendToDisplayEndpoint:

    def test_send_requires_auth(self, client, app):
        sub_id = _create_submission(app, status='approved')
        resp = client.post(f'/workshop/api/send/{sub_id}')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_send_works_when_authenticated(self, auth_client, app):
        sub_id = _create_submission(app, status='approved')
        resp = auth_client.post(f'/workshop/api/send/{sub_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'sent'
        assert 'message_id' in data

    def test_send_unapproved_returns_400(self, auth_client, app):
        sub_id = _create_submission(app, status='pending')
        resp = auth_client.post(f'/workshop/api/send/{sub_id}')
        assert resp.status_code == 400


class TestPlayTopEndpoint:

    def test_play_top_requires_auth(self, client):
        resp = client.post('/workshop/api/play-top')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_play_top_with_no_submissions_returns_404(self, auth_client):
        resp = auth_client.post('/workshop/api/play-top')
        assert resp.status_code == 404

    def test_play_top_sends_highest_voted(self, auth_client, app):
        _create_submission(app, body='LOW VOTES', status='approved')
        sub_id = _create_submission(app, body='HIGH VOTES', status='approved')

        # Give the second submission more votes
        with app.app_context():
            from app import db
            from app.workshop.models import Submission
            sub = db.session.get(Submission, sub_id)
            sub.vote_count = 5
            db.session.commit()

        resp = auth_client.post('/workshop/api/play-top')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'sent'
        assert data['body'] == 'HIGH VOTES'
        assert data['votes'] == 5
