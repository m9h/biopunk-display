"""Tests for OpenClaw agent and autonomous loop.

Covers OpenClawAgent (agent.py) and AutonomousLoop (autonomous.py) with
fully mocked Anthropic client, Flask app, and database — no real API calls
or hardware access.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.openclaw.agent import OpenClawAgent, TOOLS, SYSTEM_PROMPT
from app.openclaw.autonomous import AutonomousLoop


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_app():
    """Minimal mock Flask app with the attributes OpenClawAgent needs."""
    app = MagicMock()
    _cfg = {
        'ANTHROPIC_API_KEY': 'test-key-not-real',
        'OPENCLAW_MODEL': 'claude-sonnet-4-6',
        'OPENCLAW_INTERVAL': 60,
    }
    app.config = MagicMock()
    app.config.get = lambda key, default=None: _cfg.get(key, default)

    app.app_context.return_value.__enter__ = MagicMock(return_value=None)
    app.app_context.return_value.__exit__ = MagicMock(return_value=False)

    app.display = MagicMock()
    app.message_queue = MagicMock()
    app.message_queue.pending = 2
    app.playlists = MagicMock()
    app.playlists.now_playing = None
    app.playlists.list_playlists.return_value = ['welcome.json', 'idle.json']
    app.webcam_input = MagicMock()
    app.webcam_input.is_present = False
    app.openclaw = None

    return app


@pytest.fixture
def agent_no_client():
    """An agent with no Anthropic client (simulates missing API key)."""
    return OpenClawAgent()


@pytest.fixture
def agent_with_client(mock_app):
    """An agent whose client is a mock (no real API calls)."""
    agent = OpenClawAgent()
    agent._app = mock_app
    agent._client = MagicMock()
    agent._model = 'claude-sonnet-4-6'
    return agent


# ---------------------------------------------------------------------------
# Helper to build fake Claude responses
# ---------------------------------------------------------------------------

def _make_response(stop_reason='end_turn', content=None):
    if content is None:
        text_block = SimpleNamespace(type='text', text='Hello from OpenClaw')
        content = [text_block]
    return SimpleNamespace(stop_reason=stop_reason, content=content)


def _make_tool_use_block(tool_name, tool_input, tool_id='tool_abc123'):
    return SimpleNamespace(
        type='tool_use', name=tool_name, input=tool_input, id=tool_id,
    )


# ===================================================================
# OpenClawAgent — no client
# ===================================================================

class TestOpenClawAgentNoClient:

    def test_compose_returns_error_when_no_client(self, agent_no_client):
        result = agent_no_client.compose('write something cool')
        assert result == {'error': 'OpenClaw not available'}

    def test_react_returns_error_when_no_client(self, agent_no_client):
        result = agent_no_client.react('presence_detected', {'distance': 1.5})
        assert result == {'error': 'OpenClaw not available'}


# ===================================================================
# _execute_tool dispatch
# ===================================================================

class TestExecuteTool:

    def test_send_message(self, agent_with_client):
        agent = agent_with_client
        agent._tool_send_message = MagicMock(return_value={'status': 'queued', 'id': 1, 'body': 'HI'})
        result = agent._execute_tool('send_message', {'body': 'HI'})
        agent._tool_send_message.assert_called_once_with({'body': 'HI'})
        assert result['status'] == 'queued'

    def test_get_display_status(self, agent_with_client):
        agent = agent_with_client
        agent._tool_get_status = MagicMock(return_value={
            'queue_pending': 2, 'webcam_present': False, 'playlist_playing': None,
        })
        result = agent._execute_tool('get_display_status', {})
        agent._tool_get_status.assert_called_once()
        assert 'queue_pending' in result

    def test_clear_display(self, agent_with_client):
        result = agent_with_client._execute_tool('clear_display', {})
        agent_with_client._app.display.clear.assert_called_once()
        assert result == {'status': 'cleared'}

    def test_play_playlist(self, agent_with_client):
        agent = agent_with_client
        agent._tool_play_playlist = MagicMock(return_value={'status': 'playing', 'name': 'welcome'})
        result = agent._execute_tool('play_playlist', {'filename': 'welcome.json'})
        agent._tool_play_playlist.assert_called_once_with({'filename': 'welcome.json'})

    def test_stop_playlist(self, agent_with_client):
        result = agent_with_client._execute_tool('stop_playlist', {})
        agent_with_client._app.playlists.stop.assert_called_once()
        assert result == {'status': 'stopped'}

    def test_list_playlists(self, agent_with_client):
        result = agent_with_client._execute_tool('list_playlists', {})
        assert result == {'playlists': ['welcome.json', 'idle.json']}

    def test_get_recent_messages(self, agent_with_client):
        agent = agent_with_client
        agent._tool_get_recent = MagicMock(return_value={'messages': []})
        result = agent._execute_tool('get_recent_messages', {'limit': 5})
        agent._tool_get_recent.assert_called_once_with({'limit': 5})

    def test_create_playlist(self, agent_with_client):
        agent = agent_with_client
        agent._tool_create_playlist = MagicMock(return_value={'status': 'created', 'filename': 'test.json'})
        data = {'name': 'Test', 'messages': [{'body': 'hello'}]}
        result = agent._execute_tool('create_playlist', data)
        agent._tool_create_playlist.assert_called_once_with(data)

    def test_unknown_tool_returns_error(self, agent_with_client):
        result = agent_with_client._execute_tool('nonexistent_tool', {})
        assert 'error' in result
        assert 'Unknown tool' in result['error']


# ===================================================================
# _run_agent_loop
# ===================================================================

class TestRunAgentLoop:

    def test_end_turn_returns_response(self, agent_with_client):
        agent = agent_with_client
        agent._client.messages.create.return_value = _make_response(stop_reason='end_turn')
        result = agent._run_agent_loop('hello')
        assert result['response'] == 'Hello from OpenClaw'
        assert result['messages_sent'] == 0

    def test_tool_use_calls_execute_tool(self, agent_with_client):
        agent = agent_with_client
        tool_block = _make_tool_use_block('get_display_status', {}, tool_id='tool_1')
        tool_response = _make_response(stop_reason='tool_use', content=[tool_block])
        final_response = _make_response(stop_reason='end_turn')
        agent._client.messages.create.side_effect = [tool_response, final_response]
        agent._execute_tool = MagicMock(return_value={'queue_pending': 0})

        result = agent._run_agent_loop('check status')
        agent._execute_tool.assert_called_once_with('get_display_status', {})

    def test_send_message_tool_increments_counter(self, agent_with_client):
        agent = agent_with_client
        tool_block = _make_tool_use_block('send_message', {'body': 'HI'}, tool_id='tool_2')
        tool_response = _make_response(stop_reason='tool_use', content=[tool_block])
        final_response = _make_response(stop_reason='end_turn')
        agent._client.messages.create.side_effect = [tool_response, final_response]
        agent._execute_tool = MagicMock(return_value={'status': 'queued', 'id': 1})

        result = agent._run_agent_loop('say hi')
        assert result['messages_sent'] == 1

    def test_max_10_rounds(self, agent_with_client):
        agent = agent_with_client
        tool_block = _make_tool_use_block('get_display_status', {}, tool_id='tool_loop')
        endless_response = _make_response(stop_reason='tool_use', content=[tool_block])
        agent._client.messages.create.return_value = endless_response
        agent._execute_tool = MagicMock(return_value={'ok': True})

        result = agent._run_agent_loop('loop forever')
        assert agent._client.messages.create.call_count == 10
        assert result['response'] == 'Agent loop completed'


# ===================================================================
# TOOLS and SYSTEM_PROMPT structure
# ===================================================================

class TestToolsStructure:

    def test_tools_is_list(self):
        assert isinstance(TOOLS, list)
        assert len(TOOLS) > 0

    def test_each_tool_has_required_keys(self):
        for tool in TOOLS:
            assert 'name' in tool
            assert 'description' in tool
            assert 'input_schema' in tool
            assert isinstance(tool['input_schema'], dict)

    def test_expected_tool_names(self):
        names = {t['name'] for t in TOOLS}
        expected = {
            'send_message', 'get_display_status', 'clear_display',
            'play_playlist', 'stop_playlist', 'list_playlists',
            'get_recent_messages', 'create_playlist',
        }
        assert names == expected


class TestSystemPrompt:

    def test_system_prompt_is_nonempty_string(self):
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 0

    def test_system_prompt_mentions_openclaw(self):
        assert 'OpenClaw' in SYSTEM_PROMPT


# ===================================================================
# AutonomousLoop
# ===================================================================

class TestAutonomousLoop:

    def test_is_running_returns_false_initially(self):
        loop = AutonomousLoop()
        assert loop.is_running is False

    def test_start_does_nothing_without_agent(self, mock_app):
        mock_app.openclaw = None
        loop = AutonomousLoop()
        loop._app = mock_app
        loop.start()
        assert loop._running is False
        assert loop._thread is None

    def test_stop_sets_running_to_false(self):
        loop = AutonomousLoop()
        loop._running = True
        loop._thread = MagicMock()
        loop.stop()
        assert loop._running is False
        loop._thread.join.assert_called_once_with(timeout=10)

    def test_init_app_sets_interval(self, mock_app):
        loop = AutonomousLoop()
        loop.init_app(mock_app)
        assert loop._interval == 60
        assert mock_app.openclaw_auto is loop
