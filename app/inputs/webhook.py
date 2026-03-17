"""
Webhook input — allows external services to push messages to the display.

Already exposed via the API blueprint (/api/messages POST), but this module
provides a convenience class for registering webhook-specific routes with
validation tokens.
"""

import hashlib
import hmac
import sys
from flask import request, jsonify


class WebhookInput:
    """Validates and processes incoming webhooks."""

    def __init__(self, app=None):
        self._app = None
        self._secret = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._secret = app.config.get('WEBHOOK_SECRET')
        app.webhook_input = self

    def verify_signature(self, payload, signature):
        """Verify HMAC-SHA256 signature if a webhook secret is configured."""
        if not self._secret:
            return True  # no secret = accept all
        expected = hmac.new(
            self._secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f'sha256={expected}', signature or '')

    def process_payload(self, data, source='webhook'):
        """Create and enqueue a message from webhook payload."""
        body = data.get('body', '').strip()
        if not body or len(body) > 200:
            return None, 'body must be 1-200 characters'

        transition = data.get('transition', 'righttoleft')
        priority = min(max(int(data.get('priority', 0)), 0), 10)

        from app.models import Message
        from app import db

        msg = Message(body=body, transition=transition, source=source, priority=priority)
        db.session.add(msg)
        db.session.commit()

        self._app.message_queue.enqueue(
            msg.body, msg.transition, msg.priority, msg.id
        )

        print(f'[webhook] Queued: "{body}" from {source}', file=sys.stderr)
        return msg, None
