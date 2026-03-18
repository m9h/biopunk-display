# Chapter 17: Workshop Mode — Collaborative Display

## The Display as a Collective Voice

Everything we have built so far assumes a single author. One person types a
message on the web UI. One AI composes a thought through OpenClaw. One playlist
cycles through pre-written content. The display speaks, and the room listens.

Workshop mode inverts that relationship. Now the room speaks.

Participants pull out their phones, scan a QR code, and type whatever they want.
A moderator reviews submissions in real time. The audience votes. The
highest-voted message clicks into existence on the flipdot display -- 210
electromagnetic dots rearranging themselves into the words a room full of people
collectively chose.

This is not a novel idea. Audience response systems have existed since the 1960s
(Clayman's "clickers" at academic conferences). What is novel is the *medium*.
A projector screen showing poll results is forgettable. A physical display that
loudly, mechanically reconfigures itself to show what *you* typed -- that is
memorable. The clicking sound draws attention. The permanence of the dots
(they stay flipped until overwritten, no power needed) gives the message weight.
The constraint of 30 visible columns forces brevity. And the fact that everyone
in the room heard those dots flip, at the same moment, creates a shared
experience that a screen cannot replicate.

### Why This Matters for Education and Research

In any classroom, workshop, conference session, or exhibition:

- **Some people will not raise their hand** -- but they will type on their phone.
  Research on classroom participation consistently shows that anonymous digital
  channels increase response rates 2-3x compared to verbal Q&A, with the
  largest gains among women, introverts, and non-native speakers (see Stowell &
  Nelson, 2007; Trees & Jackson, 2007).

- **Questions get lost in large groups** -- voting surfaces the most important
  ones. When 40 people each have a question, the facilitator cannot call on all
  of them. But if 15 of those 40 voted for the same question, that question
  should be answered first. The voting mechanism performs distributed triage.

- **Engagement is measurable.** You can see how many people submitted, how many
  voted, how quickly submissions arrived after the QR code went up. This is
  real-time formative assessment data.

- **The display is democratic.** Every submission enters the same moderation
  queue. Every approved message gets the same vote button. The ranking algorithm
  does not care who you are -- it counts votes.

- **The friction is nearly zero.** No app to install, no account to create, no
  password to remember. Scan, type, submit. This matters enormously in practice:
  every step you add to a participation flow loses a fraction of your audience.
  Workshop mode has exactly three steps.

## Architecture: The Full Flow

Here is how a submission travels from a participant's phone to the flipdot
display:

```
Participant's Phone                  Facilitator's Laptop
       |                                     |
       v                                     v
  GET /workshop/submit                 GET /workshop/moderate
       |                                     |
       v                                     |
  POST /workshop/submit                      |
  (body + nickname)                          |
       |                                     |
       v                                     |
  Submission record created    ------------>  |
  (status: "pending")                        |
                                   sees pending submissions
                                   clicks Approve or Reject
                                             |
                                             v
                              POST /workshop/api/approve/<id>
                                             |
                                             v
                               Submission.status = "approved"
                                             |
       .-- appears on submit page -----------.
       |   and board page
       v
  Participants vote
  POST /workshop/api/vote/<id>
  (cookie-based voter ID)
       |
       v
  vote_count incremented
  Vote record created (unique constraint prevents double-voting)
       |
       v
  Facilitator clicks "Play Top Voted"
  POST /workshop/api/play-top
       |
       v
  Message record created (source='workshop', priority=3)
  Enqueued in the priority message queue
       |
       v
  MessageQueue dequeues --> DisplayManager renders --> flipdot clicks
```

Every arrow in this diagram is a standard HTTP request. No WebSockets, no
long-polling, no JavaScript framework. The submit page is a plain HTML form.
The moderation page uses `fetch()` for approve/reject actions but falls back
gracefully. The board page auto-refreshes with a `setTimeout`. This simplicity
is a feature: it works on every phone, every browser, every network condition.

### The Blueprint

Workshop mode is implemented as a Flask blueprint in `app/workshop/`. The
blueprint registers at the `/workshop` URL prefix:

```python
# app/workshop/__init__.py
from flask import Blueprint

bp = Blueprint('workshop', __name__, url_prefix='/workshop')

from app.workshop import routes  # noqa: E402, F401
```

This follows the same pattern as every other blueprint in the project. The
import at the bottom is the standard Flask idiom for registering routes after
the blueprint is created (avoiding circular imports).

## The Data Model

Workshop mode adds two tables to the database. They live in
`app/workshop/models.py`, separate from the core `Message` model, because they
represent a different domain: *participatory input* rather than *display
output*.

### Submission

```python
class Submission(db.Model):
    __tablename__ = 'workshop_submission'

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(200), nullable=False)
    nickname = db.Column(db.String(30), default='ANON')
    status = db.Column(db.String(10), default='pending')  # pending, approved, rejected
    vote_count = db.Column(db.Integer, default=0)
    played = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, index=True,
                           default=lambda: datetime.now(timezone.utc))

    votes = db.relationship('Vote', backref='submission', lazy='dynamic')
```

Let's walk through each field and the design decisions behind it:

**`body`** -- The message text. Capped at 200 characters. On a 30-column
flipdot display using a 5-pixel-wide font, 200 characters is approximately 33
display-widths of scrolling text. That is long enough for a meaningful sentence
but short enough that the display can render it in under a minute. The 200-char
limit also discourages essays and encourages the kind of concise, punchy
messages that work best on physical displays.

**`nickname`** -- Optional, defaults to `'ANON'`. We deliberately do not require
identification. In a classroom setting, anonymity encourages honest questions.
In an exhibition setting, most visitors will not bother filling it in -- and
that is fine. The nickname is truncated to 30 characters on the server side
(`nickname[:30]`) regardless of what the client sends.

**`status`** -- A simple string enum with three states: `pending`, `approved`,
`rejected`. This is the moderation state machine:

```
                   approve
  pending ──────────────────► approved ──────► played=True
     │                            │              (after display)
     │         reject             │
     └───────────────────► rejected
```

There is no transition from `rejected` back to `pending` or `approved`. This is
deliberate: once a moderator rejects something, it stays rejected. If you want
to reverse a mistake, approve it through a database query or build a UI for it.
The three-state model keeps the facilitator's cognitive load low -- they see a
message, they make a binary decision, they move on.

**`vote_count`** -- A denormalized counter. We could compute this by counting
`Vote` records, but that would mean a `COUNT(*)` query every time we sort
submissions by popularity. The denormalized counter lets us do a simple
`ORDER BY vote_count DESC` and get the leaderboard in one query. The tradeoff
is that we must keep it in sync with the `Vote` table -- which we do with a
single atomic update:

```python
sub.vote_count = Submission.vote_count + 1
db.session.commit()
```

Note the use of `Submission.vote_count + 1` rather than `sub.vote_count + 1`.
This generates a SQL `UPDATE ... SET vote_count = vote_count + 1` -- an atomic
increment that avoids race conditions if two people vote at the same instant.
This is a common SQLAlchemy pattern and an important one: naive Python-side
incrementing (`sub.vote_count += 1`) would be vulnerable to lost updates under
concurrent access.

**`played`** -- Boolean flag indicating whether this submission has been sent
to the display. The "Play Top Voted" feature filters for
`played=False` to avoid re-displaying messages. Once a message is played, it
still appears on the board (with a "played" badge) but will not be selected
again by the automatic play mechanism.

**`created_at`** -- Indexed for efficient time-based queries. Uses UTC
timestamps via `datetime.now(timezone.utc)`. The index matters because the
moderation view sorts pending submissions by creation time (oldest first, so the
facilitator processes them in order).

**`to_dict()`** -- Serialization method for the API. Returns all fields as
JSON-friendly types. The `created_at` field is formatted as an ISO 8601 string
with a `Z` suffix (UTC). This method is used by the `/workshop/api/submissions`
endpoint.

### Vote

```python
class Vote(db.Model):
    __tablename__ = 'workshop_vote'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('workshop_submission.id'),
                              nullable=False)
    voter_id = db.Column(db.String(16), nullable=False)  # cookie-based
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('submission_id', 'voter_id', name='uq_vote_unique'),
    )
```

The `Vote` model is intentionally minimal. It records *who* (by cookie ID)
voted for *what* (by submission ID) and *when*. The critical piece is the unique
constraint on `(submission_id, voter_id)` -- this enforces at the database level
that a single voter can only vote once per submission.

### Why Cookie-Based Voting?

This is a design decision worth discussing explicitly, because it touches on a
fundamental tension in participatory systems: **friction vs. integrity**.

At one extreme, you could require user accounts with email verification. This
gives you strong identity and prevents vote manipulation. But it also means
that half your audience will not participate -- they will not create an account
just to vote on what a flipdot display shows. You have traded integrity for
zero engagement.

At the other extreme, you could allow unlimited anonymous votes. No friction at
all. But then one person with `curl` and a `for` loop can stuff the ballot box
and undermine the entire system.

Cookie-based voting sits in the middle:

- **On first vote**, the server generates a random 16-character hex token
  (`secrets.token_hex(8)`) and sets it as a cookie with a 24-hour expiry.
- **On subsequent votes**, the server reads this cookie and uses it as the
  voter ID.
- **The unique constraint** prevents the same voter ID from voting twice on the
  same submission.

This prevents *casual* double-voting (tap the button twice, switch tabs, etc.)
without requiring *any* setup from the participant. It is not bulletproof --
clearing cookies, using incognito mode, or switching browsers all reset the
voter ID. But for a workshop setting where the stakes are "which message shows
on a flipdot display," this is an appropriate level of protection.

The cookie has a `max_age` of 86400 seconds (24 hours), which covers a full
conference day. After that, the cookie expires and the voter could vote again --
but by then the workshop is long over.

```python
voter_id = request.cookies.get('workshop_voter', '')
if not voter_id:
    import secrets
    voter_id = secrets.token_hex(8)

existing = Vote.query.filter_by(submission_id=sub_id, voter_id=voter_id).first()
if existing:
    return jsonify({'error': 'Already voted', 'votes': sub.vote_count}), 409

# ... create vote ...

resp = jsonify({'status': 'voted', 'votes': sub.vote_count})
resp.set_cookie('workshop_voter', voter_id, max_age=86400)
return resp
```

Notice that the cookie is set on the *response*, not checked against a session.
This means the voter ID persists across page loads but is not tied to Flask's
session machinery. It is a lightweight, stateless identity mechanism.

## The Four Views

Workshop mode has four HTML pages, each designed for a specific user and
context. All live in `app/templates/workshop/` and extend the project's
`base.html` template.

### 1. Submit Page (`/workshop/submit`)

This is the page participants see after scanning the QR code. It needs to work
on every phone, with every screen size, on potentially spotty WiFi. The design
priorities are:

1. **Large touch targets.** The input field is `form-control-lg` with
   `font-size: 1.4rem`. The submit button is full-width (`w-100`) and `btn-lg`.
   No one should struggle to tap the right thing on a phone screen.

2. **Minimal fields.** Just two: the message (required) and a nickname
   (optional). The message field has `autofocus` so the keyboard pops up
   immediately on mobile -- participants can start typing within one second of
   the page loading.

3. **Uppercase transformation.** The input has `text-transform: uppercase` via
   CSS. The flipdot display's built-in character set is uppercase-only (the
   hardware's font ROM was designed in the 1990s for transit signage), so
   showing uppercase in the form sets the right expectation.

4. **No JavaScript framework.** The form submits via standard HTML `POST`. This
   is critical for compatibility: it works on old phones, on phones with
   JavaScript disabled, on feature phones with basic browsers. The only
   JavaScript on the page is for the vote buttons on approved submissions --
   and even those degrade gracefully (the page still renders without JS; you
   just cannot vote inline).

Below the submission form, the page displays approved messages with vote
buttons:

```python
# GET: show submissions and allow voting
approved = Submission.query.filter_by(status='approved').order_by(
    Submission.vote_count.desc(), Submission.created_at.desc()
).limit(20).all()
```

The dual sort -- votes descending, then creation time descending -- means that
if two submissions have the same vote count, the newer one appears first. This
gives recent submissions a slight visibility advantage, preventing early
submissions from permanently dominating the list.

The vote button uses a simple `fetch()` call:

```javascript
function vote(id, btn) {
  fetch('/workshop/api/vote/' + id, {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      if (data.votes !== undefined) {
        btn.querySelector('.vote-count').textContent = data.votes;
        btn.disabled = true;
        btn.classList.add('disabled');
      }
    });
}
```

After a successful vote, the button disables itself and updates the count
inline. No page reload. This is a small but important UX detail: it gives
immediate feedback ("your vote counted") and prevents accidental double-taps
on the client side (in addition to the server-side duplicate check).

### 2. Board Page (`/workshop/board`)

The board is the "scoreboard" view -- designed to be projected on a screen next
to the flipdot display. It shows approved submissions ranked by vote count,
auto-refreshing every 5 seconds.

```python
@bp.route('/board')
def board():
    submissions = Submission.query.filter_by(status='approved').order_by(
        Submission.vote_count.desc(), Submission.created_at.desc()
    ).limit(30).all()
    return render_template('workshop/board.html', submissions=submissions)
```

The template uses visual hierarchy to create competitive energy:

- **Top 3 submissions** get gold-colored rank numbers. First place gets a
  larger font (`1.3rem` vs `1rem`). This creates a natural "leaderboard" effect
  -- people see their message at #4 and start lobbying their neighbors to vote.

- **Each entry** shows the rank, the message text, the vote count (with an
  upward triangle as a visual vote indicator), and the nickname.

- **Empty state** shows a friendly prompt: "No messages yet. Scan the QR code
  to submit!" -- useful when projecting the board before submissions start
  arriving.

The auto-refresh uses a simple `setTimeout`:

```javascript
setTimeout(() => location.reload(), 5000);
```

This is deliberately low-tech. A WebSocket connection would give truly
real-time updates, but it adds complexity (connection management, reconnection
logic, a WebSocket server) for minimal benefit. In a room of 30-50 people,
5-second polling provides "fast enough" updates. The board shifts and reranks
every few seconds as votes come in -- it feels alive without the engineering
overhead of real-time push.

### 3. Moderation Page (`/workshop/moderate`)

The facilitator's command center. This is the most complex view, with a
two-column layout:

**Left column: Pending submissions.** These are ordered by creation time
(oldest first), so the moderator works through them in the order they arrived.
Each submission shows the message text, the nickname, and the submission time.
Two buttons: a green checkmark (approve) and a red X (reject).

**Right column: Approved submissions.** Sorted by vote count descending. Each
entry shows the message, nickname, vote count, a "played" badge if it has
already been shown on the display, and a "Send" button to manually push it to
the display.

At the top of the right column: the **"Play Top Voted"** button. This is the
facilitator's primary action -- one tap sends the highest-voted unplayed
submission to the display.

The moderation actions use `fetch()` calls that update the UI inline:

```javascript
function moderate(id, action) {
  fetch('/workshop/api/' + action + '/' + id, {method: 'POST'})
    .then(() => {
      document.getElementById('sub-' + id).remove();
      setTimeout(() => location.reload(), 500);
    });
}
```

When the moderator approves a submission, it is removed from the pending list
immediately (no waiting for a page reload), and the page refreshes after 500ms
to update the approved list. This creates a smooth flow: click, see the
submission disappear from the left, see it appear on the right.

The auto-refresh interval is 10 seconds (longer than the board's 5 seconds).
The facilitator does not need the latest vote counts every 5 seconds -- they
need to see new pending submissions. Ten seconds is frequent enough that no
submission waits more than a few moments before appearing, but infrequent
enough that it does not interrupt the facilitator's workflow with constant
page reloads.

### 4. QR Code Page (`/workshop/qr`)

This is the "gateway" -- the first thing participants see. Project it on a
screen and say "scan this to submit a message."

The QR code is generated entirely client-side using the
[qrcode-generator](https://github.com/nicehash/qrcode-generator) library
loaded from a CDN:

```javascript
const submitUrl = window.location.origin + '/workshop/submit';
const qr = qrcode(0, 'M');
qr.addData(submitUrl);
qr.make();
document.getElementById('qr-container').innerHTML = qr.createSvgTag({
  cellSize: 8,
  margin: 0,
});
```

Why client-side? Because the QR code encodes the *current* URL, which depends
on the server's hostname and port. On a Raspberry Pi connected to a local
WiFi network, the URL might be `http://192.168.1.42:5000/workshop/submit`.
Generating the QR code client-side with `window.location.origin` means it
automatically adapts to whatever hostname the browser is using -- no
configuration needed.

The QR code renders as SVG, not a bitmap. SVG scales perfectly when projected
at any size, which matters when you are projecting it on a wall for a room of
50 people to scan simultaneously. The error correction level is 'M' (15%),
which tolerates moderate scanning conditions (slight angles, some distance from
the screen).

Below the QR code, the page shows the URL in plain text. This is a fallback
for anyone whose phone camera does not support QR scanning -- they can type
the URL manually.

## The API

All moderation and voting actions are exposed as API endpoints under
`/workshop/api/`. These are defined in the workshop blueprint's routes, not in
the main API blueprint. This keeps the workshop self-contained -- you can
register or unregister the entire `workshop` blueprint without affecting the
rest of the application.

### Submission Listing

```bash
# List all submissions (default: sorted by votes, limit 50)
curl http://localhost:5000/workshop/api/submissions

# Filter by status
curl http://localhost:5000/workshop/api/submissions?status=pending
curl http://localhost:5000/workshop/api/submissions?status=approved
```

Returns JSON with a `submissions` array. Each submission includes all fields
from `to_dict()`: id, body, nickname, status, vote_count, played, created_at.

### Moderation

```bash
# Approve a pending submission
curl -X POST http://localhost:5000/workshop/api/approve/42

# Reject a pending submission
curl -X POST http://localhost:5000/workshop/api/reject/42
```

Both return the new status and the submission ID. There is no authentication
on these endpoints -- in a workshop setting, the facilitator's laptop is the
security boundary. See the security section below for discussion.

### Voting

```bash
# Vote for a submission
curl -X POST http://localhost:5000/workshop/api/vote/42
```

Returns `{'status': 'voted', 'votes': <new_count>}` on success, or
`{'error': 'Already voted'}` with HTTP 409 if the voter has already voted.
Returns HTTP 400 if the submission is not in the `approved` state.

### Display Control

```bash
# Send a specific approved submission to the display
curl -X POST http://localhost:5000/workshop/api/send/42 \
  -H 'Content-Type: application/json' \
  -d '{"transition": "typewriter"}'

# Send the top-voted unplayed submission to the display
curl -X POST http://localhost:5000/workshop/api/play-top
```

The `send` endpoint accepts an optional `transition` parameter (defaults to
`'righttoleft'`). The `play-top` endpoint always uses the `'pop'` transition --
the dots appearing all at once, which creates a dramatic reveal moment
appropriate for the "winning" message.

### Integration with the Message Queue

When a submission is sent to the display (via either `send` or `play-top`), the
route creates a `Message` record and enqueues it:

```python
msg = Message(body=sub.body, transition='pop', source='workshop', priority=3)
db.session.add(msg)
sub.played = True
db.session.commit()

current_app.message_queue.enqueue(msg.body, msg.transition, msg.priority, msg.id)
```

The key detail is the `priority=3` on `play-top` (and `priority=2` on direct
send). The message queue is a priority queue -- higher priority messages are
displayed before lower priority ones. Regular web submissions default to
priority 0. Voice commands default to priority 1. Workshop messages at priority
2-3 jump ahead of the regular queue, which makes sense: when a facilitator hits
"Play Top Voted" in front of an audience, the message should appear promptly,
not wait behind a backlog of scheduled content.

The `source='workshop'` tag is important for analytics. You can query the
`Message` table later to see how many messages originated from workshop mode
versus web, API, voice, or other sources.

## Running a Workshop Session

Here is a step-by-step guide for facilitators -- the practical workflow that
ties the technical components together.

### Before the Session

1. **Network setup.** Connect the Raspberry Pi and your laptop to the same WiFi
   network. Note the Pi's IP address (`hostname -I` on the Pi, or check your
   router's DHCP lease table). If you are running a workshop where institutional
   WiFi is unreliable or heavily firewalled, consider bringing a portable
   router -- a $30 travel router creates a dedicated network that the Pi and all
   participant phones can join.

2. **Start the Flask server.** `flask run --host=0.0.0.0` (the `--host` flag
   is critical -- without it, Flask binds to `localhost` and is unreachable from
   other devices).

3. **Test the QR code.** Open `/workshop/qr` in a browser, scan it with your
   phone, verify that the submit page loads. If it does not, check firewall
   rules -- Fedora's firewalld may block port 5000 by default. Run
   `sudo firewall-cmd --add-port=5000/tcp` to open it.

4. **Clear old data** (if reusing from a previous session). There is no "reset"
   button in the UI, but a quick database operation works:
   ```python
   flask shell
   >>> from app.workshop.models import Submission, Vote
   >>> Vote.query.delete()
   >>> Submission.query.delete()
   >>> db.session.commit()
   ```

### During the Session

5. **Project the QR code.** Open `/workshop/qr` on the projector. Say something
   like: "Scan this code to send a message to the flipdot display. You don't
   need to install anything -- just point your camera at the code."

6. **Open the moderation page.** On your laptop (not the projector), open
   `/workshop/moderate`. This is your private dashboard -- participants should
   not see the pending queue or the reject button.

7. **Approve as submissions arrive.** The moderation page auto-refreshes every
   10 seconds. Approve appropriate messages, reject anything inappropriate. In
   practice, most submissions in an academic setting are fine. The moderation
   step exists primarily as a safety net, not as a gatekeeping mechanism.

8. **Switch the projector.** Once you have a few approved messages, switch the
   projector from the QR code page to the board page (`/workshop/board`). Now
   the audience can see the leaderboard updating in real time as votes come in.
   (Keep the QR code URL visible somewhere -- write it on a whiteboard, or put
   a small printed QR code on each table.)

9. **Play messages.** When the moment is right -- after a voting round, during
   a natural pause -- hit "Play Top Voted" on the moderation page. The winning
   message appears on the flipdot display. The room hears the dots flip. This
   is the payoff moment.

10. **Repeat.** New submissions arrive, new votes accumulate, the leaderboard
    shifts. Play the next top-voted message when ready. The cycle of
    submit-vote-display creates a natural rhythm for the session.

### After the Session

11. **Export the data.** The API makes this easy:
    ```bash
    curl http://localhost:5000/workshop/api/submissions > workshop_data.json
    ```
    This gives you a JSON file with every submission, its vote count, whether
    it was played, and its timestamp. This is valuable data -- you can analyze
    what themes emerged, how participation changed over time, which messages
    resonated most strongly.

## Moderation: Why It Matters and How to Do It Well

The moderation step might seem like unnecessary friction. Why not let everything
through and let the voting handle quality?

Three reasons:

1. **Safety.** In any anonymous submission system, some fraction of inputs will
   be inappropriate -- offensive language, personal attacks, spam. This is not
   cynicism; it is a well-documented pattern in every system from YouTube
   comments to conference Q&A apps. The moderation step ensures that nothing
   harmful reaches the public board or the display.

2. **Relevance.** In a focused workshop (say, a brainstorming session on a
   specific topic), off-topic submissions dilute the signal. The moderator can
   keep the conversation on track without needing to publicly call anyone out.

3. **Pacing.** The moderator controls the flow. If 50 submissions arrive in
   the first minute, the moderator can approve them in batches of 5-10,
   preventing the board from being immediately overwhelmed. This is a
   facilitation skill, not a technical feature, but the moderation step makes
   it possible.

### Moderation Best Practices

- **Approve generously.** Unless a message is clearly inappropriate or
  off-topic, let it through. The voting system will surface quality.
- **Be fast.** The biggest frustration for participants is submitting a message
  and waiting. Try to process the pending queue every 30-60 seconds.
- **Delegate if possible.** In a large event, have a co-facilitator dedicated
  to moderation while you focus on the room.
- **Announce rejections gently.** If you are rejecting a lot of messages, say
  something like "Remember, messages should be about [topic]. Rephrase and
  resubmit if your message didn't come through." Do not call out individuals.

## The Voting System: Surfacing Collective Intelligence

The voting mechanism is intentionally simple: one vote per person per
submission, counted as a running total. There is no downvoting. This design
choice has consequences.

### Why No Downvotes?

Downvotes introduce negativity. In a workshop setting, you want people to feel
safe submitting. If participants see their message getting downvoted, they are
less likely to submit again. Upvote-only systems create a positive feedback
loop: good messages rise, mediocre messages stay low, but nobody feels
punished.

This is the same reasoning behind the design of many successful Q&A platforms
(Slido, Mentimeter) and is supported by research on participation in
deliberative processes. Negative feedback in public settings has an outsized
chilling effect on contribution rates.

### The Ranking Algorithm

The current ranking is straightforward: sort by `vote_count` descending, then
by `created_at` descending as a tiebreaker. This means:

- More votes = higher rank.
- Among equally-voted submissions, newer ones appear higher.

This is a simple majority-rules system. For most workshop scenarios, it works
well. But it has a known limitation: **early submissions accumulate more votes**
because they have been visible longer. A brilliant message submitted late in the
session may never catch up to an adequate message that was approved early.

If this becomes a problem in practice, consider these algorithmic
improvements:

- **Time-decayed scoring.** Weight votes by recency:
  `score = votes / (hours_since_submission + 1)`. This is similar to Hacker
  News's ranking algorithm and gives newer submissions a fair chance.
- **Round-based voting.** Clear the board every N minutes and start fresh. This
  is how many workshop facilitation tools handle the problem.
- **Random promotion.** Periodically surface a random low-voted submission to
  the top of the board. This introduces exploration into the system -- borrowed
  from multi-armed bandit algorithms used in recommendation systems.

These are extensions, not changes to the core model. The database schema
supports all of them -- you only need to change the query in the `board` and
`submit` routes.

## Security Considerations

Workshop mode is designed for *trusted environments* -- a classroom, a
conference, a lab. It is not designed to be exposed to the open internet. That
said, even in trusted environments, a few security considerations matter.

### No Authentication on Moderation

The moderation endpoints (`/workshop/api/approve/<id>`,
`/workshop/api/reject/<id>`, `/workshop/api/send/<id>`,
`/workshop/api/play-top`) have no authentication. Anyone who knows the URL can
approve, reject, or play submissions.

In a workshop setting, this is acceptable: the facilitator is the only person
who knows the moderation URL, and the network is local. But if you want to add
protection, the simplest approach is to require Flask-Login authentication on
the moderation routes. The project already has user auth (Chapter 10) -- adding
`@login_required` to the `moderate` view and the API endpoints is a one-line
change per route.

### Rate Limiting

The submission endpoint has no rate limiting. A participant could submit
hundreds of messages per second using `curl`. In practice, the moderation step
is the rate limiter -- even if someone floods the pending queue, the moderator
simply does not approve the spam.

For stronger protection, add rate limiting with Flask-Limiter:

```python
from flask_limiter import Limiter
limiter = Limiter(key_func=get_remote_address)

@bp.route('/submit', methods=['POST'])
@limiter.limit("5 per minute")
def submit():
    ...
```

Five submissions per minute per IP is generous enough for legitimate use and
restrictive enough to prevent flooding.

### Input Validation

The server validates submission length (1-200 characters) and truncates
nicknames to 30 characters. The message body is stored as-is -- no HTML
sanitization is applied at the input stage. This is safe because Jinja2's
default template rendering auto-escapes all variables, preventing XSS. If you
use the API to read submissions and render them in a non-Jinja2 context,
you must sanitize the output yourself.

### Cookie Security

The voter cookie (`workshop_voter`) is not signed or encrypted. It is a plain
hex string. This means a technically sophisticated participant could forge a
voter ID to vote multiple times. For a workshop setting, this is an acceptable
risk. If you need stronger protection, use Flask's signed cookies
(`session['voter_id']`) or move to server-side sessions with Flask-Session.

### Network Isolation

The strongest security measure is also the simplest: run on an isolated
network. A travel router with no internet uplink creates a closed network where
the Pi is the only server. Participants can reach the workshop pages but
nothing else. This eliminates entire classes of attacks (no external traffic,
no DNS poisoning, no man-in-the-middle on public WiFi).

## Use Cases

Workshop mode is a general-purpose participatory input system. Here are
concrete scenarios, each with specific setup advice.

### Classroom Q&A

**Setup:** QR code projected at the start of a lecture. Board page on a second
screen (or split-screen with slides). Moderator is the instructor or a TA.

**Flow:** Students submit questions during the lecture. The TA approves them.
During natural breaks, the instructor checks the board: "I see the top question
is about the difference between supervised and unsupervised learning -- let me
address that." After answering, hit "Play Top Voted" to show the question on
the flipdot display (a physical acknowledgment that the question was heard).

**Why it works:** Students who would never raise their hand will type a question
on their phone. The voting surfaces the questions that many students share but
none would ask individually.

### Conference Feedback Wall

**Setup:** The flipdot display is in a hallway or foyer. A printed QR code is
next to it. The board page runs on a nearby screen. An organizer moderates from
their phone.

**Flow:** Attendees scan the QR code between sessions. They submit reactions,
questions, or ideas. The organizer approves and occasionally plays the top-voted
message. Over the course of a day, the display becomes a living record of the
conference's collective conversation.

**Why it works:** Conference hallways are dead space. The display turns them
into a participation point. The QR code catches people during the moments they
are most likely to engage -- waiting for the next talk, getting coffee, milling
around a poster session.

### Exhibition Interactive

**Setup:** The display is part of a museum or gallery installation. A printed
QR code is part of the exhibit label. No moderation -- set up an auto-approve
mechanism (or approve generously from a back-of-house tablet).

**Flow:** Visitors approach the exhibit, scan the code, type a response to a
prompt ("What does this artwork make you feel?"), and see their response join
the queue. The display cycles through responses automatically.

**Why it works:** Visitor engagement in museums drops sharply after 30 seconds
at a piece. An interactive element -- especially one that produces a physical,
audible response -- extends dwell time and creates a sense of connection with
other visitors.

### Brainstorming Session

**Setup:** Small group (5-20 people). QR code on a whiteboard. Moderator is
the session leader.

**Flow:** "Everyone take 2 minutes to submit your craziest idea for the next
product feature." Submissions arrive. The group votes. The top 3 ideas appear
on the display. Those become the starting points for deeper discussion.

**Why it works:** Brainstorming research (Paulus & Nijstad, 2003) shows that
electronic brainstorming -- where people submit ideas simultaneously and
anonymously -- produces more ideas and more diverse ideas than verbal
brainstorming. Workshop mode implements this with zero setup.

### Icebreaker / Social Event

**Setup:** The display is at a party, meetup, or conference reception. QR code
on tables or at the bar. No moderation (or very light moderation).

**Flow:** People submit jokes, greetings, inside references. The display
becomes a social object -- people gather around it, laugh at what appears,
debate what to submit next.

**Why it works:** The display creates a shared focal point. It turns a room
of strangers into a group of people with a common activity. The physical
clicking of the dots is an attention magnet -- people notice it, walk over,
and get drawn in.

## Integration with OpenClaw

When OpenClaw (Chapter 14) is enabled, the AI can participate in workshop
mode as a synthesizer of collective input. The facilitator can ask OpenClaw
to read recent submissions and compose a meta-message:

```bash
curl -X POST http://localhost:5000/api/openclaw/compose \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Read the workshop submissions and summarize the themes.",
       "context": {"source": "workshop"}}'
```

The AI reads the submissions, identifies patterns, and composes a response:
"THE ROOM SAYS: MAKE IT WEIRD AND MAKE IT LOUD." This is the AI acting as
rapporteur -- distilling the collective voice into a single statement.

This is a powerful facilitation tool. In a brainstorming session, it surfaces
themes that no individual participant might have noticed. In a Q&A, it
identifies the underlying concern behind multiple related questions. The AI
does not replace the human facilitator -- it augments them with the ability to
process 50 submissions simultaneously and find the signal.

## Deployment Tips

### Local WiFi Considerations

Workshop mode is designed to work on a local network, not over the internet.
This affects deployment:

- **Use a static IP or hostname** so the QR code URL does not change between
  sessions. On Fedora, set a static IP with NetworkManager:
  `nmcli con mod "Your WiFi" ipv4.addresses 192.168.1.42/24 ipv4.method manual`

- **DNS is optional** but nice. If you control the router, add a DHCP
  reservation and a local DNS entry like `flipdot.local`. The QR code pointing
  to `http://flipdot.local:5000/workshop/submit` is cleaner than an IP address.

- **Test with multiple phones** before the session. Different phones, different
  OS versions, different browsers. The submit page is intentionally simple HTML,
  but it is worth verifying on the actual devices your audience will use.

### QR Code Generation

The built-in QR page generates codes dynamically based on `window.location`.
For printed materials (posters, handouts, table cards), you may want to
generate QR codes offline:

```bash
# Using Python's qrcode library
pip install qrcode[pil]
python -c "
import qrcode
qr = qrcode.make('http://192.168.1.42:5000/workshop/submit')
qr.save('workshop_qr.png')
"
```

Print this at a large size. QR codes need sufficient contrast and resolution
to scan reliably from a distance. A 4-inch square works for table cards; an
8-inch square works for wall posters.

### Projecting the Board

The board page (`/workshop/board`) is designed for projection. A few tips:

- **Use a dark room theme.** The default biopunk theme has a dark background,
  which works well on projectors (less blinding, better contrast).
- **Full-screen the browser** (F11 on most browsers) to hide the address bar
  and tabs.
- **Increase zoom** to 150-200% so the text is readable from the back of the
  room.
- **Dual output:** If you have two projector outputs, put the QR code on one
  and the board on the other. If you have only one, switch between them --
  start with the QR code, switch to the board once submissions are flowing.

### Scaling Up

SQLite handles workshop-scale traffic well -- dozens of concurrent users
submitting and voting. For larger events (hundreds of simultaneous
participants), consider:

- **PostgreSQL** instead of SQLite. Flask-SQLAlchemy makes this a configuration
  change (`SQLALCHEMY_DATABASE_URI`), no code changes needed.
- **Redis for vote counting.** Atomic `INCR` operations in Redis handle
  concurrent votes better than SQL `UPDATE` under very high load.
- **WebSockets for live updates** instead of polling. Flask-SocketIO would let
  the board update instantly when a vote is cast, without the 5-second refresh
  delay.
- **A reverse proxy** (nginx) in front of Flask, especially if serving to
  hundreds of concurrent connections.

But be honest about your scale. If you are running a classroom of 40 or a
conference session of 100, SQLite and polling are more than sufficient. Do not
add infrastructure complexity for a problem you do not have.

## The Educational Angle

### Participatory Design

Workshop mode is itself an exercise in **participatory design** -- a design
methodology where the people who will use a system are involved in its creation.
By giving the audience control over what the display shows, you are implicitly
asking: what does this group think is important? What do they find funny? What
question is burning in their minds?

The submissions and votes are design data. Analyze them after the session:
- Which messages got the most votes? Why?
- What themes emerged? Were they what you expected?
- Did participation change over time? (Usually it spikes early, dips, then
  surges when people see the first message displayed.)
- Were there messages you rejected? What does that tell you about the gap
  between what the audience wants and what the facilitator thinks is
  appropriate?

### Collective Intelligence

The voting system is a minimal implementation of a **collective intelligence**
mechanism -- the idea that groups can make better decisions than individuals.
The canonical example is Galton's ox-weighing experiment (1906), where the
median of 787 guesses at an ox's weight was within 1% of the actual weight.

Workshop mode is not estimating ox weights, but it is performing distributed
prioritization: which message is most worth displaying? The group's answer
(via votes) is often better than any individual's answer -- including the
facilitator's. Messages that get the most votes tend to be the ones that
resonate with the broadest cross-section of the room, which is exactly what
you want on a shared display.

### Accessibility

The zero-friction design is an accessibility feature. No account creation means
no barriers for people with cognitive disabilities who struggle with
registration flows. Large touch targets help people with motor impairments.
The uppercase text is inherently higher-contrast and more legible. The lack of
JavaScript dependence means screen readers can parse the submit form.

That said, there is room for improvement:
- The vote button lacks an `aria-label` (it just shows a triangle and a number).
- The board page's auto-refresh could be jarring for screen reader users.
- Color should not be the only indicator of rank (the gold vs. green styling is
  supplemented by the rank number, which is good).

These are all addressable with small template changes -- good exercises for
students learning about web accessibility.

## Exercises

### Getting Started

1. **Run a mock workshop.** Set up the system on your local machine. Open four
   browser tabs: submit, board, moderate, and QR code. Submit 10 messages from
   the submit page (use different nicknames). Approve them. Vote. Play the
   top-voted one. Get a feel for the facilitator's workflow.

2. **Inspect the database.** After your mock workshop, open a `flask shell`:
   ```python
   from app.workshop.models import Submission, Vote
   for s in Submission.query.order_by(Submission.vote_count.desc()).all():
       print(f'{s.vote_count} votes: {s.body} (by {s.nickname}, {s.status})')
   ```
   How many votes were cast? Can you reconstruct the voting pattern from the
   `Vote` table?

3. **Test the API with curl.** Submit a message, approve it, vote on it, and
   play it -- all from the command line. This exercises every endpoint and
   teaches you the API contract:
   ```bash
   # Submit via the form endpoint (HTML POST)
   curl -X POST http://localhost:5000/workshop/submit \
     -d 'message=HELLO FROM CURL&nickname=TERMINAL'

   # Check pending submissions via API
   curl http://localhost:5000/workshop/api/submissions?status=pending

   # Approve (replace 1 with the actual ID)
   curl -X POST http://localhost:5000/workshop/api/approve/1

   # Vote
   curl -X POST http://localhost:5000/workshop/api/vote/1

   # Play
   curl -X POST http://localhost:5000/workshop/api/play-top
   ```

### Intermediate

4. **Add authentication to moderation.** Import `login_required` from
   `flask_login` and add it to the `moderate`, `approve`, `reject`, `send`,
   and `play_top` routes. Test that unauthenticated users get redirected to
   the login page. How does this change the facilitator workflow?

5. **Implement time-decayed ranking.** Modify the `board` route to sort by
   `vote_count / (hours_since_creation + 1)` instead of raw vote count. You
   will need to compute this in Python (SQLite's datetime functions are
   limited) or use a hybrid query. Compare the board rankings with and without
   time decay.

6. **Add a "reset" endpoint.** Create `POST /workshop/api/reset` that deletes
   all submissions and votes. Add a "Reset" button to the moderation page.
   Think about safety: what happens if you accidentally hit it mid-session?
   Should it require confirmation?

### Advanced

7. **Real-time board with WebSockets.** Replace the polling-based board with
   Flask-SocketIO. Emit an event whenever a vote is cast or a submission is
   approved. The board should update instantly without page reloads. Measure
   the difference in perceived responsiveness.

8. **Vote analytics dashboard.** Build a new page (`/workshop/analytics`) that
   shows:
   - Submissions per minute over time (line chart)
   - Vote distribution (histogram)
   - Most active nicknames (bar chart)
   - Word cloud of submission text
   Use a charting library (Chart.js, Plotly) or render server-side with
   matplotlib.

9. **Multi-room support.** Extend the data model to support multiple
   simultaneous workshops (e.g., different conference tracks). Add a `room`
   field to `Submission`. Generate different QR codes for each room. The board
   page shows only submissions for the current room. Think about how this
   changes the URL structure and the facilitator workflow.

10. **AI-assisted moderation.** Use OpenClaw to pre-screen submissions. When
    a new submission arrives, ask the AI: "Is this message appropriate for a
    professional workshop? Is it on-topic?" Auto-approve messages the AI
    considers safe, flag borderline ones for human review. This reduces the
    moderator's workload while maintaining the safety net.

## Further Reading

- Stowell, J.R. & Nelson, J.M. (2007). "Benefits of Electronic Audience
  Response Systems on Student Participation, Learning, and Emotion."
  *Teaching of Psychology*, 34(4), 253-258.
- Trees, A.R. & Jackson, M.H. (2007). "The Learning Environment in Clicker
  Classrooms." *Learning, Media and Technology*, 32(1), 21-40.
- Paulus, P.B. & Nijstad, B.A. (2003). *Group Creativity: Innovation Through
  Collaboration*. Oxford University Press.
- Surowiecki, J. (2004). *The Wisdom of Crowds*. Doubleday. -- Accessible
  introduction to collective intelligence, including Galton's ox experiment.
- Woolley, A.W. et al. (2010). "Evidence for a Collective Intelligence Factor
  in the Performance of Human Groups." *Science*, 330(6004), 686-688.

## What's Next

Workshop mode completes a circle. The flipdot display started as a thing you
*send messages to*. It grew into something that *sees, hears, and reacts*
through voice, gesture, and webcam input. It gained *a mind of its own* with
OpenClaw. It became *an artistic medium* with generative art. It became *a
window on the world* with live data streams. And now it becomes *a voice for
a room full of people*.

One physical artifact. Seven rows of electromagnetic dots. And it can be a
message board, a clock, a weather station, an autonomous AI agent, a cellular
automaton, a data dashboard, and a collaborative canvas -- sometimes all in the
same afternoon.

That is what happens when you build systems that compose. Each chapter added a
capability. Each capability multiplied the possibilities of every other one.
The priority queue accepts messages from any source. The display manager renders
any content. The blueprint architecture lets you add new input modalities
without touching existing code. The whole system is less than the sum of its
parts -- it is the *product*.

The next chapter takes this composability further, connecting workshop mode to
the scheduler to automate session flows. But even without that, what you have
now is a complete participatory display system that you can deploy at your next
class, workshop, conference, or exhibition. The QR code is ready. The display
is waiting. What will your room say?
