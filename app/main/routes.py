from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import current_user, login_user, logout_user, login_required
from app import db
from app.main import bp
from app.main.forms import MessageForm, LoginForm, RegistrationForm
from app.models import Message, User


@bp.route('/', methods=['GET', 'POST'])
def index():
    form = MessageForm()
    form.transition.choices = [(t, t) for t in current_app.display.available_transitions()]

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Please log in to send messages.', 'warning')
            return redirect(url_for('main.login'))
        msg = Message(body=form.message.data, transition=form.transition.data,
                      source='web', user_id=current_user.id)
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
@login_required
def clear():
    current_app.display.clear()
    flash('Display cleared.', 'info')
    return redirect(url_for('main.index'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password.', 'warning')
            return redirect(url_for('main.login'))
        login_user(user)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.index'))
    return render_template('login.html', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Welcome, {user.username}! You can now log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', form=form)
