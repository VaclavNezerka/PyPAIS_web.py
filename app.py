# Packages
import uuid
import pendulum as pdl
import requests
from flask import (Flask, render_template, request, send_file, 
                   send_from_directory, flash, redirect,
                   session, url_for, abort, g, has_request_context)
from flask_mail import Mail, Message
import werkzeug.security as ws
from werkzeug.local import LocalProxy
from markupsafe import Markup
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()
import numpy as np
import io
import imagehash
import cv2
import time
from datetime import timedelta
import secrets
import hashlib
import string
import os
import mimetypes
import db_api
import json
import base64
from matplotlib.path import Path as polygon_path
from rich.traceback import install
from typing import Iterable, Literal, cast
from flask_talisman import Talisman
import flask_limiter
from flask_limiter.util import get_remote_address
import threading
import warnings
from werkzeug.middleware.proxy_fix import ProxyFix
install()

from dotenv import load_dotenv
from typing_extensions import deprecated
from models import discover_models
import models
import decimal
from flask_babel import Babel, _, lazy_gettext, get_locale as get_babel_locale
from werkzeug.exceptions import HTTPException
import math
#Similarity controller
import app_similarity_controller 
similarity_controller = app_similarity_controller.ImageSimilarityController()
from app_report_exporter import exporter_registry, get_CSN_73_6161_classification, get_CSN_73_6161_word_classification
# Apps
import forms 
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from db_api import db_name, db_user, dbpwd, db_host
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
import pickle, zlib
import time
from urllib.parse import urlencode

load_dotenv(dotenv_path='.env')
RECAPTCHA_SITE_KEY=os.getenv('RECAPTCHA_SITE_KEY')
RECAPTCHA_SECRET_KEY=os.getenv('RECAPTCHA_SECRET_KEY')

app = Flask(__name__) # set debug to False for production

# UPLOAD LIMITS - request size and the size of decoded images (anybody can upload in the demo)
MAX_IMAGE_SIDE = 1920  # longer side of the stored and evaluated photo
# share of the photo the model has to find as bitumen or aggregate - below it the photo shows no sample
# (real samples cover 25-60 % of their photo, plots or photos of other things about 1 %)
MIN_SAMPLE_AREA = float(os.getenv('MIN_SAMPLE_AREA', '0.05'))
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_MB', '40')) * 1024 * 1024
Image.MAX_IMAGE_PIXELS = int(os.getenv('MAX_IMAGE_MEGAPIXELS', '100')) * 1_000_000
warnings.simplefilter('error', Image.DecompressionBombWarning)  # over the limit is an error, not just a warning


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

@app.before_request
def end_session_of_blocked_user():
    # blocking takes effect right away - checking it only at login left the blocked user's session running
    if session.get('authenticated') and request.endpoint != 'static' and db_api.is_user_blocked(user_id=session['user_id']):
        lang = session.get('lang')
        session.clear()
        session['lang'] = lang
        flash(_('Your account has been blocked. In case this should not be the case, please contact your company admin.'), 'error')
        return redirect(url_for('login'))

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
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # behind one proxy, e.g., nginx, apache (x_for: real client address for rate limits)
Talisman(app, content_security_policy=csp, force_https=False) # for security headers, force https



# LANGUAGE CONFIGURATION
# code -> name in its own language, in the order of the language menu (flags: static/language_icons/<code>.svg);
# every language except English (the source texts) needs translations/<code>/LC_MESSAGES/messages.po
LANGUAGE_NAMES = {'cs': 'Čeština', 'en': 'English', 'de': 'Deutsch', 'it': 'Italiano', 'pl': 'Polski'}
app.config['BABEL_DEFAULT_LOCALE'] = 'cs'
app.config['BABEL_SUPPORTED_LOCALES'] = list(LANGUAGE_NAMES)
# app.config['BABEL_TRANSLATION_DIRECTORIES'] = ['translations']
app.config['LANGUAGES'] = list(LANGUAGE_NAMES)
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
        lang = request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES']) or app.config['BABEL_DEFAULT_LOCALE']
        session['lang'] = lang
    return lang

babel = Babel(app, locale_selector=get_locale)

@app.context_processor
def inject_template_globals():
    # the language actually used for the page (drives <html lang>, the flag in the navbar and ui.js texts)
    return {'current_lang': str(get_babel_locale() or app.config['BABEL_DEFAULT_LOCALE']),
            'language_names': LANGUAGE_NAMES}

# the self-hosted web font; Python's MIME table may not know the extension (it was sent as octet-stream)
mimetypes.add_type('font/woff2', '.woff2')

@app.url_defaults
def static_file_version(endpoint, values):
    # url_for('static', ...) gets ?v=<modification time>: after an update browsers load the new
    # stylesheet/scripts instead of a copy they cached heuristically (Flask sends no max-age)
    if endpoint == 'static' and 'filename' in values and 'v' not in values:
        path = os.path.join(app.static_folder, values['filename'])
        if os.path.isfile(path):
            values['v'] = int(os.path.getmtime(path))

def rate_limit_key() -> str:
    # logged-in users per account, everybody else per client address (ProxyFix x_for provides the real one);
    # the random user_id of guests is not used - it changes with every new session
    return f"user:{session['user_id']}" if session.get('authenticated') else get_remote_address()

limiter = flask_limiter.Limiter(
    app=app,
    key_func=rate_limit_key,
    default_limits=["500 per day", "500 per hour"],
    # e.g. redis://localhost:6379 - otherwise every gunicorn worker counts separately
    storage_uri=os.getenv('RATELIMIT_STORAGE_URI', 'memory://'),
)
# stricter limits for forms that send e-mails or check passwords, and for the expensive image endpoints
FORM_RATE_LIMIT = "10 per minute;60 per hour"
IMAGE_RATE_LIMIT = "30 per minute"

HASH_METHOD = os.getenv('HASH_METHOD', 'pbkdf2:sha256')
SALT_LENGTH = os.getenv('SALT_LENGTH', '16')
def generate_rnd_string(length):
    possible_chars=string.ascii_letters+string.digits+string.punctuation
    return ''.join(secrets.choice(possible_chars) for _ in range(int(length))) 
# required: a random fallback differed in every gunicorn worker (and after every restart),
# so sessions and e-mail links signed by one worker were rejected by the others
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    raise RuntimeError('SECRET_KEY is not set. Put a long random value into .env, e.g. the output of: '
                       'python -c "import secrets; print(secrets.token_urlsafe(32))"')

def generate_password_hash(password: str) -> str:
    return ws.generate_password_hash(password,method=HASH_METHOD,salt_length=int(SALT_LENGTH))

class TemporaryStorage:
    """
    A class for storing temporary data for the user.
    This ensures that the user can only access their own data.
    This class replaces the need for a previous solution which was current_images dictionary.
    """
    def __init__(self, **kwargs):
        self.user_id = None
        # values
        self.info_sample_label = None # user's own designation of the sample (shown in the records table)
        self.info_datetime = None
        self.info_place_of_experiment = None
        self.info_sample_collection_data = None
        self.info_wrapping_temperature_aggregate = None
        self.info_wrapping_temperature_binder = None
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
        self._dirty_fields = set()  # to track which fields have been modified

    @staticmethod
    def _to_bytes(arr):
        buf = io.BytesIO()
        np.save(buf, arr, allow_pickle=False)
        return buf.getvalue()

    @staticmethod
    def _from_bytes(blob):
        if blob is None:
            return None
        return np.load(io.BytesIO(blob), allow_pickle=False)


    @classmethod
    def load(cls, experiment_id):
        
        if experiment_id is None:
            print("No experiment_id provided, returning empty UserTemporaryStorage instance.")
            return cls()  # return an empty instance if no experiment_id is provided
        else:
            exp_dict = db_api.get_experiment_by_id(experiment_id)  # ensure the experiment exists in the database
            if not exp_dict:
                # the sample was deleted (e.g. from the records) - forget it instead of failing on every request
                session['experiment_id'] = None
                return cls()
            return cls(**exp_dict)  # initialize the UserTemporaryStorage instance with the data from the database

    @classmethod
    def save(self):
        
        print('Saving storage to database...')
        print(f'Current dirty fields: {self._dirty_fields}')
        data_dict = self.to_dict(for_save=True)
        experiment_id = data_dict.pop('experiment_id', None)
        if self.experiment_id is None:
             self.experiment_id = db_api.insert_experiment_to_db(values_dict=data_dict)
        
        db_api.update_experiment_in_db(values_dict=data_dict, experiment_id=experiment_id)
        self._dirty_fields.clear()  # reset dirty fields after saving
        print(f'Current dirty fields: {self._dirty_fields}')


    def __setattr__(self, name: str, value):
        if hasattr(self, '_dirty_fields'):
            self._dirty_fields.add(name)
        super().__setattr__(name, value)
        
            
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
            dic['asphalt_ratio'] = self.get_asphalt_ratio() 
            # Convert numpy arrays to bytes for database storage
            for key, value in dic.items():
                if isinstance(value, np.ndarray):
                    # dic[key] = value.tobytes() 

                    # NP.SAVE APPROACH - KEEPS THE METADATA LIKE SHAPE AND DTYPE
                    buffer = io.BytesIO()
                    np.save(buffer, value)
                    dic[key] = buffer.getvalue()  # This is what you store in SQL (e.g., BLOB/BYTEA column)
                elif isinstance(value, imagehash.ImageHash):
                    dic[key] = str(value)  # store imagehash as string

            dic.pop('experiment_id', None)  # remove experiment_id from the dict when saving to db  
        dic.pop('_dirty_fields', None)  # remove _dirty_fields from the dict when saving to db

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
    
    
class UserTemporaryStorage(TemporaryStorage):
    """
    A class for storing temporary data for the authenticated user.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dirty_fields = set()  # to track which fields have been modified
        
    def to_dict(self, features = None, for_save = False):
        dict = super().to_dict(features, for_save)
        dict.pop('_dirty_fields', None)  # remove _dirty_fields from the dict when saving to db
        return dict
    
    
    @staticmethod
    def _to_bytes(arr):
        buf = io.BytesIO()
        np.save(buf, arr, allow_pickle=False)
        return buf.getvalue()

    @staticmethod
    def _from_bytes(blob):
        if blob is None:
            return None
        return np.load(io.BytesIO(blob), allow_pickle=False)


    @classmethod
    def load(cls, experiment_id):
        
        if experiment_id is None:
            return cls()  # return an empty instance if no experiment_id is provided
        else:
            exp_dict = db_api.get_experiment_by_id(experiment_id)  # ensure the experiment exists in the database
            if not exp_dict:
                # the sample was deleted (e.g. from the records) - forget it instead of failing on every request
                session['experiment_id'] = None
                return cls()
            return cls(**exp_dict)  # initialize the UserTemporaryStorage instance with the data from the database

    @classmethod
    def save(self):
        
        data_dict = self.to_dict(for_save=True)
        experiment_id = data_dict.pop('experiment_id', None)
        if self.experiment_id is None:
             self.experiment_id = db_api.insert_experiment_to_db(values_dict=data_dict)
        
        db_api.update_experiment_in_db(values_dict=data_dict, experiment_id=experiment_id)
        self._dirty_fields.clear()  # reset dirty fields after saving

    def __setattr__(self, name: str, value):
        if hasattr(self, '_dirty_fields'):
            self._dirty_fields.add(name)
        super().__setattr__(name, value)
    
class GuestTemporaryStorage(TemporaryStorage):
    """
    A class for storing temporary data for unauthenticated users.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    def __setattr__(self, name: str, value):
        super().__setattr__(name, value)
        # written back to the session once per request (save_guest_storage) - pickling the photo and masks
        # on every attribute change cost hundreds of MB of work per upload
        if has_request_context():
            g.guest_storage_dirty = True

serializer = URLSafeTimedSerializer(app.secret_key)


# Public address of the app (e.g. https://aibal.example.cz) for links in e-mails. Without it the links are built
# from the request's Host / X-Forwarded-Host header, which a client can forge to point e-mailed tokens elsewhere.
APP_BASE_URL = os.getenv('APP_BASE_URL', '').rstrip('/')
if not APP_BASE_URL:
    print('WARNING: APP_BASE_URL is not set - links in e-mails are built from the request host header.')

def external_url(endpoint: str, **values) -> str:
    """Absolute URL of an endpoint for e-mails and texts shown to users (based on APP_BASE_URL when set)."""
    if APP_BASE_URL:
        return APP_BASE_URL + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)

app.jinja_env.globals['external_url'] = external_url

def password_fingerprint(user_id: int | None) -> str:
    """Changes whenever the user's password changes - binds e-mailed password links to it, so they work only once."""
    pwd_hash = db_api.get_password_hash(user_id=user_id) if user_id is not None else None
    return hashlib.sha256((pwd_hash or '').encode()).hexdigest()[:16]

def load_password_token(token: str, salt: str) -> tuple[str, int]:
    """E-mail and user ID from a password link; raises BadSignature when the password was changed since it was sent."""
    data = serializer.loads(token, salt=salt, max_age=MAX_TOKEN_AGE)
    user_id = db_api.get_user_id(email=data['e_mail'])
    if user_id is None or data.get('pwd') != password_fingerprint(user_id):
        raise BadSignature('password link already used')
    return data['e_mail'], user_id

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
        confirm_url = external_url(confirmation, token=token)
        
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
        except SignatureExpired:  # a subclass of BadSignature - must be caught first
            flash(_('The confirmation link has expired.'), 'danger')
            return redirect(url_for('home'))
        except BadSignature:
            flash(_('The confirmation link is invalid'), 'danger')
            return redirect(url_for('home'))
    return wrapper

@app.route('/forgot_password', methods=['GET', 'POST'])
@limiter.limit(FORM_RATE_LIMIT, methods=['POST'], key_func=get_remote_address)
def forgot_password_form():
    dynamic_content = _('Forgot your password? Enter your email address.')
    form = forms.EmailForgotPasswordForm()
    match request.method:
        case 'GET' | 'HEAD':
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
                        data={'e_mail': e_mail_address, 'pwd': password_fingerprint(user)},
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
        case 'GET' | 'HEAD':
            email, user_id = load_password_token(token, 'forgot_password-salt')  # valid for MAX_TOKEN_AGE, until the password changes
            db_api.confirm_user_email(email)
            form = forms.ChangeForgottenPasswordForm()
            flash(_('You can now reset your password!'), 'success')
            return render_template('form.html', form=forms.ChangeForgottenPasswordForm(), token=token, recaptcha_site_key=RECAPTCHA_SITE_KEY), 200
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form = forms.ChangeForgottenPasswordForm()
            if form.validate_on_submit():
                email, user_id = load_password_token(token, 'forgot_password-salt')
                password_hash = generate_password_hash(form.new_password.data)
                if not db_api.update_users_table(values_dict={'pwd': password_hash}, user_id=user_id):
                    flash(_('There was an error setting your password. Please try again.'), 'danger')
                    return render_template('form.html', form=form, token=token, recaptcha_site_key=RECAPTCHA_SITE_KEY), 500
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
        case 'GET' | 'HEAD':
            email, user_id = load_password_token(token, 'confirm_company_registration_user-salt')  # valid until the password is set
            db_api.confirm_user_email(email)
            print(f'Confirming company registration for user email: {email}')
            form = forms.ChangeForgottenPasswordForm()
            flash(_('Your email address has been confirmed. Please, create your password to complete the registration!'), 'success')
            return render_template('form.html', form=forms.ChangeForgottenPasswordForm(), token=token, recaptcha_site_key=RECAPTCHA_SITE_KEY), 200
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form = forms.ChangeForgottenPasswordForm()
            if form.validate_on_submit():
                email, user_id = load_password_token(token, 'confirm_company_registration_user-salt')
                password_hash = generate_password_hash(form.new_password.data)
                if not db_api.update_users_table(values_dict={'pwd': password_hash}, user_id=user_id):
                    flash(_('There was an error setting your password. Please try again.'), 'danger')
                    return render_template('form.html', form=form, token=token, recaptcha_site_key=RECAPTCHA_SITE_KEY), 500
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
    db_api.confirm_company_registration(datadict['company_id'])
    
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
        data={'e_mail': datadict['e_mail'], 'pwd': password_fingerprint(user_id)},
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



@app.teardown_request
def save_storage(exception=None):
    storage = getattr(g, "storage", None)
    conn = getattr(g, "db", None)

    if storage is None or conn is None:
        return

    try:
        # only persist if something changed
        if getattr(storage, "_dirty_fields", None):
            if storage._dirty_fields:
                storage.save()

    except Exception as e:
        # never crash teardown (Flask will already be unwinding)
        app.logger.exception("Failed to save storage: %s", e)

def _get_storage() -> TemporaryStorage:
    # Ensure session has a user_id
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

    # Attempt to load storage from session
    if session.get('authenticated', False) == True:
        if not hasattr(g, "storage") or g.storage is None:
            
            experiment_id = session.get('experiment_id', None)
            print(f'Loading storage for experiment_id: {experiment_id}')
            g.storage =  UserTemporaryStorage.load(experiment_id)
            storage_obj = g.storage
        else:
            storage_obj = g.storage
    else:
        # guests keep their sample in the session; it is unpickled once per request (the proxy calls this function
        # on every attribute access) and saved back once by save_guest_storage
        if getattr(g, 'guest_storage', None) is None:
            storage_data = session.get('storage')
            if storage_data:
                g.guest_storage = pickle.loads(zlib.decompress(storage_data))
                g.guest_storage_dirty = False
            else:
                g.guest_storage = GuestTemporaryStorage(user_id=session['user_id'])
                g.guest_storage_dirty = True
        storage_obj = g.guest_storage

    return storage_obj

@app.after_request
def save_guest_storage(response):
    # runs before Flask-Session stores the session
    if getattr(g, 'guest_storage_dirty', False) and getattr(g, 'guest_storage', None) is not None:
        session['storage'] = zlib.compress(pickle.dumps(g.guest_storage))
    return response



storage = LocalProxy(lambda: _get_storage())
storage: TemporaryStorage = cast(TemporaryStorage, storage) # behaves like a global variable, but it is actually a proxy to the user-specific storage 


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
    session['lang'] = lang_code
    return json.dumps({'lang': lang_code}), 200

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

def check_data_ownership(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # the owner, or an admin of the owner's company (one query)
        if db_api.can_access_experiment(user_id=session['user_id'], experiment_id=kwargs['id']):
            return func(id=kwargs['id'])
        # all guarded routes are called by fetch(): a JSON 403 - a redirect arrived there as "200 OK" with a page
        return json.dumps({'status': 'error', 'message': _('You do not have permission to access this data.')}), 403, {'Content-Type': 'application/json'}
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
    """Company admins only (a NULL flag counts as no admin). Use below @check_authentication."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = db_api.get_user_by_id(session['user_id']) if session.get('authenticated') else None
        if user and user['is_company_admin']:
            return func(*args, **kwargs)
        # 403 instead of a redirect to the login page, which logged the user out
        abort(403, description=_('You do not have permission to access this page.'))
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
def index():
    # visitors start on the landing page with the demo, signed-in users on their current sample
    if not session.get('authenticated'):
        return redirect(url_for('home'))
    models = discover_models()
    return render_template('index.html', session=session, models=models), 200

@app.route('/is-users-experiment/<int:id>', methods=['GET'])
@check_authentication
@check_data_ownership
def is_users_experiment(id: int):
    user_id = session.get('user_id', None)
    experiment_user_id = db_api.get_user_id_of_experiment(id=id)
    is_users = (experiment_user_id == user_id)
    return json.dumps({'is_users': is_users}), 200, {'Content-Type': 'application/json'}
    
    
    
@app.route('/home', methods=['GET','POST'])
@limiter.limit(FORM_RATE_LIMIT, methods=['POST'], key_func=get_remote_address)
def home():
    models = discover_models()
    title = _('Contact us!')
    match request.method:
        case 'GET' | 'HEAD':
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

@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(413)
@app.errorhandler(429)
@app.errorhandler(500)
def http_error(error):
    code = error.code if isinstance(error, HTTPException) and error.code else 500
    titles = {
        400: _('The request could not be processed'),
        403: _('You do not have permission to access this page.'),
        404: _('Page not found'),
        405: _('The request could not be processed'),
        413: _('The uploaded file is too large'),
        429: _('Too many requests - please wait a moment and try again'),
        500: _('Something went wrong on our side'),
    }
    # show descriptions the app passed to abort(); werkzeug's generic English ones are replaced by the title
    custom = isinstance(error, HTTPException) and code != 500 and error.description != type(error).description
    message = error.description if custom else _('If the problem persists, please contact us.')
    return render_template('error.html', code=code, title=titles.get(code, titles[500]), message=message), code



@app.route('/logout')
def logout():
    print('Logging out user.')
    lang = session.get('lang')
    session.clear()  # Clear all session data to ensure complete logout
    session['lang'] = lang  # ... but keep the chosen language
    return redirect(url_for('login'))

#TODO - consider joining with edit_personal_information (Must be done together with FE editing)
@app.route('/change-email',methods=['GET','POST'])
@check_authentication
def change_email():
    # the new address is used only after it is confirmed from the e-mail sent to it (confirm_email_change)
    title = _('Change email')
    match request.method:
        case 'GET' | 'HEAD':
            form=forms.ChangeEmailForm()
            return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.ChangeEmailForm()
            if form.validate_on_submit():
                if not is_password_correct(password=form.password.data, user_id=session['user_id']):
                    form.password.errors.append(_('The password is not correct.'))
                    return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
                sent = send_email_confirmation(
                    to_mails=[form.e_mail.data],
                    data={'user_id': session['user_id'], 'e_mail': form.e_mail.data},
                    confirmation='confirm_email_change',
                    intro_text=_('You have requested a change of an email address.'
                                'Please confirm your new email address by clicking the button below:'),
                    title=_('AIBAL: Confirm your new email address')
                )
                if sent:
                    flash(_('We have sent a confirmation link to the new address. The e-mail address will change once you open it.'), 'success')
                else:
                    flash(_('There was an error sending your message. Please try again.'), 'error')
                return redirect('/user')
            else:
                return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)

@app.route('/confirm_email_change/<token>')
@confirm_request
def confirm_email_change(token: str):
    """Switches the user's e-mail address to the confirmed new one."""
    data = serializer.loads(token, salt='confirm_email_change-salt', max_age=MAX_TOKEN_AGE)
    if db_api.get_user_id(email=data['e_mail']) is not None:
        flash(_('This email address is already used. Please use a different one.'), 'error')
    elif db_api.update_users_table(values_dict={'e_mail': data['e_mail']}, user_id=data['user_id']):
        flash(_('Email changed successfully.'), 'success')
    else:
        flash(_('There was an error while changing your e-mail address. Please try again.'), 'error')
    return redirect('/user' if session.get('authenticated') else url_for('login'))

@app.route('/change-company-email',methods=['GET','POST'])
@check_authentication
@check_is_company_admin
def change_company_email():
    # TODO: !!! CONFIRMATION EMAIL !!!
    title = _('Change company email')
    match request.method:
        case 'GET' | 'HEAD':
            form=forms.ChangeCompanyEmailForm()
            return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.ChangeCompanyEmailForm()
            if form.validate_on_submit():
                if not is_password_correct(password=form.password.data, user_id=session['user_id']):
                    form.password.errors.append(_('The password is not correct.'))
                    return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
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
        case 'GET' | 'HEAD':
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
@check_is_company_admin
def edit_company_information():
    match request.method:
        case 'GET' | 'HEAD':
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
        case 'GET' | 'HEAD':
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
                    if not db_api.update_users_table(values_dict={'pwd': new_password_hash}, user_id=session['user_id']):
                        flash(_('Database error - the data was not saved. Please try again.'), 'error')
                        return render_template('form.html',dynamic_content=title,form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY), 500
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

def company_member_id(username: str | None) -> int:
    """
    ID of the user with the given username in the current admin's company. Aborts with 400 for unknown users,
    users of other companies and the admin's own account (admin actions must not cross company boundaries).
    """
    user_id = db_api.get_user_id(username=username) if username else None
    member = db_api.get_user_by_id(user_id=user_id) if user_id is not None else None
    if member is None or member['company'] != db_api.get_user_by_id(user_id=session['user_id'])['company']:
        abort(400, description=_('User with the provided username does not exist'))
    if user_id == session['user_id']:
        abort(400, description=_('You cannot change your own account here.'))
    return user_id

@app.route('/change-user-blockade',methods=['POST'])
@check_authentication
@check_is_company_admin
def change_user_blockade():
    print('Changing user blockade...')
    user_to_alter_id = company_member_id(request.form.get('username', None))

    # get the future status
    will_be_blocked = request.form.get('will_be_blocked','false').lower() == 'true'
    db_api.change_user_blockade(user_id=user_to_alter_id, is_blocked=will_be_blocked)
    return json.dumps({'status': 'success'}), 200

def return_max_page(total_pages, endpoint, **kwargs):
    # Clamp page
    page = int(kwargs.get('page', None) or 1)
    print(f'Checking page: {page} against total pages: {total_pages}')
    if page > total_pages:
        print(f'\n')
        print(f'\n')
        print(f'Redirecting to max page: {total_pages}')
        kwargs['page'] = total_pages
        print(url_for(endpoint, **(kwargs or {})))
        print(f'\n')
        print(f'\n')
        return redirect(url_for(endpoint, **(kwargs or {})))
    elif page < 1:
        print(f'Redirecting to max page: {total_pages}')
        kwargs['page'] = 1
        return redirect(url_for(endpoint, **(kwargs or {})))
    else:
        pass

@app.route('/change-admin-privileges',methods=['POST'])
@check_authentication
@check_is_company_admin
def change_admin_privileges():
    print('Changing admin privileges...')
    user_to_alter_id = company_member_id(request.form.get('username', None))

    # get the future status
    will_be_admin = request.form.get('will_be_admin','false').lower() == 'true'
    db_api.change_admin_privileges(user_id=user_to_alter_id, is_admin=will_be_admin)
    return json.dumps({'status': 'success'}), 200


@app.route('/login',methods=['GET','POST'])
@limiter.limit(FORM_RATE_LIMIT, methods=['POST'], key_func=get_remote_address)
def login():
    if 'authenticated' in session and session['authenticated']:
        logout()
    match request.method:
        case 'GET' | 'HEAD':
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
                print(f'User {user_id} authenticated {authenticated}.')
                if authenticated:
                    # a new session id at login (session fixation); the guest data of the old session is not needed
                    lang = session.get('lang')
                    session.clear()
                    session['lang'] = lang
                    session['authenticated'] = True
                    print(f'User {user_id} authenticated successfully.')
                    session['user_id'] = user_id
                    session['user_email'] = form.usernameXe_mail.data
                    session['is_admin'] = False
                    if db_api.get_user_by_id(user_id=user_id)['is_company_admin']:
                        session['is_admin'] = True
                    app.session_interface.regenerate(session)  # after filling it - regenerate() skips an empty session
                    print(' Session after login:')
                    print(session)
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


def sample_designation(label: str | None, collection_data: str | None) -> str:
    """Sample designation for the records table. Older samples without one show their collection data instead (marked)."""
    if label:
        return label
    if collection_data:
        return Markup('<span class="designation-fallback" title="{}">{}</span>').format(_('Sample Collection Data:'), collection_data)
    return ''

def matches_search(query: str | None, experiment_id: int, label: str | None, collection_data: str | None) -> bool:
    """Case-insensitive search of the records table by sample designation (or its fallback) and sample ID."""
    query = (query or '').strip().lower()
    return not query or query in str(experiment_id) or query in (label or collection_data or '').lower()

RECORD_SORT_KEYS = ('id', 'sample_label', 'time_stamp', 'name', 'expert_guess', 'asphalt_ratio', 'current_state')

def format_percent(ratio) -> str | None:
    return f"{float(ratio) * 100:.1f} %" if ratio is not None else None

def get_experiment_records(is_admin: bool, **kwargs) -> tuple[list[dict], int, int]:
    """
    Sample records for the records table: the user's own samples, or all samples of the company for an admin.
    Filtered by the search query, sorted and paginated. Returns (records of the page, number of pages, number of matches).
    """
    sort_order, page_limit, start_sub_id, page, sort_by = get_query_args(**kwargs)
    if is_admin:
        company_id = db_api.get_user_by_id(session['user_id'])['company']
        rows = db_api.get_all_company_experiments(company_id) or []
    else:
        rows = db_api.get_user_experiments(session['user_id']) or []

    records = [{
        'id': x['experiment_id'],
        'designation': sample_designation(x['info_sample_label'], x['info_sample_collection_data']),
        'designation_text': x['info_sample_label'] or x['info_sample_collection_data'] or '',
        'date': x['time_stamp'].strftime('%Y-%m-%d %H:%M'),
        'time_stamp': x['time_stamp'],
        'name': f"{x.get('first_name', '')} {x.get('last_name', '')}".strip(),
        'contact': x.get('e_mail'),
        'expert_guess': format_percent(x['expert_guess']),
        'asphalt_ratio': format_percent(x['asphalt_ratio']),
        'raw_expert_guess': x['expert_guess'],
        'raw_asphalt_ratio': x['asphalt_ratio'],
        'finished': x['current_state'] == 'finished',
    } for x in rows if matches_search(kwargs.get('q'), x['experiment_id'], x['info_sample_label'], x['info_sample_collection_data'])]

    sort_keys = [key for key in sort_by.split(',') if key in RECORD_SORT_KEYS] or ['time_stamp']
    sort_values = {
        'sample_label': lambda r: r['designation_text'].lower(),
        'expert_guess': lambda r: float(r['raw_expert_guess']) if r['raw_expert_guess'] is not None else -1,
        'asphalt_ratio': lambda r: float(r['raw_asphalt_ratio']) if r['raw_asphalt_ratio'] is not None else -1,
        'current_state': lambda r: r['finished'],
        'name': lambda r: r['name'].lower(),
    }
    records.sort(key=lambda r: [sort_values.get(key, lambda r: r[key])(r) for key in sort_keys], reverse=sort_order == 'desc')

    pages = get_num_pages(len(records), page_limit)
    start_sub_id, max_sub_id = get_start_and_max_sub_id(page, page_limit, len(records), start_sub_id)
    return records[start_sub_id:max_sub_id], pages, len(records)

def deactivation_pages(page: int, pages: int) -> tuple[bool, bool, int]:
    # deactivating pages 
    deactivate_next = False
    deactivate_prev = False
    
    if page == 1 and pages == 1:
        deactivate_next = True
        deactivate_prev = True
    elif page == 1:
        deactivate_next = False
        deactivate_prev = True
    elif page == pages:
        deactivate_next = True
        deactivate_prev = False
    elif page > pages:
        page = pages
        deactivate_next = True
        deactivate_prev = False if pages > 1 else True
    
    return deactivate_next, deactivate_prev, page 

def query_int(value, default: int, minimum: int = 1, maximum: int = 10_000) -> int:
    """Integer from a query string argument - invalid values fall back to the default instead of a 500."""
    try:
        return min(maximum, max(minimum, int(value)))
    except (TypeError, ValueError):
        return default

def get_query_args(**kwargs) -> dict:
    dt = {
        'sort_order': 'asc' if kwargs.get('sort_order') == 'asc' else 'desc',
        'page_limit': query_int(kwargs.get('page_limit'), 10, maximum=200),
        'start_id': kwargs.get('start_id', None),
        'page': query_int(kwargs.get('page'), 1),
        'sort_by': kwargs.get('sort_by') or 'time_stamp,id,expert_guess,asphalt_ratio'
    }

    return [value for value in dt.values()]

def get_start_and_max_sub_id(page: int, page_limit: int, len_data: int, start_sub_id: int = None) -> tuple[int, int]:
    start_sub_id = page_limit * (page - 1)
    max_sub_id = start_sub_id + page_limit    
    return start_sub_id, max_sub_id

def normalize_page_or_redirect(total_pages, args=None) -> 'requests.Response | None':
    args = args or request.args.to_dict()
    page = query_int(args.get("page"), 1)
    total_pages = max(1, total_pages)
    # Clamp
    print(f'Normalizing page: {page} against total pages: {total_pages}')
    valid_page = max(1, min(page, total_pages))
    if page != valid_page:
        args["page"] = valid_page
        return redirect(f"{request.path}?{urlencode(args)}")
    return None

@app.route('/experiments',methods=['GET','POST'])
@check_authentication
def experiments():
    kwargs = request.args.to_dict()
    is_admin = bool(db_api.get_user_by_id(session['user_id'])['is_company_admin'])
    records, pages, total = get_experiment_records(is_admin, **kwargs)

    redirect_response = normalize_page_or_redirect(pages, args=kwargs)
    if redirect_response:
        return redirect_response
    sort_order, page_limit, _start, page, sort_by = get_query_args(**kwargs)
    return render_template('experiments.html', records=records, is_admin=is_admin, page=page, pages=max(1, pages),
                           total=total, page_limit=page_limit, sort_by=sort_by.split(',')[0], sort_order=sort_order,
                           search=kwargs.get('q', ''), args=kwargs)
    
def get_num_pages(total_items: int, page_limit: int) -> int:
    pages = total_items // page_limit
    pages = pages + 1 if total_items % page_limit > 0 else pages
    return pages
    
@app.route('/employees',methods=['GET','POST'])
@check_authentication
@check_is_company_admin
def employees():
    company_id = db_api.get_user_by_id(session['user_id'])['company']
    employees = [{
        'name': f"{x['first_name']} {x['last_name']}",
        'username': x['username'],
        'e_mail': x['e_mail'],
        'is_admin': bool(x['is_company_admin']),
        'is_blocked': bool(x['is_blocked']),
        'is_me': x['id'] == session['user_id'],
    } for x in db_api.get_all_company_employees(company_id) or []]
    employees.sort(key=lambda e: e['name'].lower())
    return render_template('employees.html', employees=employees)
    
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
@limiter.limit(FORM_RATE_LIMIT, methods=['POST'], key_func=get_remote_address)
def register():
    # shown next to the form: users join an existing company with its key, a new company registers separately
    optional_content = Markup(
        '<div class="auth-aside"><h2>{}</h2><p>{}</p><a class="btn" href="/register-company">{}</a></div>'
    ).format(_("Is your company not registered yet?"),
             _("This form registers a user of an already registered company - you need its company key from your company admin. A new company is registered first and confirmed by us."),
             _("Register new company"))
    if session.get('authenticated', False):
        optional_content = ""

    match request.method:
        case 'GET' | 'HEAD':
            form=forms.RegistrationFormUser()

            return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY, optional_content_below=optional_content)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.RegistrationFormUser()
            if form.validate_on_submit():
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
                result = db_api.save_new_user_db(values=user_dict)  # True, or None when the insert failed
                if result:
                    # the confirmation e-mail only after the account really exists
                    send_email_confirmation(
                        to_mails=[form.e_mail.data],
                        data={'e_mail': form.e_mail.data},
                        confirmation='confirm_email',
                        intro_text=_('Thank you for signing up! Please confirm your email address by clicking the link below:'),
                        title=_('AIBAL: Please confirm your email address')
                    )
                    if session.get('authenticated', False) and session.get('is_admin', False):
                        # do not log out the admin user who is registering a new user
                        flash(message=_('User registered successfully. The user will be notified via the provided email address.'), category='success')
                        return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY, optional_content_below=optional_content), 200
                    else:
                        flash(message=_('Registration successful. Please confirm your email via the link sent to your email address (the process may take a few minutes).'),category='success')
                        return redirect(url_for('login')), 302
                else:
                    flash(message=_('Database error - the data was not saved. Please try again.'), category='error')
                    return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY, optional_content_below=optional_content), 500
            else:
                flash(message=_('Form validation failed. Please check your input.'),category='error')
                return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY, optional_content_below=optional_content)

@app.route('/regenerate-company-key',methods=['POST'])
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
    # no choice = the controller is the exporting user (see export_report)
    myself = (None, _('Me (the exporting user)'))
    if not users:
        users = [myself]
    else:
        users = [myself] + [(user['id'], f"{user['first_name']} {user['last_name']} ‹{user['e_mail']}›") for user in users
                            if user['id'] != session_user_id]
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
    experiment_ids = validate_report_experiment_ids(ids)
    if not experiment_ids or not are_experiments_accessible_by_user(session['user_id'], experiment_ids):
        flash(message=_('You do not have permission to access the selected experiments.'), category='error')
        return redirect(url_for('experiments'))
    samples = [{
        'id': s['experiment_id'],
        'designation': sample_designation(s['info_sample_label'], s['info_sample_collection_data']),
        'date': s['time_stamp'].strftime('%Y-%m-%d %H:%M'),
        'ai': format_percent(s['asphalt_ratio']),
        'expert': format_percent(s['expert_guess']),
        'finished': s['current_state'] == 'finished',
    } for s in db_api.get_experiment_summaries(experiment_ids) or []]

    def render_export_form(form):
        return render_template('export_report.html', form=form, samples=samples, recaptcha_site_key=RECAPTCHA_SITE_KEY)

    match request.method:
        case 'GET' | 'HEAD':
            form=forms.ExportReportForm()
            form.controlling_employee.choices = pick_users( session['user_id'])
            return render_export_form(form)
        case 'POST':
            form=forms.ExportReportForm()
            form.controlling_employee.choices = pick_users( session['user_id'])
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            if form.validate_on_submit():

                # generate report
                controlling_user_id = form.controlling_employee.data  # may be None
                if controlling_user_id is None or controlling_user_id == 'None':
                    controlling_user_id = session.get('user_id')
                ordering_party = {
                    'name': form.ordering_party_name.data,
                    'address': form.ordering_party_address.data,
                    'contact': form.ordering_party_e_mail.data,
                }

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
                return render_export_form(form)


@app.route('/register-company',methods=['GET','POST'])
@limiter.limit(FORM_RATE_LIMIT, methods=['POST'], key_func=get_remote_address)
def register_company():
    match request.method:
        case 'GET' | 'HEAD':
            form=forms.RegistrationFormCompany()
            return render_template('form.html',dynamic_content=_('Register new company'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)
        case 'POST':
            verify_recaptcha_or_abort(request.form.get('g-recaptcha-response',''))
            form=forms.RegistrationFormCompany()
            if form.validate_on_submit():
                values = {
                    'company_name': form.company_name.data,
                    'company_address': form.company_address.data,
                    'e_mail': form.e_mail.data,
                    'company_key': generate_company_key(),
                }
                result = db_api.save_new_company_db(values=values)  # True, or None when the insert failed
                if result:
                    # send email to admin for confirmation (only for a company that really was stored)
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
                    flash(message=_('Registration successful. Please confirm this request in your ADMIN mail account.'),category='success')
                    return redirect(url_for('login')), 302
                else:
                    flash(message=_('Database error - the data was not saved. Please try again.'), category='error')
                    return render_template('form.html',dynamic_content=_('Register new company'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY), 500
            else:
                flash(message=_('Form validation failed. Please check your input.'),category='error')
                return render_template('form.html',dynamic_content=_('Register new user'),form=form,session=session, recaptcha_site_key = RECAPTCHA_SITE_KEY)



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


# Experiment columns the sample form may change directly, with the labels used in error messages
EDITABLE_EXPERIMENT_FIELDS = {
    'info_sample_label': lazy_gettext('Sample Designation:'),
    'info_datetime': lazy_gettext('Date and Time:'),
    'info_place_of_experiment': lazy_gettext('Place of Experiment:'),
    'info_sample_collection_data': lazy_gettext('Sample Collection Data:'),
    'info_wrapping_temperature_aggregate': lazy_gettext('Wrapping Temperature of Aggregate [°C]:'),
    'info_wrapping_temperature_binder': lazy_gettext('Wrapping Temperature of Binder [°C]:'),
    'info_exposing_water_temperature': lazy_gettext('Exposing Water Temperature [°C]:'),
    'info_test_procedure': lazy_gettext('Test Procedure:'),
    'info_comment': lazy_gettext('Comment:'),
    'info_aggregate': lazy_gettext('Aggregate:'),
    'info_binder': lazy_gettext('Binder:'),
    'expert_guess': lazy_gettext('Expert Guess'),
    'inference_model': lazy_gettext('MODEL'),
}
NUMERIC_EXPERIMENT_FIELDS = {'info_wrapping_temperature_aggregate', 'info_wrapping_temperature_binder', 'info_exposing_water_temperature', 'expert_guess'}
MAX_LENGTH_EXPERIMENT_FIELDS = {'info_sample_label': 256}  # other text fields: 1024 (as the inputs' maxlength)

def clean_experiment_value(name: str, value: str | None):
    """Normalises a value of an editable experiment field sent by the client. Raises ValueError if it is invalid."""
    if value is None:
        return None
    value = value.strip()
    if value == '' or value.lower() == 'null':
        return None  # an emptied input is stored as NULL ('' is not a valid number or timestamp)
    if name in NUMERIC_EXPERIMENT_FIELDS:
        number = float(value.replace(',', '.'))
        if not math.isfinite(number) or (name == 'expert_guess' and not 0 <= number <= 1):
            raise ValueError(value)
        return number if name == 'expert_guess' else value.replace(',', '.')
    if name == 'info_datetime':
        pdl.parse(value)  # raises on an invalid timestamp
    elif len(value) > MAX_LENGTH_EXPERIMENT_FIELDS.get(name, 1024):
        raise ValueError(value)
    return value

def save_experiment_fields(raw_values: dict):
    """
    Validates the given editable fields and writes them to the user's active experiment in a single UPDATE.
    Always answers with JSON (also when the session has expired), so the client can tell the user whether the data was saved.
    """
    if not session.get('authenticated', False):
        return json.dumps({'status': 'error', 'message': _('Your session has expired. Please log in again - the last changes were not saved.')}), 401, {'Content-Type': 'application/json'}
    values = {}
    for name, raw in raw_values.items():
        if name not in EDITABLE_EXPERIMENT_FIELDS:
            return json.dumps({'status': 'error', 'field': name, 'message': f'Unknown field: {name}'}), 400, {'Content-Type': 'application/json'}
        try:
            values[name] = clean_experiment_value(name, raw)
        except ValueError:  # incl. pendulum's ParserError
            message = _('Invalid value:') + ' ' + str(EDITABLE_EXPERIMENT_FIELDS[name]).rstrip(':')
            return json.dumps({'status': 'error', 'field': name, 'message': message}), 400, {'Content-Type': 'application/json'}
    # the active experiment is kept in the DB (not the session), so all of the user's parallel requests agree on it
    experiment_id = db_api.return_active_experiment_id(user_id=session['user_id'])
    if experiment_id is None:
        return json.dumps({'status': 'error', 'message': _('No active sample - upload an image first.')}), 409, {'Content-Type': 'application/json'}
    if values and not db_api.update_experiment_in_db(values_dict=values, experiment_id=experiment_id):
        return json.dumps({'status': 'error', 'message': _('Database error - the data was not saved. Please try again.')}), 500, {'Content-Type': 'application/json'}
    return json.dumps({'status': 'success', 'experimentId': experiment_id, 'saved': list(values)}), 200, {'Content-Type': 'application/json'}

@app.route('/update_value/<string:value_name>',methods=['POST'])
@limiter.exempt
def update_specific_value(value_name):
    """Autosave of a single field of the sample form."""
    return save_experiment_fields({value_name: request.form.get(value_name)})

@app.route('/save-experiment-info',methods=['POST'])
@limiter.exempt
def save_experiment_info():
    """Explicit save of the whole sample form (the Save button, and before the evaluation)."""
    return save_experiment_fields(request.form.to_dict())

@app.route('/evaluate-asphalt',methods=['POST'])
@check_session_timeout
def evaluate_asphalt():
    asphalt_mask, aggregate_mask, background_mask = storage.get_masks_with_manual_corrections()
    if not sample_found(asphalt_mask, aggregate_mask):
        message = _('No asphalt sample was found in the photo, so the sample cannot be evaluated.')
        return json.dumps({'status': 'error', 'message': message}), 409, {'Content-Type': 'application/json'}
    evaluation = storage.get_asphalt_ratio()
    save_experiment(state='finished')
    print('Asphalt ratio evaluated:', evaluation)
    expert_guess = storage.expert_guess if storage.expert_guess not in (None, '') else None
    return json.dumps({
        'status': 'success',
        'evaluation': evaluation,
        'experimentId': storage.experiment_id,
        **adhesion_classification(evaluation),
        'expert': adhesion_classification(expert_guess),
    }), 200, {'Content-Type': 'application/json'}

# TODO: CORRECT THE METHOD - should be DELETE
@app.route('/delete-experiment/<int:id>',methods=['POST'])
@check_authentication
@check_data_ownership
def delete_experiment(id):
    experiment_state = db_api.execute_query('SELECT current_state FROM experiments WHERE experiment_id=%s', (id,))[0][0]
    try:
        if experiment_state == 'finished':
            query = 'UPDATE experiments SET fake_deleted=true WHERE experiment_id=%s'
            db_api.execute_query(query, (id,))
        else:
            query = 'DELETE FROM experiments WHERE experiment_id=%s'
            db_api.execute_query(query, (id,))
        # deleting the sample that is open on the Current Sample page closes it
        if db_api.return_active_experiment_id(user_id=session['user_id']) == id:
            db_api.update_experiment_active_status(user_id=session['user_id'], active=False)
        if session.get('experiment_id') == id:
            session['experiment_id'] = None
        status = 'success'
    except Exception as e:
        print(f'Deleting experiment {id} failed: {e}')
        status = 'error'
    return json.dumps({'status': status}), 200 if status == 'success' else 500, {'Content-Type': 'application/json'}

@app.route('/deactivate-current-experiment',methods=['POST'])
@check_authentication
def deactivate_current_experiment():
    id = db_api.return_active_experiment_id(user_id=session['user_id'])
    session['experiment_id'] = None
    storage = None
    return deactivate_experiment(id)

@app.route('/deactivate-experiment/<int:id>',methods=['POST'])
@check_authentication
@check_data_ownership
def deactivate_experiment_caller(id):
    return deactivate_experiment(id)

def deactivate_experiment(id):
    print('Deactivating experiment.', id)
    if id is None:
        flash(_('No active experiment found.'), 'error')
        return redirect('/'), 302
    db_api.update_experiment_active_status(user_id=session['user_id'], active=False)
    storage.experiment_id = None #**
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

@app.route('/activate-experiment/<int:id>',methods=['POST'])
@check_authentication
@check_data_ownership
def activate_experiment_caller(id):
    session['experiment_id'] = id
    return activate_experiment(id)

def activate_experiment(id):
    if id is None:
        id = storage.experiment_id
        if id is None:
            flash(_('No active experiment found.'), 'error')
            return redirect('/queue')
    # check if the experiment is already active if it is, deactivate it
    query = 'SELECT experiment_id FROM experiments WHERE user_id=%s AND active=True'
    active_id = db_api.execute_query(query, (session['user_id'],))
    print(active_id)
    if active_id:
        for i in active_id:
            print(i[0])
            r=deactivate_experiment(i[0])

    # activate the experiment
    print('before activating experiment:', id)
    db_api.update_experiment_active_status(user_id=session['user_id'], active=True, experiment_id=id)
    storage.experiment_id = id   
    print('Experiment activated:', id)
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}


@app.route('/load-experiment/<int:id>',methods=['GET'])
@check_authentication
@check_data_ownership  # it also makes the sample the user's working sample - later autosaves write into it
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
    if not response:
        return json.dumps({'status': 'error', 'message': _('No sample data found.')}), 404, {'Content-Type': 'application/json'}
    storage.from_dict(response)

    # stored masks are shown as they are - re-running the model on every opening changed the state and owner of the sample
    has_masks = any(mask is not None and np.any(mask) for mask in (storage.asphalt_mask, storage.aggregate_mask))
    dict_response = {
        'status': 'success',
        'experimentId': id,
        'current_state': response.get('current_state'),
        'has_masks': has_masks,
        'color': storage.color,
        'gray': grayscale_image(storage.color),
        # sample information for the form (raw mask arrays are not sent)
        **storage.to_dict(features=EDITABLE_EXPERIMENT_FIELDS),
    }
    if has_masks:
        dict_response.update(mask_overlays())
    owner_id = response.get('user_id')
    if owner_id is not None and owner_id != session.get('user_id'):
        # a company admin opened a colleague's sample - the page says whose it is
        owner = db_api.get_user_info_by_id(owner_id) or {}
        dict_response['owner'] = f"{owner.get('first_name') or ''} {owner.get('last_name') or ''}".strip() or owner.get('e_mail')
    return dict_to_json(dict_response), 200, {'Content-Type': 'application/json'}


# export the images folder
@app.route('/images/<path:filename>')
def download_file(filename):
    return send_from_directory('images', filename, as_attachment=True)


@app.route('/is-experiment-active',methods=['GET'])
def is_active():
    print('Checking if experiment is active.')
    if not session.get('authenticated', False):
        # guests and expired sessions have no stored experiment - their user_id is a random UUID, not a DB id,
        # so querying it ended in a "Database error" flash (e.g. for a page left open overnight)
        return json.dumps({'status': 'success', 'active': False, 'experimentId': None, 'authenticated': False}), 200, {'Content-Type': 'application/json'}
    experiment_id = db_api.return_active_experiment_id(user_id=session['user_id'])
    if experiment_id is not None and not db_api.get_experiment_timestamp_by_id(experiment_id):
        # the open sample no longer exists (deleted, e.g. by a company admin) - close it
        db_api.update_experiment_active_status(user_id=session['user_id'], active=False)
        experiment_id = None
    session['experiment_id'] = experiment_id #** ensure that the session is updated with the active experiment ID
    if experiment_id is not None:
        return json.dumps({'status': 'success', 'active': True, 'experimentId': experiment_id}), 200, {'Content-Type': 'application/json'}
    else:
        return json.dumps({'status': 'success', 'active': False, 'experimentId': None}), 200, {'Content-Type': 'application/json'}

@app.route('/save',methods=['POST'])
@ignore_unauthenticated
def save_experiment(**kwargs):
    """
    Saves the current experiment data to the database. If no experiment is active, a new one is created.
    """
    if 'state' in kwargs.keys():
        state = kwargs['state']
    else:
        state = request.args.get('state') or request.form.get('state') or 'started'
        # state = 'started'    


    ts_dict = storage.to_dict(for_save=True)
    if storage.experiment_id is not None:
        # Only write what this request changed: the storage is a snapshot loaded when the request started, so writing
        # all of it back would overwrite values saved by other requests in the meantime (e.g. the sample information
        # typed while /inference was running - it was silently reset to the values from before the inference).
        ts_dict = {key: value for key, value in ts_dict.items() if key in storage._dirty_fields or key == 'asphalt_ratio'}
    ts_dict['current_state'] = state
    # the owner is set once, on creation - a company admin who opens and edits a colleague's sample must not take it over
    if storage.experiment_id is None and session.get('authenticated', False):
        ts_dict['user_id'] = session['user_id']

    if storage.experiment_id is None:
        storage.experiment_id = db_api.insert_experiment_to_db(values_dict=ts_dict) #**
        session['experiment_id'] = storage.experiment_id #** ensure that the session is updated with the new experiment ID
        activate_experiment(storage.experiment_id)
    else:
        db_api.update_experiment_in_db(values_dict=ts_dict, experiment_id=storage.experiment_id)
    if state.lower() == 'finished':
        session.pop('storage', None)  # remove storage from session
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}


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
    max_size = MAX_IMAGE_SIDE
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
    image = Image.open(file.stream)  # raises for images over Image.MAX_IMAGE_PIXELS (decompression bombs)
    # large JPEGs are decoded at a reduced scale right away - still at least 2x the final size (see downscale_image)
    image.draft('RGB', (2 * MAX_IMAGE_SIDE, 2 * MAX_IMAGE_SIDE))
    image = image.convert("RGB")
    np_image = np.array(image)
    np_image = downscale_image(np_image, scale_factor=None)
    return np_image.astype(np.uint8)

@app.route('/process-image',methods=['POST'])
@limiter.limit(IMAGE_RATE_LIMIT)
def process_image():
    """
    This function processes the image and returns the processed image.
    It should be called when the user wants to process the image.
    """
    file = request.files.get('file')
    try:
        image = polish_input_image_file(file)
    except (AttributeError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        print(f'Rejected upload: {e!r}')
        return json.dumps({'status': 'error', 'message': _('Please choose an image file (JPG, PNG or HEIC).')}), 400, {'Content-Type': 'application/json'}

    storage.from_dict({
        'experiment_id': None,
        'color': image.copy(),
        # masks are 0/1 - uint8 instead of int64 keeps the stored blobs 8x smaller
        'asphalt_mask': np.zeros(image.shape[:2], dtype=np.uint8),
        'aggregate_mask': np.zeros(image.shape[:2], dtype=np.uint8),
        # no manual corrections exist yet (get_masks_corrected treats None as none) - no need to store zero arrays
        'asphalt_mask_manual_corrections': None,
        'aggregate_mask_manual_corrections': None,
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
    print('Exp saved')

    # let the background thread handle the similarity check
    if authenticated:
        print('Checking image similarity')
        similarity_controller.controll_experiment(user_id=session['user_id'], experiment_id=storage.experiment_id, target_image=Image.fromarray(image))
        print('in the background thread.')
    print('Similarity check should be running in the background thread.')

    response_dict = {
        'status': 'success',
        'color': storage.color,
        'gray': grayscale_image(storage.color),  # convert to list for JSON serialization
    }
    response_json = dict_to_json(response_dict)


    return response_json, 200, {'Content-Type': 'application/json'}

def to_base64(image_array: np.ndarray) -> str:
    """
    Convert a numpy array to a base64 encoded string.
    
    Parameters:
    array (numpy.ndarray): The numpy array to encode.
    
    Returns:
    str: Base64 encoded string of the array.
    """
    return base64.b64encode(encode_to_png(image_array)).decode('utf-8')


@app.route('/inference',methods=['POST'])
@limiter.limit(IMAGE_RATE_LIMIT)
def inference_image():
    model_name = request.form.get('model_name', None)
    if model_name not in discover_models():
        # the name ends up in torch.load - only the shipped models can be used
        return json.dumps({'status': 'error', 'message': _('Unknown model.')}), 400, {'Content-Type': 'application/json'}
    storage.inference_model = model_name #**
    
    if storage.color is None:
        return json.dumps({'status': 'error', 'message': 'No color image provided.'}), 200, {'Content-Type': 'application/json'}
    
    # # get model prediction and save it to the sessions
    asphalt_mask, aggregate_mask, background_mask = models.inference_on_numpy(
        np_image=storage.color,
        model_name=storage.inference_model,
    )
    # save the masks to the storage
    storage.from_dict({
        'asphalt_mask': asphalt_mask.astype(np.uint8),
        'aggregate_mask': aggregate_mask.astype(np.uint8),
        'background_mask': background_mask.astype(np.uint8)
    })
    # save to db
    save_experiment(state='started')

    # return the masks with manual corrections and the resulting assessment
    json_response = {'status': 'success', 'experimentId': storage.experiment_id, **mask_overlays()}
    return json.dumps(json_response), 200, {'Content-Type': 'application/json'}


def adhesion_classification(ratio: float | None) -> dict:
    """Asphalt coverage (0-1) as a percentage with its ČSN 73 6161 class, for the client."""
    if ratio is None:
        return {'asphalt_ratio': None, 'asphalt_percent': None, 'class': None, 'class_word': None}
    percent = round(float(ratio) * 100, 2)
    return {
        'asphalt_ratio': float(ratio),
        'asphalt_percent': percent,
        'class': get_CSN_73_6161_classification(percent),
        'class_word': get_CSN_73_6161_word_classification(percent),
    }

def sample_found(asphalt_mask, aggregate_mask) -> bool:
    """Whether the model found a sample in the photo at all (see MIN_SAMPLE_AREA)."""
    if asphalt_mask is None or aggregate_mask is None:
        return False
    return bool(np.count_nonzero(asphalt_mask) + np.count_nonzero(aggregate_mask) >= MIN_SAMPLE_AREA * np.size(asphalt_mask))

def mask_overlays() -> dict:
    """The masks of the current sample (with manual corrections) as transparent PNG overlays + the AI assessment."""
    asphalt_mask, aggregate_mask, background_mask = storage.get_masks_with_manual_corrections()
    found = sample_found(asphalt_mask, aggregate_mask)
    return {
        'asphalt_mask': to_base64(bool_to_image_array(asphalt_mask)),
        'aggregate_mask': to_base64(bool_to_image_array(aggregate_mask)),
        'background_mask': to_base64(bool_to_image_array(background_mask)),
        # no percentage and class for a photo without a sample - "0 %, unclassifiable" looked like a result
        'sample_found': found,
        **adhesion_classification(storage.get_asphalt_ratio() if found else None),
    }


def encode_to_png(image):
    # creates a byte stream ('buffer') for binary operations
    image_io=io.BytesIO()
    Image.fromarray(np.uint8(image)).save(image_io, format='PNG') #saves the img as PNG to the byte stream ('buffer')
    image_io.seek(0)
    return image_io.getvalue()
  
@deprecated("Manual corrections are currently not supported.")
def get_inner_shape(shape_object):
    # TODO: consider REMOVAL - UNUSED - NO MANUAL CORRECTIONS IN THE CURRENT APPROACH 
    # raise NotImplementedError
    grid_size_x, grid_size_y = storage.color.shape[:2]
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



@app.route('/get-default-experiment-info', methods=['GET'])
@check_authentication
def get_default_experiment_info():
    # Update the default experiment info in the database
    response = db_api.get_default_experiment_info(user_id=session['user_id'])
    return json.dumps({'status': 'success', 'data': response}), 200, {'Content-Type': 'application/json'}

@app.route('/update-default-experiment-info', methods=['POST'])
@check_authentication
@limiter.exempt
def update_default_experiment_info():
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    print(f'Updating default experiment info: {field} = {value}')
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
        'saveStatusSaving': _('Saving...'),
        'saveStatusSaved': _('All sample data saved at'),
        'saveStatusUnsaved': _('Unsaved changes'),
        'saveStatusError': _('NOT SAVED:'),
        'saveFailed': _('The sample data could not be saved, so the sample was not evaluated. Please try again.'),
        'evaluationFailed': _('The evaluation failed.'),
        'subtitleEmpty': _('Upload a photo of the sample to start the assessment.'),
        'sampleId': _('Sample ID'),
        'classLabel': _('Class'),
        'noSampleFound': _('No sample found'),
        'noSampleFoundHint': _('The model found no asphalt sample in this photo. Upload a photo of the tested sample on a plain background.'),
        'sampleOf': _('Sample of'),
        'processingPhoto': _('Processing the photo...'),
        'runningModel': _('The model is detecting bitumen and aggregate...'),
        'loadingSample': _('Loading the sample...'),
        'evaluating': _('Evaluating...'),
        'uploadFailed': _('The photo could not be processed.'),
        'inferenceFailed': _('The automatic detection failed.'),
        'notAnImage': _('Please choose an image file (JPG, PNG or HEIC).'),
        'defaultsApplied': _('Default values were filled in.'),
        'noDefaultsToApply': _('There are no default values for the empty fields. You can set them in your profile.'),
        'waitForModel': _('Wait until the automatic detection has finished.'),
        'confirm': _('Confirm'),
        'cancel': _('Cancel'),
        'delete': _('Delete'),
    }
    return json.dumps(json_translations), 200, {'Content-Type': 'application/json'}

if __name__ == "__main__":
    # development server only - production runs gunicorn (run_prod.sh); FLASK_DEBUG=1 turns on the debugger
    app.run(host='127.0.0.1', port=5000, debug=os.getenv('FLASK_DEBUG') == '1')
