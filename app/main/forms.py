from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError

from app.models import User


class MessageForm(FlaskForm):
    message = StringField('Message', validators=[DataRequired(), Length(max=200)],
                         render_kw={'placeholder': 'HELLO WORLD', 'autofocus': True})
    transition = SelectField('Transition', choices=[])
    submit = SubmitField('Send to Display')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4)])
    password2 = PasswordField('Confirm Password',
                              validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Username already taken.')
