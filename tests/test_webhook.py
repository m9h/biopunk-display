"""Tests for webhook input (app/inputs/webhook.py).

Tests HMAC signature verification without requiring Flask or hardware.
"""

import hashlib
import hmac

import pytest

from app.inputs.webhook import WebhookInput


class TestVerifySignature:

    def test_no_secret_accepts_everything(self):
        wh = WebhookInput()
        wh._secret = None
        assert wh.verify_signature(b'anything', 'bogus') is True

    def test_no_secret_accepts_none_signature(self):
        wh = WebhookInput()
        wh._secret = None
        assert wh.verify_signature(b'data', None) is True

    def test_valid_signature_accepted(self):
        secret = 'my-webhook-secret'
        payload = b'{"body": "hello"}'
        expected = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        signature = f'sha256={expected}'

        wh = WebhookInput()
        wh._secret = secret
        assert wh.verify_signature(payload, signature) is True

    def test_invalid_signature_rejected(self):
        wh = WebhookInput()
        wh._secret = 'my-secret'
        assert wh.verify_signature(b'payload', 'sha256=bad') is False

    def test_none_signature_rejected_when_secret_set(self):
        wh = WebhookInput()
        wh._secret = 'my-secret'
        assert wh.verify_signature(b'payload', None) is False

    def test_empty_signature_rejected(self):
        wh = WebhookInput()
        wh._secret = 'my-secret'
        assert wh.verify_signature(b'payload', '') is False

    def test_wrong_prefix_rejected(self):
        secret = 'test'
        payload = b'data'
        digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        # Missing sha256= prefix
        wh = WebhookInput()
        wh._secret = secret
        assert wh.verify_signature(payload, digest) is False

    def test_different_payload_rejected(self):
        secret = 'test'
        sig = 'sha256=' + hmac.new(
            secret.encode(), b'original', hashlib.sha256
        ).hexdigest()

        wh = WebhookInput()
        wh._secret = secret
        assert wh.verify_signature(b'tampered', sig) is False
