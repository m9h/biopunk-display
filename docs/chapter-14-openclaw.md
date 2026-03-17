# Chapter 14: OpenClaw — The AI Agent

## Giving the Display a Mind

This is the capstone chapter. Everything we've built — the Flask app, the message
queue, the sensor inputs, the playlist system — becomes infrastructure for an AI
agent that can autonomously control the flipdot display.

OpenClaw uses the Claude API with **tool use** to interact with the display system.
It doesn't just generate text — it *decides what to do* based on context, sensor
data, time of day, and conversational prompts.

## The Agent Architecture

```
                    ┌─────────────────┐
                    │   Claude API    │
                    │  (tool_use)     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  OpenClawAgent  │
                    │  _run_agent_loop│
                    └────────┬────────┘
                             │ tool calls
        ┌────────────────────┼───────────────────┐
        ▼                    ▼                   ▼
  send_message        get_display_status    create_playlist
  clear_display       get_recent_messages   play/stop_playlist
        │                    │                   │
        └────────────────────┼───────────────────┘
                             ▼
                    ┌─────────────────┐
                    │  Message Queue  │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │  Flipdot HW     │
                    └─────────────────┘
```

## Tool Use: The Key Concept

Claude's tool_use feature lets the model call functions instead of (or in addition
to) generating text. We define tools that map to display operations:

```python
TOOLS = [
    {
        'name': 'send_message',
        'description': 'Send a message to the flipdot display.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'body': {'type': 'string'},
                'transition': {'type': 'string'},
                'priority': {'type': 'integer'},
            },
            'required': ['body'],
        },
    },
    # ... get_display_status, clear_display, play_playlist, etc.
]
```

When Claude decides to send a message, it returns a `tool_use` block with the
message body and transition. Our code executes that tool call and sends the
result back. This loop continues until Claude is done:

```python
def _run_agent_loop(self, user_message):
    messages = [{'role': 'user', 'content': user_message}]

    for _ in range(10):  # max rounds
        response = self._client.messages.create(
            model=self._model,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({'role': 'assistant', 'content': response.content})

        if response.stop_reason == 'end_turn':
            return extract_text(response)

        # Execute tool calls, append results
        tool_results = []
        for block in response.content:
            if block.type == 'tool_use':
                result = self._execute_tool(block.name, block.input)
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': block.id,
                    'content': json.dumps(result),
                })
        messages.append({'role': 'user', 'content': tool_results})
```

## The System Prompt

The system prompt gives Claude its personality and constraints:

```
You are OpenClaw, an AI agent controlling a biopunk flipdot display.
The display is a 7-row × 30-column grid of electromagnetic dots...
Your personality: creative, slightly punk, technically sharp.
Messages must be under 200 characters (shorter is better).
ALL CAPS works best on flipdots.
```

This is where the character of the display comes from. Different system prompts
create different display personalities — a museum exhibit would be informative
and calm, while a hacker lab would be edgy and playful.

## Three Modes of Operation

### 1. Compose (on-demand)

Ask the agent to create something specific:

```bash
curl -X POST http://localhost:5000/api/openclaw/compose \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Write something about the intersection of biology and code"}'
```

The agent might respond by sending "DNA IS JUST LEGACY CODE" with the
`matrix_effect` transition — a creative decision it makes based on the prompt
and the display's capabilities.

### 2. React (event-driven)

The agent reacts to sensor events:

```python
# Called when webcam detects someone
app.openclaw.react('presence_detected', {'time': '14:30', 'day': 'Monday'})
```

Instead of the static "WELCOME" message, the AI might compose:
"MONDAY AFTERNOON HACKER DETECTED" with a `pop` transition.

### 3. Autonomous (periodic)

The autonomous loop runs every N minutes and lets the agent decide what to do:

```python
class AutonomousLoop:
    def _loop(self):
        while self._running:
            self._app.openclaw.autonomous_tick()
            time.sleep(self._interval)
```

During `autonomous_tick`, the agent checks display status (is anyone present?
what's playing?) and decides whether to act. It might:
- Start a playlist if the display is idle
- Compose a timely message ("LUNCH HOUR — GO EAT")
- Clear the display late at night
- React to patterns ("three voice messages in a row — something's happening")

## Enabling OpenClaw

```bash
# In .env or environment:
export ANTHROPIC_API_KEY=sk-ant-...
export OPENCLAW_ENABLED=true
export OPENCLAW_MODEL=claude-sonnet-4-6  # or claude-haiku-4-5

# Start autonomous mode via API:
curl -X POST http://localhost:5000/api/openclaw/auto/start
```

## Cost Considerations

Each agent call uses Claude API tokens. For autonomous mode running every 5
minutes, that's 288 calls/day. Using Haiku keeps costs minimal. The agent
loop is capped at 10 rounds, and most interactions complete in 1-3 rounds.

## The Bigger Picture

OpenClaw transforms the flipdot from a display into an *agent*. It doesn't
just show what it's told — it observes, decides, and acts. Combined with
the webcam, microphone, and gesture sensor, it becomes a physical AI
interface: a machine that can see you, hear you, and respond through
clicking electromagnetic dots.

That's biopunk.
