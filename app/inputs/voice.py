"""
Chapter 7: Voice input via Vosk + Blue Yeti microphone.

Listens on audio card 3 (Blue Yeti) using Vosk for offline speech recognition.
Recognized phrases are sent to the message queue.

Install: pip install vosk sounddevice
Model:   Download a Vosk model and set VOSK_MODEL_PATH in config.
"""

import threading
import sys
import json
import os


class VoiceInput:
    """Offline speech-to-flipdot via Vosk."""

    # Voice commands that trigger special actions
    COMMANDS = {
        'clear display': 'clear',
        'clear screen': 'clear',
    }

    def __init__(self, app=None):
        self._thread = None
        self._running = False
        self._app = None
        self._model = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._device = app.config.get('VOSK_DEVICE', None)  # None = default
        self._model_path = app.config.get(
            'VOSK_MODEL_PATH',
            os.path.join(os.path.dirname(__file__), '..', '..', 'vosk-model')
        )
        self._sample_rate = app.config.get('VOSK_SAMPLE_RATE', 16000)
        app.voice_input = self

    def start(self):
        """Start listening in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        try:
            import vosk  # noqa: F401
            import sounddevice  # noqa: F401
        except ImportError:
            print('[voice] vosk or sounddevice not installed — voice input disabled',
                  file=sys.stderr)
            return

        if not os.path.isdir(self._model_path):
            print(f'[voice] Model not found at {self._model_path} — voice input disabled',
                  file=sys.stderr)
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name='voice-input'
        )
        self._thread.start()
        print('[voice] Listening on Blue Yeti...', file=sys.stderr)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _listen_loop(self):
        """Capture audio and recognize speech continuously."""
        import vosk
        import sounddevice as sd

        if self._model is None:
            vosk.SetLogLevel(-1)
            self._model = vosk.Model(self._model_path)

        rec = vosk.KaldiRecognizer(self._model, self._sample_rate)

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f'[voice] Audio status: {status}', file=sys.stderr)
            if self._running:
                rec.AcceptWaveform(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=8000,
                device=self._device,
                dtype='int16',
                channels=1,
                callback=audio_callback,
            ):
                while self._running:
                    import time
                    time.sleep(0.1)

                    result = rec.Result()
                    if result:
                        data = json.loads(result)
                        text = data.get('text', '').strip()
                        if text:
                            self._handle_text(text)
        except Exception as e:
            print(f'[voice] Error: {e}', file=sys.stderr)

    def _handle_text(self, text):
        """Process recognized text — either a command or a message."""
        lower = text.lower()

        # Check for commands
        for phrase, action in self.COMMANDS.items():
            if phrase in lower:
                if action == 'clear':
                    self._app.display.clear()
                    print(f'[voice] Command: {action}', file=sys.stderr)
                return

        # Otherwise, queue it as a message
        with self._app.app_context():
            from app.models import Message
            from app import db

            msg = Message(body=text, transition='typewriter', source='voice', priority=2)
            db.session.add(msg)
            db.session.commit()

            self._app.message_queue.enqueue(
                msg.body, msg.transition, msg.priority, msg.id
            )
            print(f'[voice] Queued: "{text}"', file=sys.stderr)
