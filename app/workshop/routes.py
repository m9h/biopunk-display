"""
Workshop mode routes.

Three views:
  /workshop/submit     — phone-friendly form for participants (no auth)
  /workshop/moderate   — facilitator view (approve/reject/pin)
  /workshop/board      — live audience board showing submitted + voted messages
  /workshop/qr         — generates QR code for the submit URL

Plus API endpoints for voting and moderation actions.
"""

from flask import (
    render_template, request, jsonify, flash, redirect,
    url_for, current_app
)
from flask_login import login_required
from app import db
from app.workshop import bp
from app.workshop.models import Submission, Vote
from app.models import Message


# -- Participant views --

@bp.route('/submit', methods=['GET', 'POST'])
def submit():
    """Phone-friendly message submission form."""
    if request.method == 'POST':
        body = request.form.get('message', '').strip()
        nickname = request.form.get('nickname', 'ANON').strip() or 'ANON'

        if not body or len(body) > 200:
            flash('Message must be 1-200 characters.', 'warning')
            return redirect(url_for('workshop.submit'))

        sub = Submission(body=body, nickname=nickname[:30])
        db.session.add(sub)
        db.session.commit()

        flash('Submitted! Your message is awaiting moderation.', 'success')
        return redirect(url_for('workshop.submit'))

    # GET: show submissions and allow voting
    approved = Submission.query.filter_by(status='approved').order_by(
        Submission.vote_count.desc(), Submission.created_at.desc()
    ).limit(20).all()

    return render_template('workshop/submit.html', approved=approved)


@bp.route('/board')
def board():
    """Live board showing approved submissions ranked by votes."""
    submissions = Submission.query.filter_by(status='approved').order_by(
        Submission.vote_count.desc(), Submission.created_at.desc()
    ).limit(30).all()
    return render_template('workshop/board.html', submissions=submissions)


@bp.route('/qr')
def qr_code():
    """Generate a QR code pointing to the submit page."""
    return render_template('workshop/qr.html')


# -- Facilitator views --

@bp.route('/moderate')
@login_required
def moderate():
    """Facilitator moderation dashboard."""
    pending = Submission.query.filter_by(status='pending').order_by(
        Submission.created_at.asc()
    ).all()
    approved = Submission.query.filter_by(status='approved').order_by(
        Submission.vote_count.desc()
    ).limit(30).all()
    return render_template('workshop/moderate.html',
                           pending=pending, approved=approved)


# -- API endpoints --

@bp.route('/api/approve/<int:sub_id>', methods=['POST'])
@login_required
def approve(sub_id):
    """Approve a pending submission."""
    sub = db.get_or_404(Submission, sub_id)
    sub.status = 'approved'
    db.session.commit()
    return jsonify({'status': 'approved', 'id': sub.id})


@bp.route('/api/reject/<int:sub_id>', methods=['POST'])
@login_required
def reject(sub_id):
    """Reject a pending submission."""
    sub = db.get_or_404(Submission, sub_id)
    sub.status = 'rejected'
    db.session.commit()
    return jsonify({'status': 'rejected', 'id': sub.id})


@bp.route('/api/send/<int:sub_id>', methods=['POST'])
@login_required
def send_to_display(sub_id):
    """Send an approved submission to the display immediately."""
    sub = db.get_or_404(Submission, sub_id)
    if sub.status != 'approved':
        return jsonify({'error': 'Must be approved first'}), 400

    transition = request.json.get('transition', 'righttoleft') if request.is_json else 'righttoleft'

    msg = Message(body=sub.body, transition=transition,
                  source='workshop', priority=2)
    db.session.add(msg)
    sub.played = True
    db.session.commit()

    current_app.message_queue.enqueue(msg.body, msg.transition, msg.priority, msg.id)
    return jsonify({'status': 'sent', 'message_id': msg.id})


@bp.route('/api/vote/<int:sub_id>', methods=['POST'])
def vote(sub_id):
    """Upvote a submission. One vote per session (tracked by cookie)."""
    sub = db.get_or_404(Submission, sub_id)
    if sub.status != 'approved':
        return jsonify({'error': 'Can only vote on approved submissions'}), 400

    # Simple anti-stuffing: track voter by a session cookie value
    voter_id = request.cookies.get('workshop_voter', '')
    if not voter_id:
        import secrets
        voter_id = secrets.token_hex(8)

    # Check for existing vote
    existing = Vote.query.filter_by(submission_id=sub_id, voter_id=voter_id).first()
    if existing:
        return jsonify({'error': 'Already voted', 'votes': sub.vote_count}), 409

    v = Vote(submission_id=sub_id, voter_id=voter_id)
    db.session.add(v)
    sub.vote_count = Submission.vote_count + 1
    db.session.commit()

    # Refresh to get updated count
    db.session.refresh(sub)

    resp = jsonify({'status': 'voted', 'votes': sub.vote_count})
    resp.set_cookie('workshop_voter', voter_id, max_age=86400)
    return resp


@bp.route('/api/play-top', methods=['POST'])
@login_required
def play_top_voted():
    """Send the top-voted unplayed submission to the display."""
    sub = Submission.query.filter_by(
        status='approved', played=False
    ).order_by(Submission.vote_count.desc()).first()

    if not sub:
        return jsonify({'error': 'No unplayed approved submissions'}), 404

    msg = Message(body=sub.body, transition='pop', source='workshop', priority=3)
    db.session.add(msg)
    sub.played = True
    db.session.commit()

    current_app.message_queue.enqueue(msg.body, msg.transition, msg.priority, msg.id)
    return jsonify({
        'status': 'sent',
        'body': sub.body,
        'votes': sub.vote_count,
        'nickname': sub.nickname,
    })


@bp.route('/api/submissions', methods=['GET'])
def list_submissions():
    """List submissions with optional status filter."""
    status = request.args.get('status')
    query = Submission.query
    if status:
        query = query.filter_by(status=status)
    subs = query.order_by(Submission.vote_count.desc()).limit(50).all()
    return jsonify({'submissions': [s.to_dict() for s in subs]})
