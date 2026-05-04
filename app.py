# Packages
# import gunicorn
import uuid
from attrs import field
import pendulum as pdl
from db_api import User
import requests
from flask import (Flask, render_template, request, send_file, 
                   send_from_directory, flash, redirect,
                   session, url_for, abort, g)
from flask_mail import Mail, Message
from wtforms import StringField
# from flask_login import login_manager, UserMixin, login_required,
import werkzeug.security as ws
from werkzeug.local import LocalProxy
from PIL import Image
import numpy as np
import io
import imagehash
from skimage.filters.rank import entropy
from skimage.morphology import disk
from skimage import img_as_ubyte
import cv2
import time
from datetime import timedelta
import secrets
import string
import os
# from rembg import remove
from db_api import *
import db_api
import json
import base64
from matplotlib.path import Path as polygon_path
from icecream import ic
from rich.traceback import install
from typing import Iterable, Literal, cast, Any
from flask_talisman import Talisman
import flask_limiter
import threading
from werkzeug.middleware.proxy_fix import ProxyFix
install()

from dotenv import load_dotenv
from warnings import warn,WarningMessage
import torch
from typing_extensions import deprecated
from models import discover_models, load_model, add_session_to_loaded_model, pop_session_from_loaded_models, inference
import models
import decimal
from flask_babel import Babel, _
#Similarity controller
import app_similarity_controller 
similarity_controller = app_similarity_controller.ImageSimilarityController()
from app_report_exporter import exporter_registry
# Apps
import forms 
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from db_api import db_name, db_user, dbpwd, db_host
from flask_session import Session
from sqlalchemy import create_engine
from flask_sqlalchemy import SQLAlchemy
import pickle, zlib
import time

load_dotenv(dotenv_path='.env')
RECAPTCHA_SITE_KEY=os.getenv('RECAPTCHA_SITE_KEY')
RECAPTCHA_SECRET_KEY=os.getenv('RECAPTCHA_SECRET_KEY')

app = Flask(__name__) # set debug to False for production
# app.config['RECAPTCHA_PUBLIC_KEY'] = RECAPTCHA_SITE_KEY
# app.config['RECAPTCHA_PRIVATE_KEY'] = RECAPTCHA_SECRET_KEY


# SESSION CONFIGURATION - FOR MULTIPLE WORKERS AND PERSISTENT SESSIONS
SESSION_LIFETIME_UNAUTHENTICATED = timedelta(minutes=int(os.getenv('SESSION_LIFETIME_UNAUTHENTICATED', 20)))  # session lifetime for unauthenticated users
SESSION_LIFETIME_AUTHENTICATED = timedelta(hours=int(os.getenv('SESSION_LIFETIME_AUTHENTICATED', 8)))  # session lifetime for authenticated users

app.config['SESSION_TYPE'] = 'sqlalchemy'
# Flask-SQLAlchemy config
app.config['SQLALCHEMY_DATABASE_URI'] =  f"postgresql://{db_user}:{dbpwd}@{db_host}/{db_name}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# Flask-Session config
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY'] = db  # pass the SQLAlchemy instance
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_LIFETIME_UNAUTHENTICATED
Session(app)

@app.before_request
def update_session_lifetime():
    if 'authenticated' in session and session['authenticated']:
        app.permanent_session_lifetime = SESSION_LIFETIME_AUTHENTICATED
    else:
        app.permanent_session_lifetime = SESSION_LIFETIME_UNAUTHENTICATED

csp = {
    'default-src': [
        "'self'",
        "https://www.google.com/recaptcha/"
    ],
     'script-src': [
        "'self'",
        "https://www.google.com/recaptcha/",
        "https://www.gstatic.com/recaptcha/"
     ],
    'img-src': ["'self'", "data:", "blob:"],
}
# TODO - check this configuration on the server
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # if behind a proxy, e.g., nginx, apache
Talisman(app, content_security_policy=csp, force_https=False) # for security headers, force https



# LANGUAGE CONFIGURATION
app.config['BABEL_DEFAULT_LOCALE'] = 'cs'
app.config['BABEL_SUPPORTED_LOCALES'] = ['en', 'cs']
# app.config['BABEL_TRANSLATION_DIRECTORIES'] = ['translations']
app.config['LANGUAGES'] = ['en', 'cs']
# app.permanent_session_lifetime=timedelta(days=5)

# MAIL CONFIGURATION
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL') == 'True'
app.config['MAIL_SUPPRESS_SEND'] = os.getenv('MAIL_SUPPRESS_SEND') == 'True'
# the mail password must be provided via environment variable for security reasons 
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
ADMIN_EMAIL_ADDRESSES = json.loads(os.getenv('ADMIN_EMAIL_ADDRESSES', '[]'))

MAX_TOKEN_AGE = int(os.getenv('MAX_TOKEN_AGE', '3600'))  # in seconds, default to 1 hour

mail = Mail(app)

def send_email(subject: str, recipients: list[str], body: str, request_details: dict = {}) -> bool:
    """Send an email using Flask-Mail."""
    try:
        template = 'mail_contact.html'

        msgbody = render_template(
            template, 
            TITLE=subject, 
            MESSAGE=body, 
            REQUEST_DETAILS=request_details, 
            YEAR=pdl.now().year)

        msg = Message(
            subject, 
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients, 
        )
        msg.html = msgbody
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def get_locale():
    lang = session.get('lang', None) 
    if lang is None:
        lang = request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])
        session['lang'] = lang
    return lang

babel = Babel(app, locale_selector=get_locale)

limiter = flask_limiter.Limiter(
    app=app,
    key_func=lambda: session.get('user_id', request.remote_addr),
    default_limits=["500 per day", "500 per hour"]   
)

SECRET_KEY_LENGTH = os.getenv('SECRET_KEY_LENGTH', '32')
HASH_METHOD = os.getenv('HASH_METHOD', 'pbkdf2:sha256')
SALT_LENGTH = os.getenv('SALT_LENGTH', '16')
def generate_rnd_string(length):
    possible_chars=string.ascii_letters+string.digits+string.punctuation
    return ''.join(secrets.choice(possible_chars) for _ in range(int(length))) 
# if in production, use the environment variable, otherwise use the default value
app.secret_key=os.getenv('SECRET_KEY', generate_rnd_string(int(SECRET_KEY_LENGTH)))

def generate_password_hash(password: str) -> str:
    return ws.generate_password_hash(password,method=HASH_METHOD,salt_length=int(SALT_LENGTH))
# ts = {} # temporary storages for the users... ts[user_id] = UserTemporaryStorage()

class UserTemporaryStorage:
    """
    A class for storing temporary data for the user.
    This ensures that the user can only access their own data.
    This class replaces the need for a previous solution which was current_images dictionary.
    
    PREVIOUS SOLUTION: (OUTDATED - OUT OF CLASS)
    # current_images = {'color': [] , 'color_original': [], 'gray': [], 'entropy': {}, 'gray_original': {}, 
    #                   'entropy_original': {}, 'suggested_mask_threshold': {}, 'suggested_mask_blur': {},
    #                   'suggested_mask': [], 'manual_mask_adjustments': []}
    # # 'suggested_mask_blur'- an initial blur set by user for automatic mask suggestion 
    # # 'suggested_mask_threshold'- a threshold set by user for automatic mask suggestion 
    # # 'suggested_mask' - a mask suggested to a user by actual algorithm (based on the U-NET rembg model)
    # # 'manual_mask_adjustments' - changes manually made by the user (a sparse numpy boolean matrix), 
    """
    def __init__(self, **kwargs):
        self.user_id = None
        # values
        # self.info = None
        self.info_datetime = None
        self.info_place_of_experiment = None
        self.info_sample_collection_data = None
        self.info_wrapping_temperature = None
        self.info_exposing_water_temperature = None
        self.info_test_procedure = None
        self.info_comment = None
        self.info_aggregate = None
        self.info_binder = None
        self.expert_guess = None
        self.img_width = None
        self.img_height = None
        # info
        self.experiment_id = None
        # images
        self.color = None
        # masks
        self.aggregate_mask = None # [auto - rembg] all the pixels that are not background
        self.asphalt_mask = None # [auto - sliders] all the pixels that are asphalt and not background
        self.aggregate_mask_manual_corrections = None # [manual] all the pixels that are not background or are background (defined by the user)
        self.asphalt_mask_manual_corrections = None # [manual] all the pixels that are asphalt and not background (defined by the user)        
        self.inference_model = None # name of the model to be used for inference

        # image hashes for similarity checking
        self.phash = None
        self.ahash = None
        self.dhash = None
        self.colorhash = None

        self.from_dict(kwargs)

    # REPLACED BY flask g
    def _self_to_session(self):
        """
        Saves the current state of the object to the session.
        Necessary to ensure that the changes are refrected in every request / worker.
        """
        session['storage'] = zlib.compress(pickle.dumps(self))
    def __setattr__(self, name: str, value):
        super().__setattr__(name, value)
        self._self_to_session()
    
    # def __getattribute__(self, name: str) -> Any:
    #     value = super().__getattribute__(name)
    #     if name in ['color']:  
    #         # get the image from the DB 
    #         value 
    #     return value
            
    def from_dict(self, data_dict: dict) -> None:
        """
        Loads the attributes of the class from a dictionary.
        """
        try:
            self.img_height = data_dict['img_height']
            self.img_width = data_dict['img_width']
        except KeyError:
            pass

        for key, value in data_dict.items():
            if hasattr(self, key):
                if key in ['info_datetime'] and not isinstance(value, str):
                    # parse datetime string
                    if value is None:
                        value = pdl.now()
                    value = pdl.parse(str(value)).to_datetime_string()            
                if isinstance(value, decimal.Decimal):
                    value = float(value)
                if isinstance(value, bytes) or isinstance(value, memoryview):
                    # NP.SAVE APPROACH - Has the metadata like shape and dtype
                    buffer = io.BytesIO(value)
                    value = np.load(buffer, allow_pickle=True)
                setattr(self, key, value)

        # self._self_to_session()  # update the session after loading the data
   

    def to_dict(self, features: Iterable[str] = None, for_save: bool = False) -> dict:
        """
        Converts the attributes of the class to a dictionary.

        Parameters:
        -----------
            features (Iterable[str]): A list of attribute names to include in the dictionary. If None, all attributes are included.
            for_save (bool): If True, converts numpy arrays to bytes for database storage. If False, keeps numpy arrays as is.
        """
        if features is not None:
            dic = {key: value for key, value in self.__dict__.items() if key in features}
        else:
            dic = dict(self.__dict__)  # make a copy instead of using self.__dict__ (to avoid modifying the original)

        if for_save:
            dic['asphalt_ratio'] = storage.get_asphalt_ratio() 
            # Convert numpy arrays to bytes for database storage
            for key, value in dic.items():
                if isinstance(value, np.ndarray):
                    # dic[key] = value.tobytes() 

                    # NP.SAVE APPROACH - KEEPS THE METADATA LIKE SHAPE AND DTYPE
                    buffer = io.BytesIO()
                    np.save(buffer, value)
                    dic[key] = buffer.getvalue()  # This is what you store in SQL (e.g., BLOB column)
                elif isinstance(value, imagehash.ImageHash):
                    dic[key] = str(value)  # store imagehash as string

            dic.pop('experiment_id', None)  # remove experiment_id from the dict when saving to db  

        return dic

    def to_json(self, features: Iterable[str] = None) -> str:
        """
        Converts the attributes of the class to a JSON string.
        """
        json_dict = self.to_dict(features=features)
        
        for key, value in json_dict.items():
            # convert images to base64 strings for JSON serialization
            if isinstance(value, np.ndarray):
                json_dict[key] = to_base64(value)

        return json.dumps(json_dict)

    def get_asphalt_mask(self) -> np.ndarray | None:
        """
        Applies manual corrections to the masks and returns the corrected masks.

        Returns:
        --------
            tuple: A tuple containing the corrected asphalt mask and aggregate mask.
        """
        asphalt_mask = get_masks_corrected(self.asphalt_mask, self.asphalt_mask_manual_corrections) 
        # if self.asphalt_mask_manual_corrections is not None:
        #     if asphalt_mask is None:
        #         asphalt_mask = np.zeros((self.image_height, self.image_width), dtype=bool)
        #     asphalt_mask += self.asphalt_mask_manual_corrections

        return asphalt_mask

    def get_aggregate_mask(self) -> np.ndarray | None:
        """
        Applies manual corrections to the masks and returns the corrected masks.

        Returns:
        --------
            tuple: A tuple containing the corrected asphalt mask and aggregate mask.
        """
        return get_masks_corrected(self.aggregate_mask, self.aggregate_mask_manual_corrections) 

    def get_bg_mask(self) -> np.ndarray | None:
        """
        Returns the background mask based on the aggregate mask and its manual corrections.

        Returns:
        --------
            np.ndarray | None: The background mask or None if the aggregate mask is not set.
        """
        aggregate_mask = self.get_aggregate_mask()
        asphalt_mask = self.get_asphalt_mask()
        bg_mask = np.logical_and(np.logical_not(aggregate_mask), np.logical_not(asphalt_mask))
        return bg_mask
    
    def get_masks_with_manual_corrections(self) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """
        Returns the asphalt, aggregate, and background masks with manual corrections applied.

        Returns:
        --------
            tuple: A tuple containing the corrected asphalt mask, aggregate mask, and background mask.
        """
        asphalt_mask = self.get_asphalt_mask()
        aggregate_mask = self.get_aggregate_mask()
        bg_mask = self.get_bg_mask()
        return asphalt_mask, aggregate_mask, bg_mask

    def get_asphalt_ratio(self) -> float:
        """
        Returns the ratio of asphalt pixels to non-background pixels.

        Returns:
        --------
            float | None: The ratio of asphalt pixels to non-background pixels.
        """

        asphalt_mask = self.get_asphalt_mask()
        aggregate_mask = self.get_aggregate_mask()

        if asphalt_mask is None or aggregate_mask is None:
            return 0.0
        elif np.sum(aggregate_mask * asphalt_mask) > 0:
            raise ValueError("Aggregate mask and asphalt mask have overlapping areas.")

        non_bg_pixels = np.sum(aggregate_mask + asphalt_mask)
        asphalt_pixels = np.sum(asphalt_mask)
        return float(asphalt_pixels / non_bg_pixels) if non_bg_pixels > 0 else 0.0

class TemporaryStoryManager:
    def __init__(self, expire_after_seconds: int = 1200): 
        self._storages: dict[str, UserTemporaryStorage] = {}
        self.expire_after = expire_after_seconds  # in seconds
        self._lock = threading.Lock()
        self._check_frequency_seconds = 300  # check every 5 minutes
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        def cleanup():
            while True:
                time.sleep(self._check_frequency_seconds)
                with self._lock:
                    current_time = time.time()
                    expired_keys = [key for key, storage in self._storages.items()
                                      if current_time - storage.created > self.expire_after]
                    for key in expired_keys:
                        print(f'Cleaning up temporary storage for user_id: {key}')
                        del self._storages[key]
                        # flash(_('Your temporary data has expired due to time limit. If you want to use the service without limitations, consider creating an account.'), 'info') 
                        # redirect(url_for('home')) 
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()

    def create_storage(self, user_id: str) -> None:
        if user_id not in self._storages:
            with self._lock:
                self._storages[user_id] = UserTemporaryStorage(user_id=user_id)
                self._storages[user_id].created = time.time()

    def get(self, user_id: str) -> UserTemporaryStorage:
        with self._lock:
            storage = self._storages[user_id]
            return storage

# tsm = TemporaryStoryManager()  # expire after 20 minutes of inactivity    

serializer = URLSafeTimedSerializer(app.secret_key)

# TODO - implement a thread that will clean up expired tokens from the database periodically

def send_email_confirmation(to_mails: list[str], data: dict, confirmation: Literal ['confirm_email_first', 'confirm_email_change', 'confirm_company_registration_admin', 'confirm_password_reset', 'forgot_password'], intro_text: str, request_details: dict = {}, title: str = 'AIBAL') -> bool:
    """Send an email confirmation link to the user.
    
    Parameters:
        data (dict): A dictionary containing user data, including 'e_mail'.
        confirmation (str): The type of confirmation ('confirm_email_first', 'confirm_email_change', 'confirm_company_registration_admin', 'confirm_password_reset').
        salt (str): The salt to use for token generation.
        info_text (str): Introductory text to include in the email.
        request_details (dict): Details about the request to include in the email. Defaults to an empty dictionary.
    """
    try:
        token = serializer.dumps(data, salt=f'{confirmation}-salt')
        confirm_url = url_for(confirmation, token=token, _external=True)
        
        template = 'mail_confirm.html'

        body = render_template(
            template, 
            TITLE=title, 
            INTRO_TEXT=intro_text, 
            REQUEST_DETAILS=request_details, 
            CONFIRMATION_URL=confirm_url, 
            YEAR=pdl.now().year)
        
        msg = Message(
            title, 
            sender=app.config['MAIL_USERNAME'],
            recipients=to_mails, 
            html=body
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send email confirmation: {e}")
        return False    

def confirm_request(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BadSignature:
            flash(_('The confirmation link is invalid'), 'danger')
            return redirect(url_for('home'))
        except SignatureExpired:
            flash(_('The confirmation link has expired.'), 'danger')
            return redirect(url_for('home'))
    return wrapper

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password_form():
    dynamic_content = _('Forgot your password? Enter your email address.')
    form = forms.EmailForgotPasswordForm()
    match request.method:
        case 'GET':
            return render_template('form.html', form=form, dynamic_content=dynamic_content, recaptcha_site_key=RECAPTCHA_SITE_KEY), 200
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            if form.validate_on_submit():
                e_mail_address = form.e_mail.data
                user = db_api.get_user_id(email=e_mail_address)
                if user is not None:
                    # send email with confirmation link
                    send_email_confirmation(
                        to_mails=[e_mail_address],
                        data={'e_mail': e_mail_address}, 
                        confirmation='forgot_password',
                        intro_text=_('You have requested to reset your password. Please click the button below to reset your password:'),
                        title=_('AIBAL: Password Reset Request')
                    )
                    flash(_('An email with password reset instructions has been sent to your email address.'), 'success')
            return render_template('form.html', form=form, dynamic_content=dynamic_content, recaptcha_site_key=RECAPTCHA_SITE_KEY), 200


@app.route('/forgot_password/<token>', methods=['GET', 'POST'])
@confirm_request
def forgot_password(token: str):
    """Confirm the user's email address using the provided token."""
    match request.method: 
        case 'GET':
            email = serializer.loads(token, salt='forgot_password-salt', max_age=MAX_TOKEN_AGE)['e_mail']  # token valid for 1 hour
            db_api.confirm_user_email(email)
            form = forms.ChangeForgottenPasswordForm()
            flash(_('You can now reset your password!'), 'success')
            return render_template('form.html', form=forms.ChangeForgottenPasswordForm(), token=token, recaptcha_site_key=RECAPTCHA_SITE_KEY), 200
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form = forms.ChangeForgottenPasswordForm()
            if form.validate_on_submit():
                email = serializer.loads(token, salt='forgot_password-salt', max_age=MAX_TOKEN_AGE)['e_mail']  # token valid for 1 hour
                password_hash = generate_password_hash(form.new_password.data)
                user_id = db_api.get_user_id(email=email)
                db_api.update_users_table(values_dict={'pwd': password_hash}, user_id=user_id)
                flash(_('Your password has been set. You can now log in!'), 'success')
            else:
                flash(_('There was an error setting your password. Please try again.'), 'danger')
                return render_template('form.html', form=form, token=token, recaptcha_site_key=RECAPTCHA_SITE_KEY), 200
            return redirect(url_for('login'))


@app.route('/confirm_email/<token>')
@confirm_request
def confirm_email(token: str):
    """Confirm the user's email address using the provided token."""
    email = serializer.loads(token, salt='confirm_email-salt', max_age=MAX_TOKEN_AGE)['e_mail']  # token valid for ... hours
    db_api.confirm_user_email(email)
    flash(_('Your email address has been confirmed. You can now log in!'), 'success')
    return redirect(url_for('login'))

@app.route('/confirm_company_registration_user/<token>', methods=['GET', 'POST'])
@confirm_request
def confirm_company_registration_user(token: str):
    """Confirm the user's email address using the provided token."""
    match request.method: 
        case 'GET':
            email = serializer.loads(token, salt='confirm_company_registration_user-salt', max_age=MAX_TOKEN_AGE)['e_mail']  # token valid for 1 hour
            db_api.confirm_user_email(email)
            print(f'Confirming company registration for user email: {email}')
            form = forms.ChangeForgottenPasswordForm()
            flash(_('Your email address has been confirmed. Please, create your password to complete the registration!'), 'success')
            return render_template('form.html', form=forms.ChangeForgottenPasswordForm(), token=token, recaptcha_site_key=RECAPTCHA_SITE_KEY), 200
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form = forms.ChangeForgottenPasswordForm()
            if form.validate_on_submit():
                email = serializer.loads(token, salt='confirm_company_registration_user-salt', max_age=MAX_TOKEN_AGE)['e_mail']  # token valid for 1 hour
                password_hash = generate_password_hash(form.new_password.data)
                user_id = db_api.get_user_id(email=email)
                db_api.update_users_table(values_dict={'pwd': password_hash}, user_id=user_id)
                flash(_('Your password has been set. You can now log in!'), 'success')
            else:
                flash(_('There was an error setting your password. Please try again.'), 'danger')
                return render_template('form.html', form=form, token=token, recaptcha_site_key=RECAPTCHA_SITE_KEY), 200
            return redirect(url_for('login'))

@app.route('/confirm_company_registration_admin/<token>')
@confirm_request
def confirm_company_registration_admin(token: str):
    print(token)
    """Confirm a registration of a new company using the provided token."""
    datadict = serializer.loads(token, salt='confirm_company_registration_admin-salt', max_age=MAX_TOKEN_AGE)  # token valid for 1 hour
    # TODO: implement logic 
    db_api.confirm_company_registration(datadict['e_mail'])
    
    # create the company administrator account automatically
    user_data = {
        'username': 'Admin_'+ datadict['company_name'],
        'e_mail': datadict['e_mail'],
        'first_name': 'Admin',
        'last_name': datadict['company_name'],
        'company': datadict['company_id'],
        'pwd': generate_password_hash(generate_rnd_string(12)),  
    }
    db_api.save_new_user_db(user_data)
    user_id = db_api.get_user_id(email=user_data['e_mail'])
    db_api.change_admin_privileges(user_id, True)
    
    # send notification to the company admin
    print(datadict)
    send_email_confirmation(
        to_mails=[datadict['e_mail']],
        data={'e_mail': datadict['e_mail']}, 
        confirmation='confirm_company_registration_user',
        intro_text=_('Welcome to AIBAL! Your company registration has been confirmed by the AIBAL administrator.' \
                     'The administrator account for your company has been created automatically (with this email address currently used as a login username - you can change any credentials later).' \
                     'Your administrator was automatically created account has been set up. ' \
                     'Please confirm your email address and create the password to your account by clicking the button below:'),
        title=_('AIBAL: Please confirm your ADMIN email address')
    )

    flash(_('The company has been successfully confirmed. The company administrator will be notified automatically.'), 'success')
    return redirect(url_for('login'))


def verify_recaptcha(response_token: str) -> bool:
    """Verify reCAPTCHA response token with Google's API."""
    secret_key = RECAPTCHA_SECRET_KEY
    verify_url = "https://www.google.com/recaptcha/api/siteverify"
    verify_url = f"{verify_url}?secret={secret_key}&response={response_token}"
    try:
        r = requests.post(verify_url).json()
        print(f"reCAPTCHA verification response: {r}")
        if r['success'] == True and r['score'] >= 0.85:
            return True
        else:
            return False
    except requests.RequestException as e:
        print(f"Error verifying reCAPTCHA: {e}")
        return False

def verify_recaptcha_or_abort(response_token: str) -> bool:
    """Verify reCAPTCHA and abort with 400 if verification fails."""
    if verify_recaptcha(response_token)==True:
        pass
    else:
        abort(400, description=_('reCAPTCHA verification failed. Please try again.'))


def check_session_timeout(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        # uid = session.get('user_id', None)
        # if (uid in ts) or (uid in tsm._storages):
        #     return func(*args, **kwargs)
        if "storage" in session or session.get('authenticated', False) == True:
            return func(*args, **kwargs)
        else:
            message = _('Your session has expired. Please refresh the page and try again.')
            return json.dumps({'status': 'error', 'message': message}), 200
    return wrapper





# def _get_storage() -> UserTemporaryStorage:
#     if 'user_id' not in session: 
#         session['user_id'] = str(uuid.uuid4())

#     if ('authenticated' not in session or not session['authenticated']):
#         # unathenticated user - no session 
#         tsm.create_storage(session['user_id'])
#         return tsm.get(session['user_id'])
#     elif 'authenticated' in session and session['authenticated']:
#         # authenticated user - ensure storage exists
#         return ts.setdefault(session['user_id'], UserTemporaryStorage(user_id=session['user_id']))

# @app.teardown_request
# def save_storage(exception=None):
#     if hasattr(g, "storage"):
#         session["storage"] = zlib.compress(pickle.dumps(g.storage))

# @app.teardown_request
# def save_storage(exception=None):
#     if hasattr(g, "storage"):
#         session["storage"] = zlib.compress(pickle.dumps(storage))

# def _get_storage() -> UserTemporaryStorage:
#     # If already loaded during this request → reuse it
#     if hasattr(g, "storage"):
#         return g.storage

#     # Ensure user_id exists
#     if "user_id" not in session:
#         session["user_id"] = str(uuid.uuid4())

#     storage_data = session.get("storage")

#     if storage_data:
#         storage_obj = pickle.loads(zlib.decompress(storage_data))
#     else:
#         storage_obj = UserTemporaryStorage(user_id=session["user_id"])

#     # Cache in request context
#     g.storage = storage_obj
#     return storage_obj

def _get_storage() -> UserTemporaryStorage:
    # Ensure session has a user_id
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

    # Attempt to load storage from session
    storage_data = session.get('storage')
    if storage_data:
        # decompress + unpickle
        storage_obj: UserTemporaryStorage = pickle.loads(zlib.decompress(storage_data))
    else:
        # Create new storage if none exists
        storage_obj = UserTemporaryStorage(user_id=session['user_id'])
        # Save back into session
        session['storage'] = zlib.compress(pickle.dumps(storage_obj))
    
    return storage_obj

# storage = LocalProxy(lambda: ts.setdefault(session['user_id'], UserTemporaryStorage(user_id=session['user_id'])))
# storage = LocalProxy(lambda: _get_storage())
storage = LocalProxy(lambda: _get_storage())
storage: UserTemporaryStorage = cast(UserTemporaryStorage, storage)
# storage... it behaves like a global variable, but it is actually a proxy to the user-specific storage
# thus storage.name is actually ts[session['user_id']].name
# setdefault ensures that if the user_id is not in ts, it will create a new UserTemporaryStorage for that user_id

def get_masks_corrected(original: np.ndarray = None, corrections: np.ndarray = None) -> np.ndarray:
    """
    Applies manual corrections to the masks and returns the corrected masks.

    Parameters:
    -----------
        original (np.ndarray): The original mask.
        corrections (np.ndarray): The manual corrections to be applied.

    Returns:
    --------
        tuple: A tuple containing the corrected asphalt mask and aggregate mask.
    """
    if original is None and corrections is None:
        raise ValueError("At least one of 'original' or 'corrections' must be provided.")

    if original is None:
        original = np.zeros_like(corrections, dtype=bool)
    elif corrections is None:
        corrections = np.zeros_like(original, dtype=int)
    
    corrected_mask = original.copy()
    if corrections is not None:
        corrected_mask = np.clip(corrected_mask + corrections, 0, 1)
    return corrected_mask.astype(bool)

@app.route('/switch-language/<string:lang_code>', methods=['GET', 'POST'])
def switch_language(lang_code: str):
    print(f'Switching language to: {lang_code}')
    if lang_code not in app.config['LANGUAGES']:
        abort(404)
    # optional: also persist in a cookie for non-session clients
    # response.set_cookie('lang', lang_code, max_age=60*60*24*365)
    session['lang'] = lang_code
    # response = redirect(request.referrer or url_for('index'))
    return json.dumps({'lang': lang_code}), 200
    # return response, 302

def dict_to_json(data_dict: dict, features: Iterable[str] = None) -> str:
        """
        Converts a dictionary to a JSON string.
        """
        if features is not None:
            data_dict = {key: value for key, value in data_dict.items() if key in features}
        
        for key, value in data_dict.items():
            # convert images to base64 strings for JSON serialization
            if isinstance(value, np.ndarray):
                data_dict[key] = to_base64(value)

        return json.dumps(data_dict)        

# @app.before_request        
def check_data_ownership(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f'OWNERSHIP CHECK for user_id: {session.get("user_id", None)} and experiment_id: {kwargs.get("id", None)}')
        owner_user_id = db_api.get_user_id_of_experiment(id=kwargs['id'])
        # allow acces to the data for the company admin as well
        is_company_admin = db_api.get_user_by_id(session['user_id'])['is_company_admin']
        admin_company_id = db_api.get_user_by_id(session['user_id'])['company']

        print(f'Owner user ID: {owner_user_id}')
        print(f'session user ID: {session.get("user_id", None)}')

        can_access = (owner_user_id == session['user_id']) or (is_company_admin and db_api.get_user_by_id(owner_user_id)['company'] == admin_company_id)
        print(owner_user_id == session['user_id'])
        print(can_access)
        print()
        if can_access:
            return func(id=kwargs['id'])
        else:
            flash(_('You do not have permission to access this data.'), 'error')
            return redirect('/'), 302
    return wrapper

def check_authentication(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'authenticated' in session and session['authenticated']:
            return func(*args, **kwargs)
        else:
            flash(_('You must be logged in to access this page.'), 'error')
            return redirect(url_for('login')), 302
    return wrapper

def check_is_company_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if db_api.get_user_by_id(session['user_id'])['is_company_admin']:
            return func(*args, **kwargs)
        else:
            flash(_('You do not have permission to access this page.'), 'error')
            return redirect(url_for('login')), 302
    return wrapper

def ignore_unauthenticated(func):
    """The decorator allows access only to authenticated users, otherwise the function is skipped."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'authenticated' in session and session['authenticated']:
            return func(*args, **kwargs)
        else:
            pass
    return wrapper

@app.route('/')
@check_authentication
def index():
    models = discover_models()
    return render_template('index.html', session=session, models=models), 200

@app.route('/home', methods=['GET','POST'])
def home():
    models = discover_models()
    title = _('Contact us!')
    match request.method:
        case 'GET':
            form = forms.ContactForm()
            return render_template('home.html', session=session, models=models, form=form, dynamic_content=title, recaptcha_site_key = RECAPTCHA_SITE_KEY), 200
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form = forms.ContactForm()
            if form.validate_on_submit():
                # send email to admin
                subject =f'AIBAL: {form.subject.data}'
                # body = f'From: {form.name.data} <{form.email.data}>\n\n{form.message.data}'
                request_details = {'Name': form.name.data,  'e-mail': form.email.data,}
                # TODO: use template
                r = send_email(subject=subject, recipients=ADMIN_EMAIL_ADDRESSES, body=form.message.data, request_details=request_details)
                if r:
                    flash(_('Your message has been sent successfully.'), 'success')
                    return redirect(url_for('home')), 302
                else:
                    flash(_('There was an error sending your message. Please try again.'), 'error')
                    return render_template('home.html', session=session, models=models, form=form, dynamic_content=title, recaptcha_site_key = RECAPTCHA_SITE_KEY), 200
            else:
                flash(_('There was an error sending your message. Please try again.'), 'error')
                return render_template('home.html', session=session, models=models, form=form, dynamic_content=title, recaptcha_site_key = RECAPTCHA_SITE_KEY), 200

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html', session=session), 404

# @app.errorhandler(Exception)
# def handle_exception(error) -> tuple:
#     flash(_('An internal server error has occured.'), 'error')
#     return redirect(url_for('logout')), 500
#     return None, 500


@app.route('/logout')
def logout():
    print('Logging out user.')
    # session.pop('username',None)
    # session.pop('authenticated',None)
    # session.pop('user_id',None)
    # session.pop('user_email',None)
    # session.pop('is_company_admin',None)
    session.clear()  # Clear all session data to ensure complete logout
    return redirect(url_for('login'))

#TODO - consider joining with edit_personal_information (Must be done together with FE editing)
@app.route('/change-email',methods=['GET','POST'])
@check_authentication
def change_email():
    # TODO: !!! CONFIRMATION EMAIL !!!
    title = _('Change email')
    match request.method:
        case 'GET':
            form=forms.ChangeEmailForm()
            return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.ChangeEmailForm()
            if form.validate_on_submit():
                send_email_confirmation(
                    to_mails=[form.e_mail.data],
                    data={'e_mail': form.e_mail.data}, 
                    confirmation='confirm_change_email_user',
                    intro_text=_('You have requested a change of an email address.' 
                                'Please confirm your new email address by clicking the button below:'),
                    title=_('AIBAL: Confirm your new email address')
                )
                db_api.update_users_table(values_dict={'e_mail': form.e_mail.data}, user_id=session['user_id'])
                flash(_('Email changed successfully.'), 'success')
                return redirect('/user')
            else:
                return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)

@app.route('/change-company-email',methods=['GET','POST'])
@check_authentication
def change_company_email():
    # TODO: !!! CONFIRMATION EMAIL !!!
    title = _('Change company email')
    match request.method:
        case 'GET':
            form=forms.ChangeEmailForm()
            return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.ChangeEmailForm()
            if form.validate_on_submit():
                company_id = db_api.get_user_by_id(session['user_id'])['company']
                db_api.update_companies_table(values_dict={'e_mail': form.e_mail.data}, company_id=company_id)
                flash(_('Email changed successfully.'), 'success')
                return redirect('/company')
            else:
                return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)



@app.route('/edit-personal-information',methods=['GET','POST'])
@check_authentication
def edit_personal_information():
    match request.method:
        case 'GET':
            form=forms.EditPersonalInformationForm()
            return render_template('form.html',dynamic_content=_('Change personal information'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.EditPersonalInformationForm()
            if form.validate_on_submit():
                print('Form validated successfully.')
                for field in form:
                    print(field)
                    if field.data:
                        if field.name == 'csrf_token':
                            continue
                        db_api.update_users_table(values_dict={field.name: field.data}, user_id=session['user_id'])
                flash(_('Personal information updated successfully.'), 'success')
                return redirect('/user')
            else:
                return render_template('form.html',dynamic_content=_('Change personal information'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)

@app.route('/edit-company-information',methods=['GET','POST'])
@check_authentication
def edit_company_information():
    match request.method:
        case 'GET':
            form=forms.EditCompanyInformationForm()
            return render_template('form.html',dynamic_content=_('Change personal information'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.EditCompanyInformationForm()
            if form.validate_on_submit():
                print('Form validated successfully.')
                for field in form:
                    print(field)
                    if field.data:
                        if field.name == 'csrf_token':
                            continue
                        company_id = db_api.get_user_by_id(session['user_id'])['company']
                        db_api.update_companies_table(values_dict={field.name: field.data}, company_id=company_id)
                flash(_('Company information updated successfully.'), 'success')
                return redirect('/company')
            else:
                return render_template('form.html',dynamic_content=_('Change personal information'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)

@app.route('/change-password',methods=['GET','POST'])
@check_authentication
def change_password():
    title = _('Change password')
    match request.method:
        case 'GET':
            form=forms.ChangePasswordForm()
            return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.ChangePasswordForm()
            if form.validate_on_submit():                
                # check if the old password is correct
                authenticated = is_password_correct(password=form.old_password.data, user_id=session['user_id'])
                if authenticated:
                    new_password_hash=generate_password_hash(form.new_password.data)
                    db_api.update_users_table(values_dict={'pwd': new_password_hash}, user_id=session['user_id'])
                    flash(_('Password changed successfully.'), 'success')
                    return redirect('/user'), 302
                else:
                    flash(_('The old password is incorrect.'), 'error')
                    return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY), 200
            else:
                return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY), 200

def bool_to_image_array(array: np.ndarray) -> np.ndarray:
    """
    Converts a boolean numpy array to a uint8 image array.

    Parameters:
    -----------
        array (np.ndarray): The boolean numpy array to convert.

    Returns:
    --------
        np.ndarray: A uint8 numpy array representation of the boolean array.
    """
    # transfer boolean full RGBA format
    mask = np.zeros_like(array, dtype=np.uint8)
    mask = np.stack([mask]*4, axis=-1)  # Convert to RGBA by stacking the mask
    mask[array, 3] = 255
    return mask

def is_password_correct(password: str, user_id: int) -> bool:
    """
    Checks if the provided password matches the stored password hash for the user.
    
    Parameters:
    -----------
        password (str): The password to check.
        user_id (int): The ID of the user.
    
    Returns:
    --------
        bool: True if the password is correct, False otherwise.
    """
    true_pwd_hash = db_api.get_password_hash(user_id=user_id)
    return ws.check_password_hash(pwhash=true_pwd_hash,password=password)

@app.route('/change-user-blockade',methods=['POST'])
@check_authentication
def change_user_blockade():
    # admin code verification  - TODO: wrap in a decorator
    print('Changing user blockade...')
    if db_api.get_user_by_id(user_id=session['user_id'])['is_company_admin'] is False:
        abort(403, description=_('You do not have permission to perform this action.'))
    # user to be altered 
    username = request.form.get('username',None)
    user_to_alter_id = db_api.get_user_id(username=username)
    if user_to_alter_id is None:
        abort(400, description=_('User with the provided username does not exist'))

    # get the future status
    will_be_blocked = request.form.get('will_be_blocked','false').lower() == 'true'
    db_api.change_user_blockade(user_id=user_to_alter_id, is_blocked=will_be_blocked)
    return json.dumps({'status': 'success'}), 200

@app.route('/change-admin-privileges',methods=['POST'])
@check_authentication
def change_admin_privileges():
    # admin code verification - TODO: wrap in a decorator
    print('Changing admin privileges...')
    if db_api.get_user_by_id(user_id=session['user_id'])['is_company_admin'] is False:
        abort(403, description=_('You do not have permission to perform this action.'))
    # user to be granted  
    username = request.form.get('username',None)
    user_to_alter_id = db_api.get_user_id(username=username)
    if user_to_alter_id is None:
        abort(400, description=_('User with the provided username does not exist'))

    # get the future status
    will_be_admin = request.form.get('will_be_admin','false').lower() == 'true'
    db_api.change_admin_privileges(user_id=user_to_alter_id, is_admin=will_be_admin)
    return json.dumps({'status': 'success'}), 200


@app.route('/login',methods=['GET','POST'])
def login():
    if 'authenticated' in session and session['authenticated']:
        logout()
    match request.method:
        case 'GET':
            form=forms.LoginForm()
            return render_template('form.html',dynamic_content=_('Login'),form=form, session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.LoginForm()
            if form.validate_on_submit():
                user_id = db_api.get_user_id(username=form.usernameXe_mail.data, email=form.usernameXe_mail.data)
                
                # check if the email is confirmed
                if not db_api.is_user_email_confirmed(user_id=user_id):
                    flash(_('Please confirm your email address before logging in.'), 'error')
                    return redirect(url_for('login')), 302
                # check if the user is blocked
                if db_api.is_user_blocked(user_id=user_id):
                    flash(_('Your account has been blocked. In case this should not be the case, please contact your company admin.'), 'error')
                    return redirect(url_for('login')), 302
                
                authenticated = is_password_correct(password=form.password.data, user_id=user_id)
                if authenticated:
                    session['authenticated'] = True
                    session['user_id'] = user_id
                    session['user_email'] = form.usernameXe_mail.data
                    session['is_admin'] = False
                    if db_api.get_user_by_id(user_id=user_id)['is_company_admin']:
                        session['is_admin'] = True
                    return redirect('/'), 302   
                else:
                    flash(_('Invalid username/email or password.'), 'error')
                    return render_template('form.html', dynamic_content=_('Login'), form=form, session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
            else:
                # form validation failed - user is notified by flash messages in the form
                return render_template('form.html', dynamic_content=_('Login'), form=form, session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)

def sort_records(records: list, sort_order: Literal['asc', 'desc'], sort_by: str, page_limit: int) -> list:
    if sort_order == 'asc':
        records.sort(key=lambda x: x[sort_by])
    elif sort_order == 'desc':
        records.sort(key=lambda x: x[sort_by], reverse=True)
    return records[:page_limit]

@app.route('/queue',methods=['GET','POST'])
@check_authentication
def queue():
    sort_order=request.args.get('sort_order','asc')
    page_limit=int(request.args.get('page_limit') or 10)
    page=int(request.args.get('page',1))
    start_sub_id=request.args.get('start_id',None)
    sort_by=request.args.get('sort_by','time_stamp,id')
    
    records=[('id','time_stamp','current_state')]
    sort_by = sort_by.split(',')  
    sort_by = [x for x in sort_by if x in records[0]]
    
    sort_columns=[ records[0].index(x) for x in sort_by]

    columnames=[_('id'),_('date'),_('state'),_('actions')]
    actions=[_('Edit'),_('Cancel')]
    records.append(execute_query("SELECT experiment_id, time_stamp, current_state FROM experiments where user_id=%s AND current_state!='finished' ",(session['user_id'],)))
    data = records[1]

    # Data sorting and slicing
    current_state_order={'finished':0,'current_experiment': 1, 'started':2,'prepared':3,'processing':4,'pending':5}
    reversed_current_state_order={v:k for k,v in current_state_order.items()}
    data = [(x[0], x[1].strftime('%Y-%m-%d  %H:%M:%S'), x[2]) for x in data]
    data=list(map(lambda x: (x[0],x[1],current_state_order[x[2]]),data))
    data.sort(key=lambda x: [x[i] for i in sort_columns], reverse=sort_order=='desc')
    # now we have to remap the data back to strings
    data=list(map(lambda x: (x[0],x[1],reversed_current_state_order[x[2]]),data))
        
    pages=len(data)//page_limit+1
    if page>pages:
        page=pages
    if start_sub_id is None:
        start_sub_id=0+page_limit*(page-1)
    else:
        start_sub_id=int(start_sub_id)
    
    max_sub_id = min(len(data), start_sub_id+page_limit)
    data=data[start_sub_id:max_sub_id]
    records[1] = data

    # translate_column_names
    columnames = [ _(col) for col in columnames ]
    return render_template('queue.html',records=records,session=session,dynamic_content=_('Experiment Queue'),columnames=columnames, actions = actions)

def get_ordenary_user_experiments(request) -> list[tuple]:
    sort_order=request.args.get('sort_order','desc')
    page_limit=int(request.args.get('page_limit') or 10)
    start_sub_id=request.args.get('start_id',None)
    page=int(request.args.get('page',1))
    sort_by=request.args.get('sort_by','time_stamp,id,expert_guess,asphalt_ratio')
    
    records=[('id','time_stamp','expert_guess', 'asphalt_ratio')]
    sort_by = sort_by.split(',')  
    sort_by = [x for x in sort_by if x in records[0]]
    sort_columns=[ records[0].index(x) for x in sort_by]
    # records.append(execute_query("SELECT experiment_id, time_stamp, expert_guess, asphalt_ratio, current_state FROM experiments where user_id=%s AND current_state='finished' AND fake_deleted=false",(session['user_id'],)))
    records.append(
        execute_query("SELECT experiment_id, time_stamp, expert_guess, asphalt_ratio, current_state FROM experiments where user_id=%s AND fake_deleted=false",(session['user_id'],)))
    
    # data sorting and slicing
    data = records[1]   
    # shorten the time_stamp to  YYYY-MM-DD HH:MM:SS
    data = [(x[0], x[1].strftime('%Y-%m-%d  %H:%M:%S'), x[2], x[3]) for x in data]
    # Replace None values with -1
    data = [(x[0],x[1],x[2] if x[2] is not None else 0, x[3] if x[3] is not None else -1) for x in data]
    data.sort(key=lambda x: [x[i] for i in sort_columns], reverse=sort_order=='desc')
    # replace -1 with None
    data = [(x[0],x[1],x[2] if x[2] != -1 else None, x[3] if x[3] != -1 else None) for x in data]
        
    pages=len(data)//page_limit+1
    if page>pages:
        page=pages
    if start_sub_id is None:
        start_sub_id=0+page_limit*(page-1)
    else:
        start_sub_id=int(start_sub_id)
    
    max_sub_id = min(len(data), start_sub_id+page_limit)
    data=data[start_sub_id:max_sub_id]
    # convert the expert guess and asphalt_ratio to string with 2 decimal places
    data = [(x[0], x[1], f"{x[2]*100:.2f}" if x[2] is not None else _('None'), f"{x[3]*100:.2f}" if x[3] is not None else _('None')) for x in data]
    records[1] = data
    return render_template('experiments.html',records=records,session=session,dynamic_content=_('Sample Records'))
    
def get_admin_user_experiments(request) -> list[tuple]:
    sort_order=request.args.get('sort_order','desc')
    page_limit=int(request.args.get('page_limit') or 10)
    start_sub_id=request.args.get('start_id',None)
    page=int(request.args.get('page',1))
    sort_by=request.args.get('sort_by','time_stamp,id,expert_guess,asphalt_ratio')
    
    records=[('id','time_stamp','name','contact','expert_guess', 'asphalt_ratio')]
    sort_by = sort_by.split(',')  
    sort_by = [x for x in sort_by if x in records[0]]
    sort_columns=[records[0].index(x) for x in sort_by]
    
    # 
    company_id = db_api.get_user_by_id(session['user_id'])['company']
    records.append(db_api.get_all_company_experiments(company_id))
    # Join the firs and last name
    records[1] = [(
        x['experiment_id'], 
        x['time_stamp'].strftime('%Y-%m-%d  %H:%M:%S'), 
        f"{x['first_name']} {x['last_name']}",
        x['e_mail'], 
        x['expert_guess'], 
        x['asphalt_ratio'], 
    ) for x in records[1]]

    # data sorting and slicing
    data = records[1]
    # Replace None values with -1
    data = [(x[0],x[1],x[2],x[3],x[4] if x[4] is not None else 0, x[5] if x[5] is not None else -1) for x in data]
    data.sort(key=lambda x: [x[i] for i in sort_columns], reverse=sort_order=='desc')
    # replace -1 with None
    data = [(x[0],x[1],x[2],x[3],x[4] if x[4] != -1 else None, x[5] if x[5] != -1 else None) for x in data]
    records[1] = data
    pages=len(data)//page_limit+1
    if page>pages:
        page=pages  
    if start_sub_id is None:
        start_sub_id=0+page_limit*(page-1)
    else:
        start_sub_id=int(start_sub_id)
    max_sub_id = min(len(data), start_sub_id+page_limit)
    data=data[start_sub_id:max_sub_id]
    # convert the expert guess and asphalt_ratio to string with 2 decimal places
    data = [(x[0], x[1], x[2], x[3], f"{x[4]*100:.2f}" if x[4] is not None else _('None'), f"{x[5]*100:.2f}" if x[5] is not None else _('None')) for x in data]
    records[1] = data
    return render_template('experiments_admin.html',records=records,session=session,dynamic_content=_('Sample Records - Admin View'))

@app.route('/experiments',methods=['GET','POST'])
@check_authentication
def experiments():
    if db_api.get_user_by_id(session['user_id'])['is_company_admin']:
        return get_admin_user_experiments(request)
    return get_ordenary_user_experiments(request)

@app.route('/employees',methods=['GET','POST'])
@check_authentication
@check_is_company_admin
def employees():
    sort_order=request.args.get('sort_order','desc')
    page_limit=int(request.args.get('page_limit') or 10)
    start_sub_id=request.args.get('start_id',None)
    page=int(request.args.get('page',1))
    sort_by=request.args.get('sort_by','name,contact,is_company_admin')
    
    records=[('name','contact','is_company_admin')]
    sort_by = sort_by.split(',')  
    sort_by = [x for x in sort_by if x in records[0]]
    sort_columns=[records[0].index(x) for x in sort_by]
    
    # 
    company_id = db_api.get_user_by_id(session['user_id'])['company']
    records.append(db_api.get_all_company_employees(company_id))
    # Join the firs and last name
    records[1] = [(
        f"{x['first_name']} {x['last_name']}",
        x['username'], 
        x['e_mail'], 
        x['is_company_admin'], 
        x['is_blocked'], 
    ) for x in records[1]]

    # data sorting and slicing
    data = records[1]
    data.sort(key=lambda x: [x[i] for i in sort_columns], reverse=sort_order=='desc')
    # replace -1 with None
    data = [(*x,) for x in data]
    records[1] = data
    pages=len(data)//page_limit+1
    if page>pages:
        page=pages  
    if start_sub_id is None:
        start_sub_id=0+page_limit*(page-1)
    else:
        start_sub_id=int(start_sub_id)
    max_sub_id = min(len(data), start_sub_id+page_limit)
    data=data[start_sub_id:max_sub_id]
    records[1] = data
    return render_template('employees.html',records=records,session=session,dynamic_content=_('Employee Records - Admin View'))
    
@app.route('/user',methods=['GET'])
@check_authentication
def user():
    """"
    Renders the user information page.
    Returns:
        Response: The rendered user information page.
    """
    user_data_dict = db_api.get_user_info_by_id(user_id=session['user_id'])
    return render_template('user.html',session=session,dynamic_content=user_data_dict)

@app.route('/company',methods=['GET'])
@check_authentication
@check_is_company_admin
def company():
    """"
    Renders the user information page.
    Returns:
        Response: The rendered user information page.
    """
    company_id = db_api.get_user_by_id(session['user_id'])['company']
    company_data_dict = db_api.get_company_info_by_id(company_id=company_id)
    print(company_data_dict)
    return render_template('company.html',session=session,dynamic_content=company_data_dict)
            
@app.route('/register',methods=['GET','POST'])
def register():
    # logout()
    title = _("Register new company")
    info = _("You can use the form above to register a user for your existing company. If you wish to register a new company instead, please click the button below and contact us via email.")
    btnstr = _("Contact us!")
    optional_content = f"""
        <div class="colorbar">
            <h1>{title}</h1>
        </div>
        <div class="home-text">
        <p class="fancy-paragraph">
            {info}
        </p>
        <a href="\home#contact_form">
            <button id='ContactUsBtn' class="custom-file-label">{btnstr}</button>
        </a>
    </div>
    """
    if session.get('authenticated', False):
        optional_content = f""

    match request.method:
        case 'GET':
            form=forms.RegistrationFormUser()

            return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY, optional_content_below=optional_content)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.RegistrationFormUser()
            if form.validate_on_submit():
                intro_text = _('Thank you for signing up! Please confirm your email address by clicking the link below:')
                send_email_confirmation(
                    to_mails=[form.e_mail.data],
                    data={'e_mail': form.e_mail.data},
                    confirmation='confirm_email',
                    intro_text=intro_text,
                    title=_('AIBAL: Please confirm your email address')
                )
                print('Form validated successfully.')
                form.password.data=generate_password_hash(form.password.data)
                company_id=db_api.get_company_id_by_key(form.company_key.data)
                user_dict = {
                    'username': form.username.data,
                    'e_mail': form.e_mail.data,
                    'first_name': form.first_name.data,
                    'last_name': form.last_name.data,
                    'company': company_id,
                    'pwd': form.password.data
                }
                result = db_api.save_new_user_db(values=user_dict)
                if result is None:
                    flash(message=_('Registration successful. Please confirm your email via the link sent to your email address.'),category='success')
                    return redirect(url_for('login')), 302
                else:
                    flash(message=_('Database error:') + f'{result}', category='error')
                    return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY, optional_content_below=optional_content), 500
            else:
                flash(message=_('Form validation failed. Please check your input.'),category='error')
                return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY, optional_content_below=optional_content)

@app.route('/regenerate-company-key',methods=['GET'])
@check_authentication
@check_is_company_admin
def regenerate_company_key():
    # TODO - add confirmation email!
    company_id = db_api.get_user_by_id(session['user_id'])['company']
    db_api.update_company_key(company_id=company_id)
    flash(message=_('Company key regenerated successfully.'), category='success')
    return redirect('/company'), 302

@app.route('/view-company-key',methods=['GET'])
@check_authentication
@check_is_company_admin
def view_company_key():
    company_id = db_api.get_user_by_id(session['user_id'])['company']
    company_key = db_api.get_company_key(company_id=company_id)

    return render_template('company_key.html',session=session,dynamic_content=_('Company Key'), company_key=company_key)

def generate_company_key() -> str:
    """Generates a unique company key."""
    while True:
        key = uuid.uuid4().hex[:8]  # generate an 8-character hex string
        if not db_api.check_company_key_exists(key):
            break        
    return key  
        

def pick_users(session_user_id) -> list[tuple]:
    company_id = db_api.get_user_by_id(session_user_id)['company']
    users = db_api.get_users_by_company(company_id)
    if not users:
        users = [(None, 'None')]
    else:
        users = [(None, 'None')] + [(user['id'], f"{user['first_name']} {user['last_name']} ‹{user['e_mail']}›") for user in users]
    return users

def are_experiments_accessible_by_user(user_id: int, experiment_ids: list) -> bool:
    """Returns a list of experiment IDs accessible by the given user."""
    user = db_api.get_user_by_id(user_id)
    # all user experiment ids
    for experiment_id in experiment_ids:
        if user['is_company_admin']:
            company_id = user['company']
            record = db_api.get_experiment_by_id_and_company(experiment_id=experiment_id, company_id=company_id)
            if not record:
                return False
        else:
            record = db_api.get_experiment_by_id_and_user(experiment_id=experiment_id, user_id=user_id)
            print(experiment_id)
            print(record)
            if not record:
                print('returning false for record:', record)
                return False
    print('All experiments are accessible by the user.')
    return True

def validate_report_experiment_ids(experiment_ids: list) -> bool:
    """Validates the experiment IDs for report generation."""
    try:
        experiment_ids = [int(eid) for eid in experiment_ids.split(',')]
    except ValueError:
        abort(400, description=_('Invalid experiment IDs provided.'))
    return experiment_ids

@app.route('/export-report/<string:ids>',methods=['GET','POST'])
@check_authentication
def export_report(ids):
    match request.method:
        case 'GET':
            form=forms.ExportReportForm()
            form.controlling_employee.choices = pick_users( session['user_id'])
            return render_template('form.html',dynamic_content=_('Export report'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            form=forms.ExportReportForm()
            form.controlling_employee.choices = pick_users( session['user_id'])  
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            if form.validate_on_submit():
                experiment_ids = validate_report_experiment_ids(ids)
                if not experiment_ids:
                    flash(message=_('No experiments selected for report export.'),category='error')
                    return render_template('form.html',dynamic_content=_('Export report'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
                if not are_experiments_accessible_by_user(session['user_id'], experiment_ids): 
                    flash(message=_('You do not have permission to access the selected experiments.'),category='error')
                    return render_template('form.html',dynamic_content=_('Export report'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
                print('Form validated successfully.')
                # generate report
                controlling_user_id = form.controlling_employee.data  # may be None
                if controlling_user_id is None or controlling_user_id == 'None':
                    controlling_user_id = session.get('user_id')
                ordering_party = {
                    'name': form.ordering_party_name.data,
                    'address': form.ordering_party_address.data,
                    'contact': form.ordering_party_e_mail.data,
                }

                print(ordering_party)

                print()
                print('experiment_ids')
                print(experiment_ids)
                print('controlling_user_id:', controlling_user_id)
                print()
                report_id = uuid.uuid4().hex[:8]
                report_bytes = exporter_registry["CSN_73_6161"](
                    experiment_ids=experiment_ids,
                    report_id = report_id,
                    user_id=session.get('user_id'),
                    controlling_user_id=controlling_user_id,
                    ordering_party = ordering_party,
                )

                response = send_file(
                    io.BytesIO(report_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'AIBAL_Report_{report_id}.pdf',
                )
                return response
            else:
                flash(message=_('Form validation failed. Please check your input.'),category='error')
                return render_template('form.html',dynamic_content=_('Export report'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)


@app.route('/register-company',methods=['GET','POST'])
def register_company():
    logout()
    match request.method:
        case 'GET':
            form=forms.RegistrationFormCompany()
            return render_template('form.html',dynamic_content=_('Register new company'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.RegistrationFormCompany()
            if form.validate_on_submit():
                print('Form validated successfully.')
                values = {
                    'company_name': form.company_name.data,
                    'company_address': form.company_address.data,
                    'e_mail': form.e_mail.data,
                    'company_key': generate_company_key(),
                }
                result = db_api.save_new_company_db(values=values)
                # send email to admin for confirmation
                intro_text = _('A new company registration with the following details has been requested:')
                request_details = {
                    _('Company Name'): form.company_name.data,
                    _('Company Address'): form.company_address.data,
                    _('Contact Email'): form.e_mail.data,
                }
                send_email_confirmation(
                    to_mails=ADMIN_EMAIL_ADDRESSES,
                    data={'e_mail': form.e_mail.data, 'company_name': form.company_name.data, 'company_id': db_api.get_company_id_by_key(values['company_key'])},
                    confirmation='confirm_company_registration_admin',
                    intro_text=intro_text,
                    request_details=request_details,
                    title=_('AIBAL: New company registration request')
                )
                if result is None:
                    flash(message=_('Registration successful. Please confirm this request in your ADMIN mail account.'),category='success')
                    return redirect(url_for('login')), 302
                else:
                    flash(message=_('Database error:') + f'{result}', category='error')
                    return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY), 500
            else:
                flash(message=_('Form validation failed. Please check your input.'),category='error')
                return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)


# TODO: CONSIDER REMOVAL - BAD DESIGN - SPLIT THE FUNCTIONALITY
# TODO: GET - for fetching the grayscale image
# TODO: The image will be grayscaled automatically after uploading/loading the color image
# @app.route('/grayscale-data', methods=['POST'])
# def get_grayscale_data():
#     file = request.files['file']
#     if file:
#         image = Image.open(file.stream)        
#         gray_image = image.convert('L')
#         np_gray = np.array(gray_image)
#         storage.gray_original = np_gray
#         storage.gray = np_gray

#         # ts[session['user_id']].gray = np_gray
#         # ts[session['user_id']].gray_original = np_gray
        
#         # cv2.imwrite('temp/gray_temp.jpg', np_gray)
#         print('Image loaded.')

#         img_byte_arr = io.BytesIO()
#         gray_image.save(img_byte_arr, format='PNG')
#         img_byte_arr.seek(0)  # Rewind the buffer to the beginning

#         img_byte_arr = io.BytesIO()
#         Image.fromarray(np_gray).save(img_byte_arr, format='PNG')
#         img_byte_arr = img_byte_arr.getvalue()
#         return img_byte_arr, 200, {'Content-Type': 'image/png'}


@app.route('/get-current-experiment', methods=['GET'])
@check_authentication
def get_current_experiment():
    """
    Returns the current experiment data for the authenticated user.

    Returns:
    --------
        Response: A JSON response containing the current experiment data or an error message.
    """
    if storage.experiment_id is None:
        return json.dumps({'status': 'error', 'message': 'No active experiment found'}), 404, {'Content-Type': 'application/json'}
    else:
        dict_response = {'status': 'success'}
        dict_response.update(storage.to_dict())
        json_response = dict_to_json(dict_response)
        return json_response, 200, {'Content-Type': 'application/json'}

@app.route('/get-grayscale-image', methods=['GET'])
def get_grayscale_image():
    """
    Returns the grayscale version of the currently loaded color image. If no color image is loaded, returns an error message.

    Returns:
    --------
        Response: A JSON response containing the base64-encoded grayscale image or an error message.
    """
    if storage.color is None:
        return json.dumps({'status': 'error', 'message': 'No image found in the experiment'}), 404, {'Content-Type': 'application/json'}
    else:
        dict_response = {'status': 'success'}
        dict_response.update({
            "gray": to_base64(grayscale_image(storage.color)),
        })
        return json.dumps(dict_response), 200, {'Content-Type': 'application/json'}

def grayscale_image(image: np.ndarray) -> np.ndarray:
    """
    Converts a color image to grayscale.
    Parameters:
    -----------
        image (np.ndarray): The input color image in RGB format. Shape should be (H, W, 3/4).
        
    Returns:
    --------
        np.ndarray: The grayscale image. Shape will be (H, W).
    """
    if len(image.shape) == 3 and image.shape[2] >= 3:
        # Convert RGB to Grayscale, dropping alpha channel if present
        gray_image = cv2.cvtColor(image[:, :, :3], cv2.COLOR_RGB2GRAY)
    elif len(image.shape) == 2:
        gray_image = image
    else:
        raise ValueError("Invalid image shape for grayscaling.")
    return gray_image

# TODO: CONSIDER REMOVAL - SLOWER THAN CV2
# def grayscale_image(image: np.ndarray) -> np.ndarray:
#     gray_image = Image.fromarray(image).convert('L')
#     np_gray = np.array(gray_image)
#     return np_gray

# TODO: CONSIDER REMOVAL - LIKELY UNUSED
# @app.route('/rembg',methods=['GET'])
# @check_authentication
# def rembg():
#     return render_template('rembg.html')

@app.route('/update_value/<string:value_name>',methods=['POST'])
@check_authentication
@limiter.exempt 
def update_specific_value(value_name):
    # ts[session['user_id']].values.__dict__[value_name] = value
    # setattr(ts[session['user_id']], value_name, value)    
    if storage.experiment_id is None:
        return json.dumps({'status': 'error', 'message': 'No active experiment found'}), 404, {'Content-Type': 'application/json'}
    value = request.form.get(value_name)
    if value is None or value.lower() == 'null':
        value = None
    storage.from_dict({value_name: value})
    response = save_specific_value(value_name)
    return response    
   
@app.route('/save_value/<string:value_name>',methods=['POST','GET'])
@ignore_unauthenticated
def save_specific_value(value_name):
    try:
        value_name = value_name.lower()
        # value = ts[session['user_id']].values.__dict__[value_name]
        value = getattr(storage, value_name)
        db_api.update_experiment_in_db(values_dict={value_name: value}, experiment_id=storage.experiment_id)
        return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return json.dumps({'status': 'error'}), 200, {'Content-Type': 'application/json'}

# TODO: CONSIDER REMOVAL - REPLACED BY storage.get_asphalt_ratio()
@deprecated("Use storage.get_asphalt_ratio() instead.")
def evaluate_asphalt():
    non_bg_pixels = np.sum(return_foreground_mask())
    asphalt_pixels = np.sum(storage.asphalt_mask + storage.asphalt_mask_manual_corrections) 
    ic(return_asphalt_mask())
    print('Asphalt pixels:', asphalt_pixels)
    print('Non bg pixels:', non_bg_pixels)
    return asphalt_pixels / non_bg_pixels


@app.route('/evaluate-asphalt',methods=['GET', 'POST'])
# @check_authentication
@check_session_timeout
def evaluate_asphalt_caller():
    # evaluation = evaluate_asphalt()
    # inference
    # get the resul

    evaluation = storage.get_asphalt_ratio()
    save_experiment(state='finished')
    print('Asphalt ratio evaluated:', evaluation)
    return json.dumps({'status': 'success', 'evaluation': evaluation}), 200, {'Content-Type': 'application/json'}

# TODO: CORRECT THE METHOD - should be DELETE
# @app.route('/delete-experiment/<int:id>',methods=['DLELERTE'])
@app.route('/delete-experiment/<int:id>',methods=['GET', 'POST'])
@check_authentication
@check_data_ownership
def delete_experiment(id):
    experiment_state = execute_query('SELECT current_state FROM experiments WHERE experiment_id=%s', (id,))[0][0]
    try:
        if experiment_state == 'finished':
            query = 'UPDATE experiments SET fake_deleted=true WHERE experiment_id=%s'
            execute_query(query, (id,))
        else:
            query = 'DELETE FROM experiments WHERE experiment_id=%s'
            execute_query(query, (id,))
        status = 'success'
    except:
        status = 'error'
    return json.dumps({'status': status}), 200, {'Content-Type': 'application/json'}

@app.route('/deactivate-current-experiment',methods=['GET', 'POST'])
@check_authentication
def deactivate_current_experiment():
    id = db_api.return_active_experiment_id(user_id=session['user_id'])
    storage = None
    return deactivate_experiment(id)

@app.route('/deactivate-experiment/<int:id>',methods=['GET', 'POST'])
@check_authentication
@check_data_ownership
def deactivate_experiment_caller(id):
    return deactivate_experiment(id)

def deactivate_experiment(id):
    print('Deactivating experiment.', id)
    if id is None:
        flash(_('No active experiment found.'), 'error')
        return redirect('/'), 302
    
    # query = 'UPDATE experiments SET active=%s WHERE experiment_id=%s'
    # values = (False, id)
    # execute_query(query, values)

    # deactivate the current experiment in the database
    db_api.update_experiment_active_status(user_id=session['user_id'], active=False)
    storage.experiment_id = None
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

@app.route('/activate-experiment/<int:id>',methods=['GET', 'POST']) 
@check_authentication
@check_data_ownership
def activate_experiment_caller(id):
    return activate_experiment(id)

def activate_experiment(id):
    if id is None:
        id = storage.experiment_id
        if id is None:
            flash(_('No active experiment found.'), 'error')
            return redirect('/queue')
    # check if the experiment is already active if it is, deactivate it
    query = 'SELECT experiment_id FROM experiments WHERE user_id=%s AND active=True'
    active_id = execute_query(query, (session['user_id'],))
    print(active_id)
    if active_id:
        for i in active_id:
            print(i[0])
            r=deactivate_experiment(i[0])

    # activate the experiment
    db_api.update_experiment_active_status(user_id=session['user_id'], active=True, experiment_id=id)
    # query = 'UPDATE experiments SET active=%s WHERE experiment_id=%s'
    # values = (True, id)
    # execute_query(query, values)
    # ts [session['user_id']].experiment_id = id    
    storage.experiment_id = id    
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

# TODO: consider removal - of 'POST' method - unused
# @app.route('/load-experiment/<int:id>',methods=['GET', 'POST'])
@app.route('/load-experiment/<int:id>',methods=['GET'])
@check_authentication
def load_experiment(id):
    """
    Loads the experiment data from the database (expects a dictionary) into the user-specific temporary storage.
    
    Parameters:
    -----------
        id (int): The ID of the experiment to load. If None, loads the currently active experiment.
    
    Returns:
    --------    
        Response: A JSON response indicating success or failure of the operation and data the public experiment data.
    """
    if id is None:
        id = storage.experiment_id
        if id is None:
            flash(_('No active experiment found.'), 'error')
            return redirect('/queue'), 302          
    response = db_api.get_experiment_by_id(id)
    storage.from_dict(response)
    
    
    dict_response = {
        'status': 'success',
        'gray': grayscale_image(storage.color)
     }
    dict_response.update(storage.to_dict())
    return dict_to_json(dict_response), 200, {'Content-Type': 'application/json'}

    #     print('Experiment loaded.')
    #     redirect('/')
    # return json.dumps(json_response), 200, {'Content-Type': 'application/json'}      

# export the images folder
@app.route('/images/<path:filename>')
def download_file(filename):
    return send_from_directory('images', filename, as_attachment=True)

# manual corrections
# @app.route('/manual-corrections',methods=['GET'])
# @check_authentication
# def manual_corrections():
#     return render_template('manual_corrections.html')

@app.route('/is-experiment-active',methods=['GET'])
def is_active():
    print('Checking if experiment is active.')
    storage.experiment_id = db_api.return_active_experiment_id(user_id=session['user_id'])
    print(storage.experiment_id)
    if storage.experiment_id is not None:
        return json.dumps({'status': 'success', 'active': True, 'experimentId': storage.experiment_id}), 200, {'Content-Type': 'application/json'}
    else:
        return json.dumps({'status': 'success', 'active': False, 'experimentId': None}), 200, {'Content-Type': 'application/json'}

@app.route('/save',methods=['POST'])
@ignore_unauthenticated
# @check_authentication
def save_experiment(**kwargs):
        """
        Saves the current experiment data to the database. If no experiment is active, a new one is created.
        """
        if 'state' in kwargs.keys():
            state = kwargs['state']
        else:
            state = request.args.get('state') or request.form.get('state') or 'started'
            # state = 'started'    

        print('Saving record.')
        print('state', state)
    # try:        
        print()
        print()
        print('Current experiment ID:', storage.experiment_id)
        print('Storeage user ID:', storage.user_id)
        print('Current user ID:', session['user_id'])
        print()
        print()
        if storage.experiment_id is None:
            print('Inserting new record.')
            ts_dict = storage.to_dict(for_save=True)
            ts_dict['current_state'] = state 
            ts_dict['user_id'] = session['user_id']
            # ts_dict.pop('experiment_id', None)  # ensure that the experiment_id is not in the dict
            storage.experiment_id = db_api.insert_experiment_to_db(values_dict=ts_dict)
            activate_experiment(storage.experiment_id)
            print('New experiment ID:', storage.experiment_id)
            # storage.from_dict(ts_dict)  # to ensure consistency
        else:
            print('Updating record.')
            ts_dict = storage.to_dict(for_save=True)
            ts_dict['current_state'] = state
            ts_dict['user_id'] = session['user_id']
            db_api.update_experiment_in_db(values_dict=ts_dict, experiment_id=storage.experiment_id)
        if state.lower() == 'finished':
            # delete temporary storage and create a new one
            print('Experiment finished.')
            # ts.pop(session['user_id'])
            session.pop('storage', None)  # remove storage from session
            # storage = UserTemporaryStorage() # TODO: check if this is needed >>> should be created dynamically when needed by lambda function in storage definition
        return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}
    # except Exception as e:
    #     return json.dumps({'status': 'error', 'message': str(e)}), 500, {'Content-Type': 'application/json'}


# @app.route('/backup-storage',methods=['POST', 'GET'])
# @check_authentication
# def backup_temporal_storage():
#     # This function bacups the temporary storage of the user and creates a new one
#     # it should be called when the user wants to upload new images without harming the current experiment
    
#     # ts[str(session['user_id'])+"&backup"] = ts[session['user_id']]
#     # ts[session['user_id']] = UserTemporaryStorage()
    
#     storage_backup = UserTemporaryStorage().from_dict(storage.to_dict())  # create a copy of the current storage

#     return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

# @app.route('/restore-storage',methods=['POST', 'GET'])
# @check_authentication
# def restore_temporal_storage():
#     # This function restores the temporary storage of the user from the backup
#     # it should be called when the user wants to restore the previous experiment
#     ts[session['user_id']] = ts[str(session['user_id'])+"&backup"]
#     ts.pop(str(session['user_id'])+"&backup")
#     return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}


def downscale_image(image: np.ndarray, scale_factor: float = None) -> np.ndarray:
    """
    Downscale the input image by a given scale factor.
    
    Parameters:
    -----------
        image (np.ndarray): The input image as a numpy array of shape (H, W, C) or (H, W).
        scale_factor (float): The factor by which to downscale the image. E.g., a scale factor of 2 will reduce the image dimensions by half.
    
    Returns:
    --------
        np.ndarray: The downscaled image as a numpy array.
    """
    max_size = 1920
    if scale_factor is None:
        # compute scale factor based on the image size such that the maximum dimension is 1200 pixels
        scale_factor = 1.0
        max_dimension = max(image.shape[:2])
        if max_dimension > max_size:
            scale_factor = max_dimension / max_size
    elif scale_factor <= 0:
        raise ValueError("Scale factor must be greater than 0.")

    new_size = (int(image.shape[1] / scale_factor), int(image.shape[0] / scale_factor))
    downscaled_image = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
    return downscaled_image

def polish_input_image_file(file) -> np.ndarray:
    image = Image.open(file.stream).convert("RGB")
    np_image = np.array(image)
    np_image = downscale_image(np_image, scale_factor=None)
    return np_image.astype(np.uint8)

# def polish_input_image_file(file) -> np.ndarray: 
#     """
#     This function processes the input image file and returns the image as a numpy array.
#     It handles HEIC files by converting them to PNG format and ensures the image has no alpha channel.
#     """

#     print('Polishing input image file.')
#     image = Image.open(file.stream)
#     print('1')

#     if file.filename.split('.')[-1].upper() == 'HEIC':
#         unique_query = str(request.args.get('nocache'))
#         path = f'temp/temp_{unique_query}.png'
#         image.save(path)
#         image = Image.open(path)

#         np_image = np.concatenate((np.array(image), np.ones((image.size[1], image.size[0], 1), dtype=np.uint8)*255), axis=2)
#     else:
#         np_image = np.array(image)

#     # if the image is BW image, convert it to RGB
#     if len(np_image.shape) == 2:
#         np_image = np.stack((np_image,)*3, axis=-1)

#     if file.filename.split('.')[-1].upper() == 'HEIC':
#         # delete the temporary file
#         os.remove(path)
    
#     # if the image has more than 4 channels, convert it to RGB
#     if np_image.shape[2] > 3:
#         np_image = np_image[:, :, :3]

#     # downscale the image if it is larger than 1200 pixels in any dimension
#     np_image = downscale_image(np_image, scale_factor=None)

#     return np_image.astype(np.uint8)


@deprecated("currently used directly in process_image function")
def temporary_store_image(image: np.ndarray):
    """
    This function creates a temporary storage for the image, i.e. it creates a new UserTemporaryStorage object
    and assigns it to the session['user_id'] key in the ts dictionary.
    """
    storage.from_dict({
        'experiment_id': None,
        'color': image.copy(),
        'asphalt_mask': np.zeros(image.shape[:2], dtype=int),
        'aggregate_mask': np.zeros(image.shape[:2], dtype=int),
        'asphalt_mask_manual_corrections': np.zeros(image.shape[:2], dtype=int), # TODO consider replacement with NONE - if no corrections are made, we do not need to store the array
        'aggregate_mask_manual_corrections': np.zeros(image.shape[:2], dtype=int), # TODO consider replacement with NONE - if no corrections are made, we do not need to store the array
        'img_width': image.shape[1],
        'img_height': image.shape[0],
    })
    # # manual corrections
    # ts[session['user_id']].asphalt_mask_manual_corrections = np.zeros(ts[session['user_id']].color_original.shape[:2], dtype=int)
    # ts[session['user_id']].aggregate_mask_manual_corrections = np.zeros(ts[session['user_id']].color_original.shape[:2], dtype=int)
    # # initialize the masks
    # ts[session['user_id']].asphalt_mask = np.zeros_like(ts[session['user_id']].asphalt_mask_manual_corrections, dtype=int)
    # ts[session['user_id']].aggregate_mask = np.zeros_like(ts[session['user_id']].asphalt_mask_manual_corrections, dtype=int)

    # TODO: consider removing the entropy calculation from here, as it is not used in the current approach
    # ts[session['user_id']].entropy_original = ts[session['user_id']].gray_original.copy()
    # ts[session['user_id']].entropy = ts[session['user_id']].entropy_original.copy()
    # ts[session['user_id']].values.entropy_min_threshold = 0
    # ts[session['user_id']].values.entropy_max_threshold = 255


@app.route('/process-image',methods=['POST'])
def process_image():
    # This function processes the image and returns the processed image
    # it should be called when the user wants to process the image
    file = request.files['file']
    image = polish_input_image_file(file)
    # temporary_store_image(image)
    
    storage.from_dict({
        'experiment_id': None,
        'color': image.copy(),
        'asphalt_mask': np.zeros(image.shape[:2], dtype=int),
        'aggregate_mask': np.zeros(image.shape[:2], dtype=int),
        'asphalt_mask_manual_corrections': np.zeros(image.shape[:2], dtype=int), # TODO consider replacement with NONE - if no corrections are made, we do not need to store the array
        'aggregate_mask_manual_corrections': np.zeros(image.shape[:2], dtype=int), # TODO consider replacement with NONE - if no corrections are made, we do not need to store the array
        'img_width': image.shape[1],
        'img_height': image.shape[0],
    })

    # get hash of the image for similarity check
    authenticated = session.get('authenticated', False)
    if authenticated:
        print('here')
        img_hashes = app_similarity_controller.return_hashes(Image.fromarray(image))
        storage.from_dict(img_hashes)

    save_experiment(state='started')

    # let the background thread handle the similarity check
    if authenticated:
        print('Checking image similarity in the background thread.')
        similarity_controller.controll_experiment(user_id=session['user_id'], experiment_id=storage.experiment_id)

    response_dict = {
        'status': 'success',
        'color': storage.color,
        'gray': grayscale_image(storage.color),  # convert to list for JSON serialization
    }
    response_json = dict_to_json(response_dict)


    return response_json, 200, {'Content-Type': 'application/json'}


@deprecated("used in thresholding approach, but not in the current one")
def get_masks_with_manual_corrections():
    """
    Get the masks with manual corrections.
    
    Returns:
    tuple: A tuple containing asphalt_mask, aggregate_mask, and background_mask.
    """
    asphalt_mask = return_asphalt_mask()
    aggregate_mask = return_aggregate_mask()
    background_mask = return_background_mask()
    # asphalt_mask = ts[session['user_id']].asphalt_mask + ts[session['user_id']].asphalt_mask_manual_corrections
    # aggregate_mask = ts[session['user_id']].aggregate_mask + ts[session['user_id']].aggregate_mask_manual_corrections
    # background_mask = np.ones_like(asphalt_mask) - asphalt_mask - aggregate_mask
    return asphalt_mask, aggregate_mask, background_mask

def to_base64(image_array: np.ndarray) -> str:
    """
    Convert a numpy array to a base64 encoded string.
    
    Parameters:
    array (numpy.ndarray): The numpy array to encode.
    
    Returns:
    str: Base64 encoded string of the array.
    """
    return base64.b64encode(encode_to_png(image_array)).decode('utf-8')

# @app.route('/remove-asphalt',methods=['POST'])

@app.route('/inference',methods=['POST'])
def inference_image():
    storage.inference_model = request.form.get('model_name', None)
    print()
    print('Inference should be model set to:', request.form.get('model_name', None))
    print('Inference model set to:', storage.inference_model)
    print()


    if storage.inference_model is None:
        return json.dumps({'status': 'error', 'message': 'Model name is required.'}), 400, {'Content-Type': 'application/json'}

    # OLD CODE - REPLACED BY A SINGLE FUNCTION
    # input_data = torch.from_numpy(storage.color).unsqueeze(0).float()  # Add batch channel dimension
    # input_data = input_data.permute(0, 3, 1, 2)  # Change to torch (batch_size, channels, height, width)
    
    # print("input_data.shape")
    # print(input_data.shape)

    # model_prediction = inference(model_name=storage.inference_model,
    #                              input_data=input_data,
    #                              session_id=session['user_id'])
    
    # # get model prediction and save it to the sessions
    # asphalt_mask, aggregate_mask, background_mask = models.postprocess_model_prediction(model_prediction)
    asphalt_mask, aggregate_mask, background_mask = models.inference_on_numpy(
        np_image=storage.color,
        model_name=storage.inference_model,
        session_id=session['user_id']
    )
    # save the masks to the storage
    storage.from_dict({
        'asphalt_mask': asphalt_mask.astype(int),
        'aggregate_mask': aggregate_mask.astype(int),
        'background_mask': background_mask.astype(int)
    })
    # save to db
    save_experiment(state='started')

    # return the masks with manual corrections
    asphalt_mask, aggregate_mask, background_mask = storage.get_masks_with_manual_corrections()
    # asphalt_mask = ts[session['user_id']].get_asphalt_mask()
    # aggregate_mask = ts[session['user_id']].get_aggregate_mask()
    # background_mask = ts[session['user_id']].get_background_mask()

    # save the masks to the session
    # ts[session['user_id']].asphalt_mask = asphalt_mask.astype(int)
    # ts[session['user_id']].aggregate_mask = aggregate_mask.astype(int)
    # ts[session['user_id']].background_mask = background_mask.astype(int)

    json_response = {
        'status': 'success',
        'asphalt_mask': to_base64(bool_to_image_array(asphalt_mask)),
        'aggregate_mask': to_base64(bool_to_image_array(aggregate_mask)),
        'background_mask': to_base64(bool_to_image_array(background_mask))
    }
    json_response = dict_to_json(json_response)

    # return json.dumps(json_response), 200, {'Content-Type': 'application/json'}
    return json_response, 200, {'Content-Type': 'application/json'}


@app.route('/remove-background',methods=['POST'])
@deprecated("used in thresholding approach, but not in the current one")
def remove_picture_background():
    # this function returns a suggested mask, i.e. boolean matrix  
    # denoting wether a pixel should (T) or should not (F) be taken into
    # account during the other computations
    # adjust the mask by setting a manual threshold 
    
    # read the necessary properties
    file = request.files['file']
    # check wether the file is .heic and if so, convert it to .png
    threshold=128 #consider changing this to a value from the form that user can set # threshold=request.form.get('threshold')
    image = polish_input_image_file(file)
    
    # if the alpha channel is not present, add it  
    # if np_image.shape[2] == 3:
    #     np_image = np.concatenate((np_image, np.ones((np_image.shape[0], np_image.shape[1], 1), dtype=np.uint8)*255), axis=2)

    # image = request.form.get('image')
    # image=np.array(request.form.get('image'),dtype=np.int8)
    
    print('SAVED SHAPE ORIGINAL', ts[session['user_id']].color_original.shape)
    # remove the background
    image = np.array(remove(image))
    
    # if file.filename[-len('.HEIC'):].upper() == '.HEIC':
    #     print('HEIC file detected. TRANSPOSE')
    #     image = image.transpose((1,0,2))

    # sharpen the mask
    mask = image[:, :, 3]
    mask[mask > threshold] = 255
    mask[mask <= threshold] = 0
    # assign the sharpen mask to the alpha channel
    image[:, :, 3] = mask
        
    # save the requested variables (in future this should be different function, doing everything at once and more 
    # importantly, at the end, when the user is satisfied with the result so we won't be constantly overwriting the DB)
    ts[session['user_id']].aggregate_mask = np.array(mask/255, dtype=int)
    ts[session['user_id']].values.threshold = threshold
    ts[session['user_id']].color = image
    
    # allocate the memory for the manual corrections and the asphalt mask
    ts[session['user_id']].asphalt_mask = np.zeros_like(mask, dtype=int)
    ts[session['user_id']].asphalt_mask_manual_corrections = np.zeros_like(mask, dtype=int)
    ts[session['user_id']].aggregate_mask_manual_corrections = np.zeros_like(mask, dtype=int)
    
    # return the mask
    print('Background removed')

    json_response = {'original_image': to_base64(ts[session['user_id']].color_original),
                     'nobg': to_base64(ts[session['user_id']].color)}
    return json.dumps(json_response), 200, {'Content-Type': 'application/json'}
    # return encode_to_png(image), 200, {'Content-Type': 'image/png'}


@app.route('/entropy', methods=['POST'])
@deprecated("used in thresholding approach, but not in the current one")
def calculate_entropy():
    # np_gray = cv2.imread('temp/gray_temp.jpg', cv2.IMREAD_GRAYSCALE)
    np_gray = ts[session['user_id']].gray
    # Calculate local entropy
    entropy_image = entropy(img_as_ubyte(np_gray), disk(5))

    # Normalize the entropy image
    normalized_entropy = cv2.normalize(entropy_image, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    np_entropy = np.uint8(normalized_entropy)
    # cv2.imwrite('temp/entropy_temp.jpg', np_entropy)
    ts[session['user_id']].entropy = np_entropy
    ts[session['user_id']].entropy_original = np_entropy
    print('Entropy calculated.')

    # Store entropy image for later use
    img_byte_arr = io.BytesIO()
    Image.fromarray(np_entropy).save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr, 200, {'Content-Type': 'image/png'}

def encode_to_png(image):
    # creates a byte stream ('buffer') for binary operations
    image_io=io.BytesIO()
    Image.fromarray(np.uint8(image)).save(image_io, format='PNG') #saves the img as PNG to the byte stream ('buffer')
    # image.save(image_io, format='PNG') #saves the img as PNG to the byte stream ('buffer')
    image_io.seek(0)
    return image_io.getvalue()

# TODO repair the image blur - err: when a value of blur is set 
@app.route('/blur', methods=['POST'])
@deprecated("used in thresholding approach, but not in the current one")
def blur_caller():
    blur_value = int(request.form.get('blurValue', 0))
    ts[session['user_id']].values.blur = blur_value
    # calls twice the function for the blur_image for the gray image and image entropy
       
    ts[session['user_id']].color=blur_image(blur_value,image=ts[session['user_id']].color_original)
    ts[session['user_id']].gray=blur_image(blur_value,image=ts[session['user_id']].gray_original)
    ts[session['user_id']].entropy=blur_image(blur_value,image=ts[session['user_id']].entropy_original)

    #  encode the images to PNG
    encoded_gray = encode_to_png(ts[session['user_id']].gray) 
    encoded_color = encode_to_png(ts[session['user_id']].color)
    encoded_no_bg = encode_to_png(ts[session['user_id']].color*ts[session['user_id']].aggregate_mask[:,:,None])
    # print('ci shape',ts[session['user_id']].color.shape)
    # print('mask shape',ts[session['user_id']].aggregate_mask.shape)
    
    encoded_gray = base64.b64encode(encoded_gray).decode('utf-8')
    encoded_color = base64.b64encode(encoded_color).decode('utf-8')
    encoded_no_bg = base64.b64encode(encoded_no_bg).decode('utf-8')
    
    return json.dumps({'gray': encoded_gray, 'color': encoded_color, 'nobg': encoded_no_bg}), 200, {'Content-Type': 'application/json'}

def blur_image(blur_value,image):
    if blur_value <= 0:
        blur_value = 0
        pass
    elif blur_value % 2 == 0:
        blur_value -= 1  # Make it odd by adding 1 if it's even
        image = cv2.GaussianBlur(image, (blur_value, blur_value), 0)
    else:
        image = cv2.GaussianBlur(image, (blur_value, blur_value), 0)
    print('Image blurred, blur kernel size %d.' % blur_value)
    return image


@app.route('/apply-mask', methods=['POST'])
@deprecated("used in thresholding approach, but not in the current one")
def apply_mask():
    # 
    warn("Old endpoint will be removed soon", DeprecationWarning)
    flash("⚠️ This endpoint APPLY-MASK is deprecated and will be removed in a future version.", "warning")


    # Assuming the image's ID or a unique identifier is sent as part of the form data for key lookup
    image_id = request.form.get('imageId')
    min_threshold_0 = int(request.form.get('minThreshold0', 0))
    max_threshold_0 = int(request.form.get('maxThreshold0', 100))
    min_threshold_1 = int(request.form.get('minThreshold1', 100))
    max_threshold_1 = int(request.form.get('maxThreshold1', 255))
    entropy_min_threshold = int(request.form.get('entropyMinThreshold', 0))
    entropy_max_threshold = int(request.form.get('entropyMaxThreshold', 255))
    
    # save the values
    storage.from_dict(request.form.to_dict())
    
    # ts[session['user_id']].values.intensity_min_threshold_0 = min_threshold_0
    # ts[session['user_id']].values.intensity_max_threshold_0 = max_threshold_0
    # ts[session['user_id']].values.intensity_min_threshold_1 = min_threshold_1
    # ts[session['user_id']].values.intensity_max_threshold_1 = max_threshold_1
    # ts[session['user_id']].values.entropy_min_threshold = entropy_min_threshold
    # ts[session['user_id']].values.entropy_max_threshold = entropy_max_threshold    
    
    print('Mask applied')
    # np_gray = cv2.imread('temp/gray_temp.jpg', cv2.IMREAD_GRAYSCALE)
    # np_entropy = cv2.imread('temp/entropy_temp.jpg', cv2.IMREAD_GRAYSCALE)
    # np_gray = ts[session['user_id']].gray
    # np_entropy = ts[session['user_id']].entropy
    
    # min_thresholds = [min_threshold_0, min_threshold_1]
    # max_thresholds = [max_threshold_0, max_threshold_1]    
    # print('Thresholds:', min_thresholds, max_thresholds)
    # print('Entropy thresholds:', entropy_min_threshold, entropy_max_threshold)
    # if image_id == 'gray':
    #     print('Gray image selected.')
    #     overlay_image = apply_red_overlay(np_gray, np_gray, np_entropy, min_thresholds, max_thresholds,
    #                                       entropy_min_threshold, entropy_max_threshold)
    # else:
    #     print('Color image selected.')
    #     overlay_image = apply_red_overlay(np_entropy, np_gray, np_entropy, min_thresholds, max_thresholds,
    #                                       entropy_min_threshold, entropy_max_threshold)

    overlay_image = get_masks_with_manual_corrections()[0]
    overlay_image = np.dstack([overlay_image]*3)*255
    overlay_image = to_base64(overlay_image)
    return json.dumps({'overlay': overlay_image}), 200, {'Content-Type': 'application/json'}

def return_aggregate_mask():
    """
    Returns a mask of the aggregate, i.e. pixels that are aggregate by automatic detection or manual corrections.
    """
    mask = ts[session['user_id']].aggregate_mask + ts[session['user_id']].aggregate_mask_manual_corrections
    ic('AGG')
    ic(np.sum(mask) / mask.shape[0] / mask.shape[1])
    return mask.astype(bool)
    
def return_asphalt_mask():
    """
    Returns a mask of the asphalt, i.e. pixels that are asphalt by automatic detection or manual corrections.
    """
    mask = ts[session['user_id']].asphalt_mask + ts[session['user_id']].asphalt_mask_manual_corrections
    ic('ASP')
    ic(np.sum(mask) / mask.shape[0] / mask.shape[1])
    return mask.astype(bool)

def return_foreground_mask() -> np.ndarray:
    """
    Returns a mask of the foreground, i.e. pixels that are asphalt or aggregate.
    """
    mask = return_asphalt_mask() | return_aggregate_mask()
    return mask.astype(bool)    

def return_background_mask() -> np.ndarray:
    """
    Returns a mask of the background, i.e. pixels that are not asphalt and not aggregate.
    """
    # return the mask of the background, i.e. pixels that are not asphalt and not aggregate
    mask = np.logical_not(return_foreground_mask())
    return mask.astype(bool)

@deprecated("used in thresholding approach, but not in the current one.")
def apply_red_overlay(masked_img, intensity_img, entropy_img, min_thresholds, max_thresholds, entropy_min_threshold,
                      entropy_max_threshold):        
    intensity_mask_0 = (intensity_img >= min_thresholds[0]) & (intensity_img <= max_thresholds[0])
    intensity_mask_1 = (intensity_img >= min_thresholds[1]) & (intensity_img <= max_thresholds[1])
    entropy_mask = (entropy_img >= entropy_min_threshold) & (entropy_img <= entropy_max_threshold)
    # combined_mask = intensity_mask & entropy_mask 

    intensity_mask = intensity_mask_0 | intensity_mask_1
    combined_mask = intensity_mask & entropy_mask
    combined_mask &= return_foreground_mask() 
    # print('Combined mask:', np.sum(combined_mask))
    # print('Foreground mask:', np.sum(return_foreground_mask()))
    # Create an RGBA version of the processed data
    rgba_image = np.dstack([masked_img] * 3 + [np.full(masked_img.shape, 255, dtype=np.uint8)])

    # Prepare the red overlay
    red_overlay = np.zeros_like(rgba_image, dtype=np.uint8)
    red_overlay[..., 0] = 255  # Red channel full intensity
    red_overlay[combined_mask] = [255, 0, 0, 128]  # Semi-transparent red overlay where mask is True
    # Combine the original image with the overlay
    # overlay_image = Image.alpha_composite(Image.fromarray(rgba_image), Image.fromarray(red_overlay))
    fg_mask = return_foreground_mask().astype(int)
    # adjust the manual corrections    
    ts[session['user_id']].asphalt_mask = (red_overlay[:,:,-1] == 128).astype(int)
    ts[session['user_id']].aggregate_mask = fg_mask - ts[session['user_id']].asphalt_mask

    print('Overlay applied.')

    return red_overlay

def get_inner_shape(shape_object):
    # raise NotImplementedError
    grid_size_x, grid_size_y = ts[session['user_id']].color_original.shape[:2]
    y, x = np.meshgrid(np.arange(grid_size_x), np.arange(grid_size_y))
    points = np.vstack((x.ravel(), y.ravel())).T
    match shape_object["type"]:
        case "polygon":
            poly_path = polygon_path([p for p in zip(shape_object["points"][::2], shape_object["points"][1::2])])
            mask = poly_path.contains_points(points).reshape((grid_size_y, grid_size_x))
        case "rectangle":
            min_x, min_y = min(shape_object["points"][::2]), min(shape_object["points"][1::2])
            max_x, max_y = max(shape_object["points"][::2]), max(shape_object["points"][1::2])
            mask = (x >= min_x) & (x <= max_x) & (y >= min_y) & (y <= max_y)
        case "ellipse":
            np_points = np.array(shape_object["points"])
            center = (np_points[:2]+np_points[2:4])/2
            radius_x = np.abs(np_points[0] - center[0])
            radius_y = np.abs(np_points[-1] - center[1])
            mask = (((x - center[0]) / radius_x) ** 2 + ((y - center[1]) / radius_y) ** 2 ) <= 1
    return np.array(mask, dtype=bool).T

@deprecated("used in thresholding approach, but not in the current one.")
def correct_mask(mask: np.ndarray, label: str) -> None:
    match label:
        case "asphalt":
            lidx = mask & ~ts[session['user_id']].asphalt_mask
            ts[session['user_id']].asphalt_mask_manual_corrections[lidx.astype(bool)] = 1
            lidx = mask & ts[session['user_id']].asphalt_mask
            ts[session['user_id']].asphalt_mask_manual_corrections[lidx.astype(bool)] = 0
            lidx = mask & abs(ts[session['user_id']].aggregate_mask_manual_corrections)
            ts[session['user_id']].aggregate_mask_manual_corrections[lidx.astype(bool)] = 0
            lidx = mask & ts[session['user_id']].aggregate_mask
            ts[session['user_id']].aggregate_mask_manual_corrections[lidx.astype(bool)] = -1

        case "aggregate":
            lidx = (mask & ~ts[session['user_id']].aggregate_mask).astype(bool)
            ts[session['user_id']].aggregate_mask_manual_corrections[lidx] = 1
            lidx = (mask & ts[session['user_id']].aggregate_mask).astype(bool)
            ts[session['user_id']].aggregate_mask_manual_corrections[lidx] = 0
            lidx =( mask & abs(ts[session['user_id']].asphalt_mask_manual_corrections)).astype(bool)
            ts[session['user_id']].asphalt_mask_manual_corrections[lidx] = 0
            lidx = (mask & ts[session['user_id']].asphalt_mask).astype(bool)
            ts[session['user_id']].asphalt_mask_manual_corrections[lidx] = -1
        case "background":
            lidx = (mask & abs(ts[session['user_id']].aggregate_mask_manual_corrections)).astype(bool)
            ts[session['user_id']].aggregate_mask_manual_corrections[lidx] = 0
            lidx = (mask & abs(ts[session['user_id']].asphalt_mask_manual_corrections)).astype(bool)
            ts[session['user_id']].asphalt_mask_manual_corrections[lidx] = 0
            lidx = (mask & (ts[session['user_id']].aggregate_mask)).astype(bool)
            ts[session['user_id']].aggregate_mask_manual_corrections[lidx] = -1
            lidx = (mask & (ts[session['user_id']].asphalt_mask)).astype(bool)
            ts[session['user_id']].asphalt_mask_manual_corrections[lidx] = -1
            
    return None



@app.route('/get-corrected-mask', methods=['GET'])
@deprecated("used in thresholding approach, but not in the current one.")
def get_corrected_mask() -> tuple[dict, int, dict]:
    # choose intensity for drawing the masks
    intensity = 51 
    
    draw_mask_aggregate=np.zeros_like(ts[session['user_id']].color_original)
    draw_mask_aggregate[:,:,3]=intensity*return_aggregate_mask()
    encoded_aggregate = encode_to_png(draw_mask_aggregate)
    
    draw_mask_asphalt=np.zeros_like(ts[session['user_id']].color_original)
    draw_mask_asphalt[:,:,3]=intensity*return_asphalt_mask()
    encoded_asphalt = encode_to_png(draw_mask_asphalt)

    draw_mask_aggregate[:,:,3][~np.any(ts[session['user_id']].aggregate_mask_manual_corrections | ts[session['user_id']].aggregate_mask, axis=-1)]=0
    
    draw_mask_bg=np.zeros_like(ts[session['user_id']].color_original)
    draw_mask_bg[:,:,3] = intensity * (~return_foreground_mask())
    encoded_bg = encode_to_png(draw_mask_bg)
    
    encoded_aggregate = base64.b64encode(encoded_aggregate).decode('utf-8')
    encoded_asphalt = base64.b64encode(encoded_asphalt).decode('utf-8') 
    encoded_bg = base64.b64encode(encoded_bg).decode('utf-8')
    
    # return encoded_bg, encoded_aggregate, encoded_asphalt
    json_response = {'status': 'success', 
                     'bg': encoded_bg, 
                     'aggregate': encoded_aggregate, 
                     'asphalt': encoded_asphalt}
    return json.dumps(json_response), 200, {'Content-Type': 'application/json'}

@app.route('/save-annotation', methods=['POST'])
@ignore_unauthenticated
# @check_authentication
@deprecated("Used for manual annotation correction in thresholding approach, but not in the current one.")
def save_annotation():
    # Annotate the data according to the request
    annotation = request.get_json()
    mask = get_inner_shape(annotation["shape"])
    correct_mask(mask, annotation["label"])             
    # Save the annotation to the database
    save_experiment()
    print('Annotation saved.')
    # return masks for bg, aggregate and asphalt
    return get_corrected_mask()
    

    # encoded_bg, encoded_aggregate, encoded_asphalt = get_corrected_mask()
    # json_response = {'status': 'success', 'bg': encoded_bg, 'aggregate': encoded_aggregate, 'asphalt': encoded_asphalt}
    # return json.dumps(json_response), 200, {'Content-Type': 'application/json'}


@app.route('/get-default-experiment-info', methods=['GET'])
@check_authentication
def get_default_experiment_info():
    # Update the default experiment info in the database
    response = db_api.get_default_experiment_info(user_id=session['user_id'])
    # experiment_id = db_api.return_active_experiment_id(user_id=session['user_id'])
    # print('Experiment ID:', experiment_id)
    # print('response:', response)
    # if experiment_id:
    #     for key, value in response.items(): 
    #         db_api.update_experiment_in_db(values_dict={key: value}, experiment_id=experiment_id)
    #     # db_api.update_experiment_in_db(values_dict=response, experiment_id=experiment_id)
    return json.dumps({'status': 'success', 'data': response}), 200, {'Content-Type': 'application/json'}

@app.route('/update-default-experiment-info', methods=['POST'])
@check_authentication
def update_default_experiment_info():
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    # Update the default experiment info in the database
    db_api.update_default_experiment_info(user_id=session['user_id'], field=field, value=value)
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/node_modules/<path:path>')
def send_node_modules(path):
    return send_from_directory('node_modules', path)

@app.route('/translations-alerts')
def translations_alerts():
    json_translations = {
        'noExperiment': _('No sample data found.'),
        'expertGuessEmpty': _('Please fill the expert guess field before evaluating the sample.'),
        'evaluationCompleted': _('Evaluation completed. Check the console for the results.'),
        'evaluationResults': _('Evaluation results: '),
        'evaluationDemo': _('Would you like to use this app with no limitations? Store and export these results? Contact us to create an account.'),
        'noEmployeesSelected': _('No employees selected for intended action.'),
        'noExperimentsSelectedforDeletion': _('No sample selected for deletion.'),
        'sureDeleteExperiments': _('Are you sure you want to delete the selected samples?'),
        'cannotBeUndone': _('This action cannot be undone.'),
        'selectExperimetnsToViewDetails': _('Please select sample to view details.'),
        'selectJustOneExperimetnsToViewDetails': _("Please select only one sample for viewing details."),
        'selectAtLeastOneExperimentForExport': _('Please select at least one sample for export.'),
        'exportSingleExperimentNotAllowed': _('For CSN 73 6161, exporting a single sample is not allowed.'),
        'exportSingleExperimentProceeding': _('Do you want to proceed with exporting this single sample?'),
        'grantAdmin': _('Are you sure, you want to grant admin privileges to the following users?'),
        'removeAdmin': _('Are you sure, you want to remove admin privileges from the following users?'),
        'blockUser': _('Are you sure, you want to block the sign in option for the following users?'),
        'unblockUser': _('Are you sure, you want to unblock the sign in option for the following users?'),
    }
    return json.dumps(json_translations), 200, {'Content-Type': 'application/json'}

if __name__ == "__main__":
    debug = True
    if debug:
        app.secret_key='test_secret_key'
        app.run(debug=debug)
    else:
        app.secret_key='test_secret_key'
        app.run(host='127.0.0.1', port=5000, debug=debug)
        # app.run(host='0.0.0.0', port=5011, debug=debug)
