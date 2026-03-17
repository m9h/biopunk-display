from flask import jsonify, request, current_app
from app import db
from app.api import bp
from app.models import Message


@bp.route('/messages', methods=['POST'])
def create_message():
    data = request.get_json()
    if not data or not data.get('body'):
        return jsonify({'error': 'body is required'}), 400

    body = data['body'].strip()
    if not body or len(body) > 200:
        return jsonify({'error': 'body must be 1-200 characters'}), 400

    transitions = current_app.display.available_transitions()
    transition = data.get('transition', 'righttoleft')
    if transition not in transitions:
        transition = 'righttoleft'

    source = data.get('source', 'api')
    priority = min(max(int(data.get('priority', 0)), 0), 10)

    msg = Message(body=body, transition=transition, source=source, priority=priority)
    db.session.add(msg)
    db.session.commit()

    current_app.message_queue.enqueue(
        msg.body, msg.transition, msg.priority, msg.id
    )

    return jsonify(msg.to_dict()), 201


@bp.route('/messages', methods=['GET'])
def list_messages():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    pagination = Message.query.order_by(Message.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        'messages': [m.to_dict() for m in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    })


@bp.route('/messages/<int:id>', methods=['GET'])
def get_message(id):
    msg = db.get_or_404(Message, id)
    return jsonify(msg.to_dict())


@bp.route('/display/status', methods=['GET'])
def display_status():
    return jsonify({
        'transitions': current_app.display.available_transitions(),
        'connected': current_app.display._core is not None,
        'queue_pending': current_app.message_queue.pending,
        'webcam_present': getattr(current_app.webcam_input, 'is_present', False),
        'playlist_playing': current_app.playlists.now_playing,
        'openclaw_enabled': current_app.openclaw is not None,
    })


@bp.route('/display/clear', methods=['POST'])
def clear_display():
    current_app.display.clear()
    return jsonify({'status': 'ok'})


# -- Playlist endpoints (Chapter 12) --

@bp.route('/playlists', methods=['GET'])
def list_playlists():
    return jsonify({'playlists': current_app.playlists.list_playlists()})


@bp.route('/playlists/<filename>', methods=['GET'])
def get_playlist(filename):
    try:
        data = current_app.playlists.get_playlist(filename)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'error': 'not found'}), 404


@bp.route('/playlists', methods=['POST'])
def save_playlist():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('messages'):
        return jsonify({'error': 'name and messages required'}), 400
    filename = data.get('filename', data['name'].lower().replace(' ', '_'))
    filename = current_app.playlists.save_playlist(filename, data)
    return jsonify({'filename': filename, 'status': 'saved'}), 201


@bp.route('/playlists/<filename>/play', methods=['POST'])
def play_playlist(filename):
    try:
        current_app.playlists.play(filename)
        return jsonify({'status': 'playing', 'name': current_app.playlists.now_playing})
    except FileNotFoundError:
        return jsonify({'error': 'not found'}), 404


@bp.route('/playlists/stop', methods=['POST'])
def stop_playlist():
    current_app.playlists.stop()
    return jsonify({'status': 'stopped'})


# -- OpenClaw endpoints (Chapter 14) --

@bp.route('/openclaw/compose', methods=['POST'])
def openclaw_compose():
    """Ask OpenClaw to compose a message for the display."""
    if not current_app.openclaw:
        return jsonify({'error': 'OpenClaw not enabled'}), 503

    data = request.get_json() or {}
    prompt = data.get('prompt', '')
    context = data.get('context', {})

    result = current_app.openclaw.compose(prompt, context)
    return jsonify(result)


@bp.route('/openclaw/react', methods=['POST'])
def openclaw_react():
    """Ask OpenClaw to react to an event (presence, gesture, etc.)."""
    if not current_app.openclaw:
        return jsonify({'error': 'OpenClaw not enabled'}), 503

    data = request.get_json() or {}
    event_type = data.get('event', '')
    event_data = data.get('data', {})

    result = current_app.openclaw.react(event_type, event_data)
    return jsonify(result)


@bp.route('/openclaw/auto/start', methods=['POST'])
def openclaw_auto_start():
    """Start OpenClaw autonomous mode."""
    auto = getattr(current_app, 'openclaw_auto', None)
    if not auto:
        return jsonify({'error': 'Autonomous mode not available'}), 503
    auto.start()
    return jsonify({'status': 'started', 'interval': auto._interval})


@bp.route('/openclaw/auto/stop', methods=['POST'])
def openclaw_auto_stop():
    """Stop OpenClaw autonomous mode."""
    auto = getattr(current_app, 'openclaw_auto', None)
    if not auto:
        return jsonify({'error': 'Autonomous mode not available'}), 503
    auto.stop()
    return jsonify({'status': 'stopped'})


@bp.route('/openclaw/auto/status', methods=['GET'])
def openclaw_auto_status():
    """Check OpenClaw autonomous mode status."""
    auto = getattr(current_app, 'openclaw_auto', None)
    return jsonify({
        'enabled': current_app.openclaw is not None,
        'autonomous_running': auto.is_running if auto else False,
    })
