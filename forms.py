# from collections.abc import Sequence
# from typing import Any, Mapping
# from flask_wtf.form import _Auto
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField,ValidationError,IntegerField
from wtforms.validators import DataRequired, Email, EqualTo
import db_api 
    
# TODO - define validators (especially because of desired uniqueness of mail/username)
# @validator
def IsUnique(tablename):
    def is_unique(form,field):
        query=f'SELECT {field.name} FROM {tablename} WHERE {field.name}=%s LIMIT %s;'
        response=db_api.execute_query(query=query,values=(field.data,1))
        if len(response):
            raise ValidationError(f'The {field.name} "{field.data}" is already used. Please, choose a different one.')
    return is_unique

# @validator
def Exists(tablename):
    def exists(form,field):
        query=f'SELECT {field.name} FROM {tablename} WHERE {field.name}=%s LIMIT %s;'
        response=db_api.execute_query(query=query,values=(int(field.data),1))
        if 0==len(response):
            raise ValidationError(f'No record {field.name} with value "{field.data}" exists. Contact your admin to get your credentials (or register your company).')
    return exists

def RequiredLength(min=1,max=50):
    def exists(form,field):
        if min:
            if len(field.data)<min:
                raise ValidationError(f'The minimal allowed length is {min} characters.')
        if max:
            if len(field.data)>max:
                raise ValidationError(f'The maximal allowed length is {max} characters.')
    return exists

# def IsNumeric():
#     def is_numeric(form,field):
    
#         if ~len(response):
#             message=f'No record {field.name} with value "{field.data}" exists. Contact your admin to get your credentials (or register your company).'
#             return ValidationError(message=message)
#     return exists

class RegistrationFormUser(FlaskForm):    
    username = StringField('Username',validators=[DataRequired(),IsUnique(tablename='public_users')])
    e_mail = StringField('Email address',validators=[DataRequired(), Email(),IsUnique(tablename='public_users')])
    first_name = StringField('First name',validators=[DataRequired()])
    last_name = StringField('Last name',validators=[DataRequired()])
    # company_name = StringField('Company Name',validators=[DataRequired(),Exists(tablename='public_companies')])
    # company_id = IntegerField('Company ID',validators=[DataRequired(),Exists(tablename='public_companies')])
    company_id = StringField('Company ID',validators=[DataRequired(),Exists(tablename='public_companies')])
    # in future - add check if the company is in registered companies
    password = PasswordField('Password',validators=[DataRequired(),RequiredLength(min=8)])
    confirm_password = PasswordField('Confirm password',validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Submit')
    

# class RegistrationFormCompany(FlaskForm):
#     # in future - register companies in a smarter way
#     company_name = StringField('Company name',validators=[DataRequired()])
#     company_address = PasswordField('Company address',validators=[DataRequired()])
#     submit = SubmitField('Submit')

# class LoginForm(FlaskForm):
#     username_email = StringField('Username/Email',validators=[DataRequired()])
#     password = PasswordField('Password',validators=[DataRequired()])
#     submit=SubmitField('Login')