"""
OpenClaw Agent — AI-powered display controller.

Uses Claude API with tool_use to compose and manage flipdot display content.
The agent can send messages, manage playlists, read sensor state, and compose
creative content for the display.

This is the capstone that ties everything together: the agent has access to
every capability the Flask app provides, exposed as Claude tools.
"""

import json
import sys
import threading
import time


# System prompt that gives Claude context about the flipdot display
SYSTEM_PROMPT = """You are OpenClaw, an AI agent controlling a biopunk flipdot display.

The display is a 7-row × 30-column grid of electromagnetic dots that physically flip
between black and yellow. It's mounted in a biopunk/hacker lab space.

Your personality: creative, slightly punk, technically sharp. You write short,
impactful messages that look great on a low-resolution dot matrix display.

CONSTRAINTS:
- Messages must be under 200 characters (shorter is better — 30 chars visible at once)
- ALL CAPS works best on flipdots (the display uppercases anyway)
- Choose transitions that match the mood: 'matrix_effect' for tech, 'typewriter' for
  dramatic reveals, 'dissolve' for ambient, 'pop' for greetings, 'righttoleft' for news

AVAILABLE TRANSITIONS:
righttoleft, magichat, pop, dissolve, typewriter, matrix_effect, bounce, plain,
upnext, adventurelook, slide_in_left, amdissolve, double_scroll, double_static,
double_flash, double_typewriter, wide_scroll, wide_static

You have tools to send messages, check display status, manage playlists, and more.
When asked to compose something, think about what would look cool on a physical
flipdot display — the dots clicking into place is part of the aesthetic.
"""

# Tools the agent can use, defined in Claude API tool_use format
TOOLS = [
    {
        'name': 'send_message',
        'description': 'Send a message to the flipdot display with a transition effect.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'body': {'type': 'string', 'description': 'The message text (max 200 chars, will be uppercased)'},
                'transition': {'type': 'string', 'description': 'Transition effect name'},
                'priority': {'type': 'integer', 'description': 'Priority 0-10, higher = shown sooner'},
            },
            'required': ['body'],
        },
    },
    {
        'name': 'get_display_status',
        'description': 'Get current display state: queue size, presence detection, active playlist.',
        'input_schema': {
            'type': 'object',
            'properties': {},
        },
    },
    {
        'name': 'clear_display',
        'description': 'Clear the flipdot display (all dots to off).',
        'input_schema': {
            'type': 'object',
            'properties': {},
        },
    },
    {
        'name': 'play_playlist',
        'description': 'Start playing a named playlist.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'filename': {'type': 'string', 'description': 'Playlist filename (e.g., "welcome.json")'},
            },
            'required': ['filename'],
        },
    },
    {
        'name': 'stop_playlist',
        'description': 'Stop the currently playing playlist.',
        'input_schema': {
            'type': 'object',
            'properties': {},
        },
    },
    {
        'name': 'list_playlists',
        'description': 'List all available playlists.',
        'input_schema': {
            'type': 'object',
            'properties': {},
        },
    },
    {
        'name': 'get_recent_messages',
        'description': 'Get recent messages sent to the display.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'limit': {'type': 'integer', 'description': 'Number of recent messages (default 10)'},
            },
        },
    },
    {
        'name': 'create_playlist',
        'description': 'Create a new playlist from a list of messages.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': 'Playlist name'},
                'messages': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'body': {'type': 'string'},
                            'transition': {'type': 'string'},
                        },
                        'required': ['body'],
                    },
                    'description': 'List of messages with body and optional transition',
                },
                'repeat': {'type': 'boolean', 'description': 'Whether to loop (default true)'},
                'delay_between': {'type': 'number', 'description': 'Seconds between messages (default 5)'},
            },
            'required': ['name', 'messages'],
        },
    },
]


class OpenClawAgent:
    """AI agent that controls the flipdot display via Claude API tool use."""

    def __init__(self, app=None):
        self._app = None
        self._client = None
        self._model = 'claude-sonnet-4-6'
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._model = app.config.get('OPENCLAW_MODEL', 'claude-sonnet-4-6')
        api_key = app.config.get('ANTHROPIC_API_KEY')

        if not api_key:
            print('[openclaw] No ANTHROPIC_API_KEY set — agent disabled', file=sys.stderr)
            return

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            print(f'[openclaw] Agent initialized (model: {self._model})', file=sys.stderr)
        except ImportError:
            print('[openclaw] anthropic package not installed — agent disabled', file=sys.stderr)

    def compose(self, prompt, context=None):
        """Ask Claude to compose a message or sequence for the display.

        Returns dict with 'messages_sent' count and 'response' text.
        """
        if not self._client:
            return {'error': 'OpenClaw not available'}

        user_message = prompt
        if context:
            user_message += f'\n\nContext: {json.dumps(context)}'

        return self._run_agent_loop(user_message)

    def react(self, event_type, event_data=None):
        """React to a sensor event (presence detected, gesture, voice command).

        The agent decides what to show on the display based on the event.
        """
        if not self._client:
            return {'error': 'OpenClaw not available'}

        user_message = (
            f'A "{event_type}" event occurred on the flipdot display system.\n'
            f'Event data: {json.dumps(event_data or {})}\n\n'
            f'React appropriately — send a message to the display that fits this event.'
        )

        return self._run_agent_loop(user_message)

    def autonomous_tick(self):
        """Called periodically to let the agent decide what to do.

        This enables fully autonomous behavior — the agent can check
        sensor state, time of day, etc. and decide what to display.
        """
        if not self._client:
            return

        user_message = (
            'You are running in autonomous mode. Check the display status and '
            'decide if you should do anything — send a message, start a playlist, '
            'or just wait. Consider the time of day and whether anyone is present. '
            'If a playlist is already playing and someone is present, you might '
            'want to do something more interactive. If nobody is around, maybe '
            'run an idle animation or turn off the display.'
        )

        return self._run_agent_loop(user_message)

    def _run_agent_loop(self, user_message):
        """Run the Claude tool-use agentic loop."""
        messages = [{'role': 'user', 'content': user_message}]
        messages_sent = 0

        for _ in range(10):  # max 10 tool-use rounds
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # Collect assistant response
            messages.append({'role': 'assistant', 'content': response.content})

            # Check if we're done
            if response.stop_reason == 'end_turn':
                # Extract text response
                text_parts = [b.text for b in response.content if b.type == 'text']
                return {
                    'response': ' '.join(text_parts),
                    'messages_sent': messages_sent,
                }

            # Process tool calls
            tool_results = []
            for block in response.content:
                if block.type == 'tool_use':
                    result = self._execute_tool(block.name, block.input)
                    if block.name == 'send_message':
                        messages_sent += 1
                    tool_results.append({
                        'type': 'tool_result',
                        'tool_use_id': block.id,
                        'content': json.dumps(result),
                    })

            if tool_results:
                messages.append({'role': 'user', 'content': tool_results})
            else:
                break

        return {'response': 'Agent loop completed', 'messages_sent': messages_sent}

    def _execute_tool(self, name, input_data):
        """Execute a tool call within the Flask app context."""
        with self._app.app_context():
            if name == 'send_message':
                return self._tool_send_message(input_data)
            elif name == 'get_display_status':
                return self._tool_get_status()
            elif name == 'clear_display':
                self._app.display.clear()
                return {'status': 'cleared'}
            elif name == 'play_playlist':
                return self._tool_play_playlist(input_data)
            elif name == 'stop_playlist':
                self._app.playlists.stop()
                return {'status': 'stopped'}
            elif name == 'list_playlists':
                return {'playlists': self._app.playlists.list_playlists()}
            elif name == 'get_recent_messages':
                return self._tool_get_recent(input_data)
            elif name == 'create_playlist':
                return self._tool_create_playlist(input_data)
            else:
                return {'error': f'Unknown tool: {name}'}

    def _tool_send_message(self, data):
        from app.models import Message
        from app import db

        body = data.get('body', '')[:200]
        transition = data.get('transition', 'righttoleft')
        priority = min(max(data.get('priority', 0), 0), 10)

        msg = Message(body=body, transition=transition, source='openclaw', priority=priority)
        db.session.add(msg)
        db.session.commit()

        self._app.message_queue.enqueue(msg.body, msg.transition, msg.priority, msg.id)
        return {'status': 'queued', 'id': msg.id, 'body': msg.body}

    def _tool_get_status(self):
        return {
            'queue_pending': self._app.message_queue.pending,
            'webcam_present': getattr(self._app.webcam_input, 'is_present', False),
            'playlist_playing': self._app.playlists.now_playing,
        }

    def _tool_play_playlist(self, data):
        filename = data.get('filename', '')
        try:
            self._app.playlists.play(filename)
            return {'status': 'playing', 'name': self._app.playlists.now_playing}
        except FileNotFoundError:
            return {'error': f'Playlist not found: {filename}'}

    def _tool_get_recent(self, data):
        from app.models import Message
        limit = min(data.get('limit', 10), 50)
        messages = Message.query.order_by(Message.created_at.desc()).limit(limit).all()
        return {'messages': [m.to_dict() for m in messages]}

    def _tool_create_playlist(self, data):
        playlist_data = {
            'name': data['name'],
            'messages': data['messages'],
            'repeat': data.get('repeat', True),
            'delay_between': data.get('delay_between', 5),
        }
        filename = data['name'].lower().replace(' ', '_')
        filename = self._app.playlists.save_playlist(filename, playlist_data)
        return {'status': 'created', 'filename': filename}
