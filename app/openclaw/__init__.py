"""
Chapter 14: OpenClaw — AI agent layer for the biopunk flipdot display.

OpenClaw is an optional AI agent that can:
- Compose dynamic, contextual messages for the display
- React intelligently to sensor events (presence, gestures, voice)
- Run autonomous display programs (e.g., news ticker, weather, art)
- Process complex voice commands that go beyond simple keyword matching

It uses the Anthropic Claude API with tool use to interact with
the display system through the same Flask API that all other inputs use.
"""
