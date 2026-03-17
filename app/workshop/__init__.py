"""
Chapter 17: Workshop Mode — Collaborative & Audience Interaction

A facilitation layer for live settings. Multiple participants submit messages
from their phones (QR code → web form), a moderator approves/rejects them,
and the audience votes on what gets displayed next.

The display becomes a shared voice for a room full of people.
"""

from flask import Blueprint

bp = Blueprint('workshop', __name__, url_prefix='/workshop')

from app.workshop import routes  # noqa: E402, F401
