# Chapter 3: Web Forms with Flask-WTF

## The Problem

Raw HTML forms are dangerous. Without protection, anyone can forge a POST request
and submit data to your app. This is called **CSRF** (Cross-Site Request Forgery),
and it's one of the OWASP Top 10 vulnerabilities.

## Flask-WTF to the Rescue

Flask-WTF wraps WTForms with Flask integration, giving us:
- **CSRF protection** — every form includes a hidden token that proves it came from our site
- **Validation** — check input length, required fields, etc. server-side
- **Rendering helpers** — generate form HTML with proper Bootstrap classes

### Defining the Form

```python
# app/main/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

class MessageForm(FlaskForm):
    message = StringField('Message',
        validators=[DataRequired(), Length(max=200)],
        render_kw={'placeholder': 'HELLO WORLD', 'autofocus': True})
    transition = SelectField('Transition', choices=[])
    submit = SubmitField('Send to Display')
```

Key points:
- `DataRequired()` ensures the field isn't empty
- `Length(max=200)` prevents oversized messages (the display can only show so much)
- `choices=[]` on the transition select — we populate this dynamically from the
  DisplayManager's available transitions in the route

### The Route

```python
@bp.route('/', methods=['GET', 'POST'])
def index():
    form = MessageForm()
    form.transition.choices = [
        (t, t) for t in current_app.display.available_transitions()
    ]

    if form.validate_on_submit():
        msg = Message(body=form.message.data, transition=form.transition.data, source='web')
        db.session.add(msg)
        db.session.commit()
        current_app.message_queue.enqueue(msg.body, msg.transition, msg.priority, msg.id)
        flash(f'Queued: "{msg.body}" ({msg.transition})', 'success')
        return redirect(url_for('main.index'))

    recent = Message.query.order_by(Message.created_at.desc()).limit(20).all()
    return render_template('index.html', form=form, recent=recent)
```

`form.validate_on_submit()` does two things:
1. Checks if this is a POST request
2. Runs all validators (CSRF token + field validators)

Only if both pass does it return `True`. The redirect after success follows the
**Post/Redirect/Get** pattern — preventing duplicate submissions on page refresh.

### The Template

```html
<form method="post">
  {{ form.hidden_tag() }}          {# CSRF token #}
  {{ form.message(class="form-control") }}
  {{ form.transition(class="form-select") }}
  {{ form.submit(class="btn btn-bio") }}
</form>
```

`form.hidden_tag()` renders the CSRF token as a hidden input. Without it, the form
submission will be rejected with a 400 error.

## What's Next

Chapter 4 adds the database — where every message gets logged so we have a history
of everything the display has shown.
