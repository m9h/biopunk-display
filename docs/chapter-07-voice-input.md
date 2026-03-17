# Chapter 7: Voice Input via Vosk + Blue Yeti

## Talking to a Flipdot Display

Voice is the most natural human input. By connecting a Blue Yeti USB microphone
to offline speech recognition via Vosk, we let people speak messages directly to
the display — no phone, no keyboard, no network required.

## Why Vosk?

- **Completely offline** — no cloud API, no latency, no privacy concerns
- **Lightweight** — runs on a Raspberry Pi 4 with a small model (~50MB)
- **Real-time** — processes audio as a stream, not in batch
- **Multi-language** — models available for dozens of languages

Compare this to Google Speech API or Whisper: Vosk runs locally, doesn't need
internet, and starts recognizing immediately.

## The Architecture

```
Blue Yeti Mic → sounddevice (raw PCM) → Vosk (speech-to-text) → Message Queue
```

The `VoiceInput` class runs a background thread that:
1. Opens a raw audio stream from the Blue Yeti (16kHz, mono, int16)
2. Feeds audio chunks to Vosk's `KaldiRecognizer`
3. When Vosk produces a result, checks for commands or queues the text

## Audio Capture

```python
with sd.RawInputStream(
    samplerate=16000,
    blocksize=8000,
    device=self._device,   # Blue Yeti = device index from config
    dtype='int16',
    channels=1,
    callback=audio_callback,
):
```

`sounddevice` uses PortAudio under the hood. The callback receives raw PCM data
that Vosk can process directly — no format conversion needed.

**Why 16kHz?** Most speech recognition models are trained on 16kHz audio. Higher
sample rates don't improve accuracy and waste CPU.

**Why mono?** Speech recognition doesn't benefit from stereo. The Blue Yeti can
record in multiple patterns, but for voice commands, cardioid (front-facing) mono
is ideal.

## Voice Commands

Some phrases trigger actions instead of being displayed:

```python
COMMANDS = {
    'clear display': 'clear',
    'clear screen': 'clear',
}
```

When a recognized phrase matches a command, it's executed immediately (e.g.,
clearing the display) instead of being queued. This makes the display feel
responsive to direct instructions.

## Graceful Degradation

```python
try:
    import vosk
    import sounddevice
except ImportError:
    print('[voice] vosk or sounddevice not installed — voice input disabled')
    return
```

If `vosk` or `sounddevice` aren't installed, the voice module simply doesn't start.
The rest of the app continues working. This is critical for development — you
shouldn't need a microphone plugged in to work on the web interface.

## Setup

```bash
# Install dependencies
pip install vosk sounddevice

# Download a small English model
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
mv vosk-model-small-en-us-0.15 vosk-model

# Find the Blue Yeti's device index
python3 -c "import sounddevice; print(sounddevice.query_devices())"
# Set VOSK_DEVICE in .env to the correct index
```

## What's Next

Chapter 8 adds gesture input via the Leap Motion Controller — wave your hand
to trigger transitions and send messages.
