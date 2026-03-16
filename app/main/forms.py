from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length


class MessageForm(FlaskForm):
    message = StringField('Message', validators=[DataRequired(), Length(max=200)],
                         render_kw={'placeholder': 'HELLO WORLD', 'autofocus': True})
    transition = SelectField('Transition', choices=[])
    submit = SubmitField('Send to Display')
