from flask import render_template, flash, redirect, url_for, current_app
from app import db
from app.main import bp
from app.main.forms import MessageForm
from app.models import Message


@bp.route('/', methods=['GET', 'POST'])
def index():
    form = MessageForm()
    form.transition.choices = [(t, t) for t in current_app.display.available_transitions()]

    if form.validate_on_submit():
        msg = Message(body=form.message.data, transition=form.transition.data, source='web')
        db.session.add(msg)
        db.session.commit()
        current_app.message_queue.enqueue(
            msg.body, msg.transition, msg.priority, msg.id
        )
        flash(f'Queued: "{msg.body}" ({msg.transition})', 'success')
        return redirect(url_for('main.index'))

    recent = Message.query.order_by(Message.created_at.desc()).limit(20).all()
    return render_template('index.html', form=form, recent=recent)


@bp.route('/clear', methods=['POST'])
def clear():
    current_app.display.clear()
    flash('Display cleared.', 'info')
    return redirect(url_for('main.index'))
