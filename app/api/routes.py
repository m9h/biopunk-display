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


@bp.route('/display/frame', methods=['GET'])
def display_frame():
    """Return the current display frame as a 105-element array of ints.

    Each int is a column byte (0-127). First 30 = visible columns.
    Bit 0 = bottom row (row 6), bit 6 = top row (row 0).
    Used by the curses simulator in monitor mode.
    """
    player = getattr(current_app, '_automata_player', None)
    automaton = None
    if player and player.is_running:
        automaton = player._automaton

    return jsonify({
        'frame': current_app.display.last_frame,
        'queue_pending': current_app.message_queue.pending,
        'playlist_playing': current_app.playlists.now_playing,
        'automaton': automaton,
    })


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


# -- Generator endpoints (Chapter 15) --

@bp.route('/generators', methods=['GET'])
def list_generators():
    """List available generative art algorithms."""
    return jsonify({
        'generators': current_app.generators.list_generators(),
        'active': current_app.generators.active,
    })


@bp.route('/generators/start', methods=['POST'])
def start_generator():
    """Start a generative art algorithm on the display."""
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'name is required'}), 400

    seed = data.get('seed')
    tick_rate = data.get('tick_rate')

    try:
        current_app.generators.start(name, seed=seed, tick_rate=tick_rate)
        return jsonify({'status': 'running', 'generator': name})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@bp.route('/generators/stop', methods=['POST'])
def stop_generator():
    """Stop the currently running generator."""
    current_app.generators.stop()
    return jsonify({'status': 'stopped'})


# -- Stream endpoints (Chapter 16) --

@bp.route('/streams', methods=['GET'])
def list_streams():
    """List available and active data streams."""
    return jsonify({'streams': current_app.streams.list_sources()})


@bp.route('/streams/<name>/start', methods=['POST'])
def start_stream(name):
    """Start a data stream."""
    try:
        current_app.streams.start_stream(name)
        return jsonify({'status': 'started', 'stream': name})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@bp.route('/streams/<name>/stop', methods=['POST'])
def stop_stream(name):
    """Stop a data stream."""
    current_app.streams.stop_stream(name)
    return jsonify({'status': 'stopped', 'stream': name})


@bp.route('/streams/stop-all', methods=['POST'])
def stop_all_streams():
    """Stop all active data streams."""
    current_app.streams.stop_all()
    return jsonify({'status': 'all stopped'})


# -- Cellular Automata endpoints (legacy, from remote) --

@bp.route('/automata/start', methods=['POST'])
def automata_start():
    """Start a cellular automaton on the display.

    JSON body (all optional):
      automaton: "life" | "brain" | "elementary" | "cyclic" (default: "life")
      speed: seconds between generations (default: 0.3)
      rule: Wolfram rule number for elementary CA (default: 30)
      density: initial fill density 0.0-1.0 (default: 0.4)
      num_states: states for cyclic CA (default: 4)
      threshold: neighbor threshold for cyclic CA (default: 1)
    """
    # Stop any running automaton first
    player = getattr(current_app, '_automata_player', None)
    if player and player.is_running:
        player.stop()

    data = request.get_json() or {}
    automaton = data.get('automaton', 'life')
    if automaton not in ('life', 'brain', 'elementary', 'cyclic'):
        return jsonify({'error': 'automaton must be life, brain, elementary, or cyclic'}), 400

    speed = float(data.get('speed', 0.3))
    kwargs = {}
    if 'density' in data:
        kwargs['density'] = float(data['density'])
    if 'rule' in data:
        kwargs['rule'] = int(data['rule'])
    if 'num_states' in data:
        kwargs['num_states'] = int(data['num_states'])
    if 'threshold' in data:
        kwargs['threshold'] = int(data['threshold'])

    from app.display.automata import AutomataPlayer
    player = AutomataPlayer(current_app, automaton=automaton, speed=speed, **kwargs)
    player.start()
    current_app._automata_player = player

    return jsonify({
        'status': 'running',
        'automaton': automaton,
        'speed': speed,
        **kwargs,
    })


@bp.route('/automata/stop', methods=['POST'])
def automata_stop():
    """Stop the running cellular automaton."""
    player = getattr(current_app, '_automata_player', None)
    if player and player.is_running:
        player.stop()
        current_app.display.clear()
        return jsonify({'status': 'stopped'})
    return jsonify({'status': 'not running'})


@bp.route('/automata/status', methods=['GET'])
def automata_status():
    """Check if a cellular automaton is running."""
    player = getattr(current_app, '_automata_player', None)
    return jsonify({
        'running': player.is_running if player else False,
        'automaton': player._automaton if player and player.is_running else None,
    })


@bp.route('/automata/patterns', methods=['GET'])
def automata_patterns():
    """List available CA patterns from the pattern library."""
    import json
    import os
    path = os.path.join(current_app.config.get('PLAYLIST_DIR', 'playlists'), 'ca_patterns.json')
    try:
        with open(path) as f:
            data = json.load(f)
        patterns = [{'name': p['name'], 'automaton': p['automaton'],
                      'description': p.get('description', '')}
                     for p in data.get('patterns', [])]
        return jsonify({'patterns': patterns})
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'patterns': []})


@bp.route('/automata/patterns/<name>/play', methods=['POST'])
def automata_play_pattern(name):
    """Start a named pattern from the pattern library."""
    import json
    import os
    path = os.path.join(current_app.config.get('PLAYLIST_DIR', 'playlists'), 'ca_patterns.json')
    try:
        with open(path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'error': 'pattern library not found'}), 404

    # Find pattern by name (case-insensitive)
    pattern = None
    for p in data.get('patterns', []):
        if p['name'].lower() == name.lower():
            pattern = p
            break
    if not pattern:
        return jsonify({'error': f'pattern "{name}" not found'}), 404

    # Stop any running automaton
    player = getattr(current_app, '_automata_player', None)
    if player and player.is_running:
        player.stop()

    automaton = pattern['automaton']
    speed = pattern.get('speed', 0.3)
    kwargs = {}
    if 'cells' in pattern:
        kwargs['cells'] = pattern['cells']
    if 'density' in pattern:
        kwargs['density'] = float(pattern['density'])
    if 'rule' in pattern:
        kwargs['rule'] = int(pattern['rule'])
    if 'num_states' in pattern:
        kwargs['num_states'] = int(pattern['num_states'])
    if 'threshold' in pattern:
        kwargs['threshold'] = int(pattern['threshold'])

    from app.display.automata import AutomataPlayer
    player = AutomataPlayer(current_app, automaton=automaton, speed=speed, **kwargs)
    player.start()
    current_app._automata_player = player

    return jsonify({
        'status': 'running',
        'pattern': pattern['name'],
        'automaton': automaton,
        'speed': speed,
    })
