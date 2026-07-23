from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, IntegerField
from wtforms.validators import DataRequired
class AddDepartmentForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired()])
    chief = IntegerField('Главный (id)', validators=[DataRequired()])
    members= StringField('Партнёры', validators=[DataRequired()])
    email = StringField('Почта', validators=[DataRequired()])
    submit = SubmitField('Принять')