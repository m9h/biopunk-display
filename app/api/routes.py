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
    })


@bp.route('/display/clear', methods=['POST'])
def clear_display():
    current_app.display.clear()
    return jsonify({'status': 'ok'})
