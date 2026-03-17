# Chapter 17: Workshop Mode — Collaborative Display

## The Display as a Shared Voice

Everything we've built so far assumes a single author: one person (or one AI)
deciding what the display shows. Workshop mode inverts that. Now the audience
decides.

Participants submit messages from their phones. A moderator approves them.
The audience votes. The top-voted message gets displayed. The flipdot becomes
a collective voice — a physical manifestation of what a room full of people
wants to say.

## Why This Matters for Education

In any classroom, workshop, or exhibition:
- **Some people won't raise their hand** — but they'll type on their phone
- **Questions get lost** in large groups — voting surfaces the most important ones
- **Engagement is measurable** — you can see participation in real-time
- **The display is democratic** — every submission has equal access to the queue

The QR code → phone submission flow has near-zero friction. No app to install,
no account to create. Scan, type, submit.

## The Architecture

```
Participant Phone                Facilitator
     │                               │
     ▼                               ▼
 /workshop/submit              /workshop/moderate
     │                               │
     ▼                               │
  Submission (status: pending) ──────┘
     │                          approve/reject
     ▼
  Submission (status: approved)
     │
     ├──── Audience votes (via submit page)
     │
     ▼
  "Play Top Voted" ──► Message Queue ──► Flipdot Display
```

## The Database Models

Two new models:

```python
class Submission(db.Model):
    body = db.Column(db.String(200), nullable=False)
    nickname = db.Column(db.String(30), default='ANON')
    status = db.Column(db.String(10), default='pending')  # pending/approved/rejected
    vote_count = db.Column(db.Integer, default=0)
    played = db.Column(db.Boolean, default=False)

class Vote(db.Model):
    submission_id = db.Column(db.Integer, db.ForeignKey(...))
    voter_id = db.Column(db.String(16))  # cookie-based
    # Unique constraint: one vote per voter per submission
```

### Why cookie-based voting?

We need *some* anti-stuffing mechanism, but we can't require login — that would
kill the zero-friction submission flow. A cookie-based voter ID is a reasonable
middle ground: it prevents casual double-voting without requiring authentication.

It's not bulletproof (clear cookies = vote again), but for a workshop setting
where the stakes are "which message shows on a flipdot display," it's appropriate.

## The Four Views

### 1. Submit (`/workshop/submit`)

Phone-optimized form with large inputs and a big submit button. Below the form,
approved messages are displayed with vote buttons. This is the only page
participants need.

The form uses standard HTML (no JavaScript framework) — maximum compatibility
with whatever phone people are carrying.

### 2. Board (`/workshop/board`)

A leaderboard showing approved submissions ranked by votes. Auto-refreshes every
5 seconds. Project this on a screen next to the flipdot display for a live
"what's winning" view.

The top 3 messages get gold styling. The first-place message gets a larger font.
This creates natural competition — people will lobby their neighbors to vote.

### 3. Moderate (`/workshop/moderate`)

The facilitator's dashboard. Left column: pending submissions (approve/reject).
Right column: approved messages sorted by votes, with "Send to Display" buttons.

A "Play Top Voted" button sends the highest-voted unplayed submission directly
to the display with priority 3 — jumping the queue.

Auto-refreshes every 10 seconds so the facilitator sees new submissions promptly.

### 4. QR Code (`/workshop/qr`)

Generates a QR code pointing to the submit page. Project this at the start of
a session. Uses the lightweight `qrcode-generator` library — renders client-side
as SVG, no server-side image generation needed.

## The API

Workshop mode exposes a full API for custom integrations:

```bash
# Submit flow
GET  /workshop/api/submissions          # list (optional ?status=pending)
POST /workshop/api/approve/<id>         # moderator approves
POST /workshop/api/reject/<id>          # moderator rejects

# Voting
POST /workshop/api/vote/<id>            # cast a vote

# Display control
POST /workshop/api/send/<id>            # send specific submission to display
POST /workshop/api/play-top             # send top-voted to display
```

## Workshop Flow

Here's how a typical session works:

1. **Setup**: Facilitator projects the QR code (`/workshop/qr`) on a screen
2. **Submit**: Participants scan and submit messages from their phones
3. **Moderate**: Facilitator approves appropriate messages (`/workshop/moderate`)
4. **Vote**: Participants see approved messages and vote on their favorites
5. **Display**: Facilitator hits "Play Top Voted" — the winning message clicks
   into existence on the flipdot display
6. **Repeat**: New round of submissions and votes

The board view (`/workshop/board`) can be projected alongside the flipdot
for a live scoreboard effect.

## Integration with OpenClaw

When OpenClaw is enabled, you can ask the AI to participate in workshop mode:

```bash
curl -X POST /api/openclaw/compose \
  -d '{"prompt": "Look at the workshop submissions and compose a response
       that synthesizes the themes people are talking about"}'
```

The AI reads recent submissions, identifies patterns, and composes a meta-message:
"THE ROOM AGREES: HACK EVERYTHING." It's a facilitator's tool — the AI as
rapporteur, summarizing the collective voice.

## Scaling Considerations

SQLite handles workshop-scale traffic easily (dozens of concurrent users). For
larger events (hundreds of phones submitting simultaneously), you'd want:
- PostgreSQL instead of SQLite
- Redis for the vote counting (atomic increments)
- WebSocket for live board updates instead of polling

But for a classroom, maker faire booth, or lab open house — the current
implementation is more than sufficient.

## The Bigger Picture

Workshop mode completes the circle. The flipdot display started as a thing you
*send messages to*. It grew into something that *sees, hears, and reacts*. Then
it gained *a mind of its own* with OpenClaw. Now it becomes *a voice for a room
full of people*.

One physical artifact. Seven rows of electromagnetic dots. And it can be:
- A message board
- A clock
- A weather station
- An autonomous AI agent
- A cellular automaton
- A collaborative canvas

That's what happens when you build systems that compose. Each chapter added a
capability. Each capability multiplied the possibilities of every other one.

That's biopunk engineering.
