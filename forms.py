from collections.abc import Sequence
from typing import Any, Mapping
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo

class RegistrationFormUser(FlaskForm):
    username = StringField('Username',validators=[DataRequired()])
    email = StringField('Email address',validators=[DataRequired(), Email()])
    first_name = StringField('First name',validators=[DataRequired()])
    last_name = StringField('Last name',validators=[DataRequired()])
    company = StringField('Company',validators=[DataRequired()])
    # in future - add check if the company is in registered companies
    password = PasswordField('Password',validators=[DataRequired()])
    confirm_password = PasswordField('Confirm password',validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Submit')
    # TODO - define validators (especially because of desired uniqueness of mail/username)
    

# class RegistrationFormCompany(FlaskForm):
#     # in future - register companies in a smarter way
#     company_name = StringField('Company name',validators=[DataRequired()])
#     company_address = PasswordField('Company address',validators=[DataRequired()])
#     submit = SubmitField('Submit')

# class LoginForm(FlaskForm):
#     username_email = StringField('Username/Email',validators=[DataRequired()])
#     password = PasswordField('Password',validators=[DataRequired()])
#     submit=SubmitField('Login')