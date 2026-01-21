# from collections.abc import Sequence
# from typing import Any, Mapping
# from flask_wtf.form import _Auto
from flask_wtf import FlaskForm
# RecaptchaField
from flask import flash
from wtforms import StringField, PasswordField, SubmitField,ValidationError,IntegerField, TextAreaField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo
import db_api 
from flask_babel import lazy_gettext, _

messages={
    'email_already_used': lazy_gettext('This email address is already used. Please use a different one.'),
    'username_already_taken': lazy_gettext('This username is already taken. Please choose a different one.'),
    'company_name_already_taken': lazy_gettext('This company name is already taken. Please choose a different one.'),
    'passwords_must_match': lazy_gettext('Passwords must match.'),

}

# TODO - define validators (especially because of desired uniqueness of mail/username)
# @validator
def IsUnique(tablename, message=None):
    def is_unique(form,field):
        query=f'SELECT {field.name} FROM {tablename} WHERE {field.name}=%s LIMIT %s;'
        response=db_api.execute_query(query=query,values=(field.data,1))
        if len(response):
            raise ValidationError(message)
    return is_unique

# @validator
def Exists(tablename):
    def exists(form,field):
        # query=f'SELECT {field.name} FROM {tablename} WHERE {field.name}=%s LIMIT %s;'
        # response=db_api.execute_query(query=query,values=(int(field.data),1))
        query=f'SELECT {field.name} FROM {tablename} WHERE {field.name}='+'%s LIMIT %s;'
        response=db_api.execute_query(query=query,values=(field.data,1))
        if 0==len(response):
            # message=_('No record {field.name} with value "{field.data}" exists. Contact your admin to get your credentials.')
            message = lazy_gettext(
                'No record "%(field_name)s" with value "%(field_data)s" exists. '
                'Contact your admin to get your credentials.'
            ) % {'field_name': field.label.text, 'field_data': field.data}
            raise ValidationError(message)
    return exists

def ExistsAny(tablename):
    def something_exists(form,field):
        record_found=False
        for name in field.name.split('X'):
            query=f'SELECT {name} FROM {tablename} WHERE {name}=%s LIMIT %s;'
            response=db_api.execute_query(query=query,values=(field.data,1))
            if 1==len(response):
                record_found=True
        if not record_found:
            flash(_('Invalid username/email or password.'))
            raise ValidationError()
    return something_exists

def RequiredLength(min=1,max=50):
    def exists(form,field):
        if min:
            if len(field.data)<min:
                raise ValidationError(lazy_gettext('The minimal allowed length is {min} characters.').format(min=min))
        if max:
            if len(field.data)>max:
                raise ValidationError(lazy_gettext('The maximal allowed length is {max} characters.').format(max=max))
    return exists

def EmailOrNone():
    def email_or_none(form,field):
        if field.data:
            email_validator=Email()
            email_validator(form,field)
    return email_or_none

class RegistrationFormUser(FlaskForm):  
    username = StringField(lazy_gettext('Username'),validators=[DataRequired(),IsUnique(tablename='public_users', message=messages['username_already_taken']),RequiredLength(min=1,max=50)],)    
    e_mail = StringField(lazy_gettext('Email address'),
                         validators=[DataRequired(), Email(),IsUnique(tablename='public_users', message=messages['email_already_used']),RequiredLength(min=5,max=100)])
    first_name = StringField(lazy_gettext('First name'),validators=[DataRequired()])
    last_name = StringField(lazy_gettext('Last name'),validators=[DataRequired()])
    company_key = StringField(lazy_gettext('Company Key'),validators=[DataRequired(),Exists(tablename='public_companies')])
    password = PasswordField(lazy_gettext('Password'),validators=[DataRequired(),RequiredLength(min=8)])
    confirm_password = PasswordField(lazy_gettext('Confirm password'),validators=[DataRequired(), EqualTo('password', message=messages['passwords_must_match'])])
    submit = SubmitField(lazy_gettext('Submit'))
    # recaptcha = RecaptchaField()

class RegistrationFormCompany(FlaskForm):  
    company_name = StringField(lazy_gettext('Company Name'),validators=[DataRequired(),IsUnique(tablename='public_companies', message=messages['username_already_taken']),RequiredLength(min=1,max=50)],)    
    e_mail = StringField(lazy_gettext('Email address'),
                         validators=[DataRequired(), Email(),IsUnique(tablename='public_companies', message=messages['email_already_used']),RequiredLength(min=5,max=100)])
    company_address = StringField(lazy_gettext('Company address'),validators=[DataRequired()])
    submit = SubmitField(lazy_gettext('Submit'))

class LoginForm(FlaskForm):
    usernameXe_mail = StringField(lazy_gettext('Username/Email'),validators=[DataRequired(),ExistsAny(tablename='public_users')])
    password = PasswordField(lazy_gettext('Password'),validators=[DataRequired()])
    login=SubmitField(lazy_gettext('Login'))

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField(lazy_gettext('Old password'),validators=[DataRequired()])
    new_password = PasswordField(lazy_gettext('New password'),validators=[DataRequired(),RequiredLength(min=8)])
    confirm_new_password = PasswordField(lazy_gettext('Confirm new password'),validators=[DataRequired(), EqualTo('new_password', message=messages['passwords_must_match'])])
    submit = SubmitField(lazy_gettext('Submit'))

class ChangeForgottenPasswordForm(FlaskForm):
    new_password = PasswordField(lazy_gettext('New password'),validators=[DataRequired(),RequiredLength(min=8)])
    confirm_new_password = PasswordField(lazy_gettext('Confirm new password'),validators=[DataRequired(), EqualTo('new_password', message=messages['passwords_must_match'])])
    submit = SubmitField(lazy_gettext('Submit'))

class ForgottenPasswordForm(FlaskForm):
    e_mail = StringField(lazy_gettext('Your Email address'),validators=[DataRequired(), Email(),RequiredLength(min=5,max=100)])
    submit = SubmitField(lazy_gettext('Submit'))

class EditPersonalInformationForm(FlaskForm):
    # default values are taken from the database
    username = StringField(lazy_gettext('Username'),validators=[IsUnique(tablename='public_users', message=messages['username_already_taken']),RequiredLength(min=0,max=50)])
    first_name = StringField(lazy_gettext('First name'))
    last_name = StringField(lazy_gettext('Last name'))
    submit = SubmitField(lazy_gettext('Submit'))

    def validate(self, **kwargs):
        #   control that at least one field is filled in 
        if not any([self.username.data,self.first_name.data,self.last_name.data]):
            flash(_('At least one field must be filled in.'))
            return False
            # raise ValidationError('At least one field must be filled in.')
        return super(EditPersonalInformationForm, self).validate(**kwargs)  

class EditCompanyInformationForm(FlaskForm):
    # default values are taken from the database
    company_name = StringField(lazy_gettext('Company Name'),validators=[IsUnique(tablename='companies', message=messages['company_name_already_taken']),RequiredLength(min=0,max=100)])
    company_address = StringField(lazy_gettext('Company Address'),validators=[RequiredLength(min=0,max=200)])
    submit = SubmitField(lazy_gettext('Submit'))

    def validate(self, **kwargs):
        #   control that at least one field is filled in 
        if not any([self.company_name.data,self.company_address.data]):
            flash(_('At least one field must be filled in.'))
            return False
            # raise ValidationError('At least one field must be filled in.')
        return super(EditCompanyInformationForm, self).validate(**kwargs)  
    
class EmailForgotPasswordForm(FlaskForm):
    # default values are taken from the database
    e_mail = StringField(lazy_gettext(
        'Email address'),
        validators=[DataRequired(), Email(),
        Exists(tablename='public_users'), 
        RequiredLength(min=5,max=100)])
    submit = SubmitField(lazy_gettext('Submit'))

class ChangeEmailForm(FlaskForm):
    # default values are taken from the database
    e_mail = StringField(lazy_gettext('New email address'),validators=[DataRequired(), Email(), IsUnique(tablename='public_users', message=messages['email_already_used']),RequiredLength(min=5,max=100)])
    submit = SubmitField(lazy_gettext('Submit'))

class ContactForm(FlaskForm):
    name = StringField(lazy_gettext('Your Name'),validators=[DataRequired(),RequiredLength(min=1,max=100)])
    email = StringField(lazy_gettext('Email address'),validators=[DataRequired(), Email(),RequiredLength(min=5,max=100)])
    subject = StringField(lazy_gettext('Subject'),validators=[DataRequired(),RequiredLength(min=1,max=150)])
    message = TextAreaField(
        lazy_gettext('Message'),
        validators=[DataRequired(),RequiredLength(min=1,max=2000)], 
    )
    submit = SubmitField(lazy_gettext('Submit'))

class ExportReportForm(FlaskForm):
    ordering_party_name = StringField(lazy_gettext('Ordering Party Name'),validators=[RequiredLength(min=0,max=100)])
    ordering_party_address = StringField(lazy_gettext('Ordering Party Address'),validators=[RequiredLength(min=0,max=200)])
    ordering_party_e_mail = StringField(lazy_gettext('Ordering Party Email'),validators=[RequiredLength(min=0,max=100),EmailOrNone()])
    controlling_employee = SelectField(lazy_gettext('Controller/Employee Email'),choices=[],validators=[DataRequired()])
    submit = SubmitField(lazy_gettext('Submit'))

# class RegistrationFormCompany(FlaskForm):
#     # in future - register companies in a smarter way
#     company_name = StringField(lazy_gettext('Company name'),validators=[DataRequired()])
#     company_address = PasswordField(lazy_gettext('Company address'),validators=[DataRequired()])
#     submit = SubmitField(lazy_gettext('Submit'))
