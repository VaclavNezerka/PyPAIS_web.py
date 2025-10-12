# Packages
from attrs import field
from db_api import User
from flask import (Flask, render_template, request, 
                   send_from_directory, flash, redirect,
                   session, url_for, abort, g, make_response, send_file)
from flask_mail import Mail, Message
from wtforms import StringField
# from flask_login import login_manager, UserMixin, login_required,
import werkzeug.security as ws
from werkzeug.local import LocalProxy
from PIL import Image
import numpy as np
import io
from skimage.filters.rank import entropy
from skimage.morphology import disk
from skimage import img_as_ubyte
import cv2
import time
from datetime import timedelta
import secrets
import string
import os
from rembg import remove
from db_api import *
import db_api
import json
import base64
from matplotlib.path import Path as polygon_path
from icecream import ic
from rich.traceback import install
from typing import Iterable, Literal, cast
from flask_talisman import Talisman
install()

from warnings import warn,WarningMessage
import torch
from typing_extensions import deprecated
from models import discover_models, load_model, add_session_to_loaded_model, pop_session_from_loaded_models, inference



# Apps
import forms 
from functools import wraps

app = Flask(__name__) # set debug to False for production
csp = {
    'default-src': ["'self'"],
    'img-src': ["'self'", "data:", "blob:"],
}
Talisman(app, content_security_policy=csp) # for security headers, force https



# app.permanent_session_lifetime=timedelta(days=5)

# configuration of the mail server
# app.config['MAIL_SERVER'] = 'smtp.example.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USERNAME'] = 'your-email@example.com'
# app.config['MAIL_PASSWORD'] = 'your-email-password'
# app.config['MAIL_DEFAULT_SENDER'] = ('Your Name', 'your-email@example.com')
# app.config['ES6_MODULES'] = True

def generate_rnd_string(length):
    possible_chars=string.ascii_letters+string.digits+string.punctuation
    return ''.join(secrets.choice(possible_chars) for _ in range(int(length))) 
# if in production, use the environment variable, otherwise use the default value
app.secret_key=generate_rnd_string(os.environ['SECRET_KEY_LENGTH'])

def generate_password_hash(password: str) -> str:
    return ws.generate_password_hash(password,method=os.environ['HASH_METHOD'],salt_length=int(os.environ['SALT_LENGTH']))
ts = {} # temporary storages for the users... ts[user_id] = UserTemporaryStorage()

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
        self.info = None
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

        self.from_dict(kwargs)

    def from_dict(self, data_dict: dict) -> None:
        """
        Loads the attributes of the class from a dictionary.
        """
        for key, value in data_dict.items():
            if hasattr(self, key):
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
            # Convert numpy arrays to bytes for database storage
            for key, value in dic.items():
                if isinstance(value, np.ndarray):
                    dic[key] = value.tobytes()

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
        return asphalt_pixels / non_bg_pixels if non_bg_pixels > 0 else 0.0    

# storage: UserTemporaryStorage  = LocalProxy(lambda: ts.setdefault(session['user_id'], UserTemporaryStorage(user_id=session['user_id'])))
storage = LocalProxy(lambda: ts.setdefault(session['user_id'], UserTemporaryStorage(user_id=session['user_id'])))
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
        user_id = db_api.get_user_id_of_experiment(id=kwargs['id'])
        if user_id == session['user_id']:
            return func(id=kwargs['id'])
        else:
            flash('You do not have permission to access this data.','error')
            return redirect('/'), 302
    return wrapper

def check_authentication(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'authenticated' in session and session['authenticated']:
            return func(*args, **kwargs)
        else:
            flash('You must be logged in to access this page.','error')
            return redirect(url_for('login')), 302
    return wrapper

@app.route('/')
@check_authentication
def index():
    models = discover_models()
    return render_template('index.html', session=session, models=models), 200

@app.route('/home')
def home():
    return render_template('home.html', session=session), 200

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html', session=session), 404

# @app.errorhandler(Exception)
# def handle_exception(error) -> tuple:
#     flash('An internal server error has occured.','error')
#     return redirect(url_for('logout')), 500
#     return None, 500


@app.route('/logout')
def logout():
    print('Logging out user.')
    session.pop('username',None)
    session.pop('authenticated',None)
    session.pop('user_id',None)
    return redirect(url_for('login'))

#TODO - consider joining with edit_personal_information (Must be done together with FE editing)
@app.route('/change-email',methods=['GET','POST'])
@check_authentication
def change_email():
    match request.method:
        case 'GET':
            form=forms.ChangeEmailForm()
            return render_template('form.html',dynamic_content='Change email',form=form,session=session)
        case 'POST':
            form=forms.ChangeEmailForm()
            if form.validate_on_submit():
                # TODO - consider removal - old approach - unused
                # query='UPDATE public_users SET e_mail=%s WHERE id=%s'
                # values=(form.e_mail.data,session['user_id'])
                # execute_query(query,values)
                db_api.update_users_table(values_dict={'e_mail': form.e_mail.data}, user_id=session['user_id'])
                flash('Email changed successfully.','success')
                return redirect('/user')
            else:
                return render_template('form.html',dynamic_content='Change email',form=form,session=session)

@app.route('/edit-personal-information',methods=['GET','POST'])
@check_authentication
def edit_personal_information():
    match request.method:
        case 'GET':
            form=forms.EditPersonalInformationForm()
            return render_template('form.html',dynamic_content='Change personal information',form=form,session=session)
        case 'POST':
            form=forms.EditPersonalInformationForm()
            if form.validate_on_submit():
                print('Form validated successfully.')
                for field in form:
                    print(field)
                    if field.data:
                        if field.name == 'csrf_token':
                            continue
                        db_api.update_users_table(values_dict={field.name: field.data}, user_id=session['user_id'])
                        # TODO - consider removal - old approach - unused
                        # query = f'UPDATE public_users SET {field.name}=%s WHERE id=%s'
                        # values = (field.data, session['user_id'])
                        # execute_query(query, values)
                flash('Personal information updated successfully.','success')
                return redirect('/user')
            else:
                return render_template('form.html',dynamic_content='Change personal information',form=form,session=session)

@app.route('/change-password',methods=['GET','POST'])
@check_authentication
def change_password():
    match request.method:
        case 'GET':
            form=forms.ChangePasswordForm()
            return render_template('form.html',dynamic_content='Change password',form=form,session=session)
        case 'POST':
            form=forms.ChangePasswordForm()
            if form.validate_on_submit():                
                # check if the old password is correct
                authenticated = is_password_correct(password=form.old_password.data, user_id=session['user_id'])
                if authenticated:
                    new_password_hash=generate_password_hash(form.new_password.data)
                    db_api.update_users_table(values_dict={'pwd': new_password_hash}, user_id=session['user_id'])
                    flash('Password changed successfully.','success')
                    return redirect('/user'), 302
                else:
                    flash('The old password is incorrect.','error')
                    return render_template('form.html',dynamic_content='Change password',form=form,session=session), 200
            else:
                return render_template('form.html',dynamic_content='Change password',form=form,session=session), 200

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

@app.route('/login',methods=['GET','POST'])
def login():
    logout()
    match request.method:
        case 'GET':
            form=forms.LoginForm()
            return render_template('form.html',dynamic_content='Login ',form=form, session=session)
        case 'POST':
            form=forms.LoginForm()
            if form.validate_on_submit():
                user_id = db_api.get_user_id(username=form.usernameXe_mail.data, email=form.usernameXe_mail.data)
                authenticated = is_password_correct(password=form.password.data, user_id=user_id)
                if authenticated:
                    session['authenticated'] = True
                    session['user_id'] = user_id
                    # TODO - consider removal - old approach - unused
                    # TODO - currently the ts is created dynamically when needed, so this may be redundant
                    # create a new user temporary storage for the user
                    # if session['user_id'] not in ts:
                    #     ts[session['user_id']] = UserTemporaryStorage()                
                    return redirect('/'), 302   
                else:
                    flash('Invalid username or password.','error')
                    return render_template('form.html',dynamic_content='Login ',form=form,session=session)
            else:
                # form validation failed - user is notified by flash messages in the form
                return render_template('form.html',dynamic_content='Login ',form=form,session=session)

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
    page_limit=int(request.args.get('page_limit',10))
    page=int(request.args.get('page',1))
    start_sub_id=request.args.get('start_id',None)
    sort_by=request.args.get('sort_by','time_stamp,id')
    
    records=[('id','time_stamp','current_state')]
    sort_by = sort_by.split(',')  
    sort_by = [x for x in sort_by if x in records[0]]
    
    sort_columns=[ records[0].index(x) for x in sort_by]

    columnames=['id','date','state','actions']
    actions=['Edit','Cancel']
    records.append(execute_query("SELECT id, time_stamp, current_state FROM experiments where user_id=%s AND current_state!='finished' ",(session['user_id'],)))
    data = records[1]

    # Data sorting and slicing
    current_state_order={'finished':0,'current_experiment': 1, 'started':2,'prepared':3,'processing':4,'pending':5}
    reversed_current_state_order={v:k for k,v in current_state_order.items()}
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
    return render_template('queue.html',records=records,session=session,dynamic_content='Experiment Queue',columnames=columnames, actions = actions)

@app.route('/experiments',methods=['GET','POST'])
@check_authentication
def experiments():
    sort_order=request.args.get('sort_order','desc')
    page_limit=int(request.args.get('page_limit',10))
    start_sub_id=request.args.get('start_id',None)
    page=int(request.args.get('page',1))
    sort_by=request.args.get('sort_by','time_stamp,id,expert_guess,asphalt_ratio')
    
    records=[('id','time_stamp','expert_guess', 'asphalt_ratio')]
    sort_by = sort_by.split(',')  
    sort_by = [x for x in sort_by if x in records[0]]
    sort_columns=[ records[0].index(x) for x in sort_by]
    records.append(execute_query("SELECT id, time_stamp, expert_guess, asphalt_ratio FROM experiments where user_id=%s AND current_state='finished' ",(session['user_id'],)))
    
    # data sorting and slicing
    data = records[1]   
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
    records[1] = data
    return render_template('experiments.html',records=records,session=session,dynamic_content='Experiment Records')

@app.route('/user',methods=['GET'])
@check_authentication
def user():
    # user_id = session['user_id']
    # if user_id!=session['user_id']:
    #     flash('You do not have permission to access this page.','error')
    #     return redirect('/'), 302
    # query = 'SELECT first_name, last_name, username, e_mail, company FROM public_users WHERE id=%s'
    # user_data = execute_query(query, (user_id,))
    user_data_dict = db_api.get_user_info_by_id(user_id=session['user_id'])
    return render_template('user.html',session=session,dynamic_content=user_data_dict)



@app.route('/register',methods=['GET','POST'])
def register():
    logout()
    match request.method:
        case 'GET':
            form=forms.RegistrationFormUser()
            return render_template('form.html',dynamic_content='Register new user',form=form,session=session)
        case 'POST':
            form=forms.RegistrationFormUser()
            if form.validate_on_submit():
                print('Form validated successfully.')
                # form.password.data=ws.generate_password_hash(form.password.data,method=os.environ['HASH_METHOD'],salt_length=int(os.environ['SALT_LENGTH']))
                form.password.data=generate_password_hash(form.password.data)
                print('1')
                company_id=db_api.get_company_id_by_key(form.company_key.data)
                print('2')
                user_dict = {
                    'username': form.username.data,
                    'e_mail': form.e_mail.data,
                    'first_name': form.first_name.data,
                    'last_name': form.last_name.data,
                    'company': company_id,
                    'pwd': form.password.data
                }
                print('3')
                result = db_api.save_new_user_db(values=user_dict)
                print('3')
                if result is None:
                    flash(message='Registration successful. Please log in.',category='success')
                    return redirect(url_for('login')), 302
                else:
                    flash(message=f'Database error: {result}',category='error')
                    return render_template('form.html',dynamic_content='Register new user',form=form,session=session), 500
            else:
                # flash(message='Form validation failed. Please check your input.',category='error')
                return render_template('form.html',dynamic_content='Register new user',form=form,session=session)


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
def update_specific_value(value_name):
    # ts[session['user_id']].values.__dict__[value_name] = value
    # setattr(ts[session['user_id']], value_name, value)
    value = request.form.get(value_name)
    storage.from_dict({value_name: value})
    response = save_specific_value(value_name)
    return response    
   
@app.route('/save_value/<string:value_name>',methods=['POST','GET'])
def save_specific_value(value_name):
    try:
        value_name = value_name.lower()
        # value = ts[session['user_id']].values.__dict__[value_name]
        value = getattr(ts[session['user_id']], value_name, None)
        query = f'UPDATE experiments SET {value_name}=%s, asphalt_ratio=%s, img_mask_asphalt=%s WHERE id=%s'
        values = (value,
                #   evaluate_asphalt(),
                  storage.get_asphalt_ratio(),
                #   ts[session['user_id']].asphalt_mask.copy().tobytes(),
                  ts[session['user_id']].experiment_id)
        execute_query(query, values)
        return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return json.dumps({'status': 'error'}), 200, {'Content-Type': 'application/json'}

# TODO: CONSIDER REMOVAL - REPLACED BY storage.get_asphalt_ratio()
@deprecated("Use storage.get_asphalt_ratio() instead.")
def evaluate_asphalt():
    non_bg_pixels = np.sum(return_foreground_mask())
    asphalt_pixels = np.sum(ts[session['user_id']].asphalt_mask + ts[session['user_id']].asphalt_mask_manual_corrections) 
    ic(return_asphalt_mask())
    print('Asphalt pixels:', asphalt_pixels)
    print('Non bg pixels:', non_bg_pixels)
    return asphalt_pixels / non_bg_pixels

@app.route('/evaluate-asphalt',methods=['POST'])
@check_authentication
def evaluate_asphalt_caller():
    # evaluation = evaluate_asphalt()
    # inference

    # get the result
    evaluation = storage.get_asphalt_ratio()
    save_experiment(state='finished')
    return json.dumps({'evaluation': evaluation}), 200, {'Content-Type': 'application/json'}

# TODO: CORRECT THE METHOD - should be DELETE
# @app.route('/delete-experiment/<int:id>',methods=['DLELERTE'])
@app.route('/delete-experiment/<int:id>',methods=['GET', 'POST'])
@check_authentication
@check_data_ownership
def delete_experiment(id):
    experiment_state = execute_query('SELECT current_state FROM experiments WHERE id=%s', (id,))[0][0]
    try:
        if experiment_state == 'finished':
            query = 'UPDATE experiments.fake_deleted=true WHERE id=%s'
            execute_query(query, (id,))
        else:
            query = 'DELETE FROM experiments WHERE id=%s'
            execute_query(query, (id,))
        status = 'success'
    except:
        status = 'error'
    return json.dumps({'status': status}), 200, {'Content-Type': 'application/json'}

@app.route('/deactivate-current-experiment',methods=['GET', 'POST'])
@check_authentication
def deactivate_current_experiment():
    return deactivate_experiment(None)

@app.route('/deactivate-experiment/<int:id>',methods=['GET', 'POST'])
@check_authentication
@check_data_ownership
def deactivate_experiment_caller(id):
    return deactivate_experiment(id)

def deactivate_experiment(id):
    if id is None:
        id = ts[session['user_id']].experiment_id
        if id is None:
            flash('No active experiment found.','error')
            return redirect('/queue')
    print('Deactivating experiment.', id)
    query = 'UPDATE experiments SET active=%s WHERE experiment_id=%s'
    values = (False, id)
    execute_query(query, values)
    ts[session['user_id']].experiment_id = None
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
            flash('No active experiment found.','error')
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
    query = 'UPDATE experiments SET active=%s WHERE experiment_id=%s'
    values = (True, id)
    execute_query(query, values)
    ts [session['user_id']].experiment_id = id    
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

# TODO: consider removal - of 'POST' method - unused
# @app.route('/load-experiment/<int:id>',methods=['GET', 'POST'])
@app.route('/load-experiment/<int:id>',methods=['GET'])
@check_authentication
def load_experiment(id):
    try:        
        if id is None:
            id = ts[session['user_id']].experiment_id
            if id is None:
                flash('NO ID No active experiment found.','error')
                return redirect('/queue')          

        # response = load_experiment_from_db(id)
        response = db_api.load_experiment_from_db(id)
        if type(response) == dict:
            storage.from_dict(response)
        else:
            if not response:
                flash('The requested experiment does not exist.','error')
                return redirect('/queue')
        
        dict_response = {'status': 'success'}
        dict_enrich = storage.to_dict()
        dict_response.update(dict_enrich)
        print(dict_response)
        return dict_to_json(dict_response), 200, {'Content-Type': 'application/json'}

    #     print('Experiment loaded.')
    #     redirect('/')
    except:
        flash('ERR No active experiment found.','error')
        redirect('/')
        return json.dumps({'status': 'error'}), 200, {'Content-Type': 'application/json'}
    # return json.dumps(json_response), 200, {'Content-Type': 'application/json'}      

# export the images folder
@app.route('/images/<path:filename>')
def download_file(filename):
    return send_from_directory('images', filename, as_attachment=True)

# manual corrections
@app.route('/manual-corrections',methods=['GET'])
@check_authentication
def manual_corrections():
    return render_template('manual_corrections.html')

@app.route('/is-experiment-active',methods=['GET'])
def is_active():
    print('Checking if experiment is active.')
    try:
        if 'user_id' in session:
            print('2 Checking if experiment is active.')
            ts[session['user_id']].experiment_id = return_active_experiment_id(session['user_id'])
            print(ts[session['user_id']].experiment_id)
            if ts[session['user_id']].experiment_id is not None:
                print('Checking if experiment is active.')
                return json.dumps({'active': True, 'experimentId': ts[session['user_id']].experiment_id}), 200, {'Content-Type': 'application/json'}
    except:
        pass    
    return json.dumps({'status': False}), 200, {'Content-Type': 'application/json'}

@app.route('/save',methods=['POST'])
@check_authentication
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
    # try:        
        if storage.experiment_id is None:
            print('Inserting new record.')
            ts_dict = storage.to_dict(for_save=True)
            ts_dict['current_state'] = state
            ts_dict.pop('experiment_id', None)  # ensure that the experiment_id is not in the dict
            storage.experiment_id = db_api.insert_experiment_to_db(values_dict=ts_dict)
            activate_experiment(storage.experiment_id)
            print('New experiment ID:', storage.experiment_id)
            # storage.from_dict(ts_dict)  # to ensure consistency
        else:
            print('Updating record.')
            ts_dict = storage.to_dict(for_save=True)
            db_api.update_experiment_in_db(values_dict=ts_dict)
            # print('state', state)
            # print(storage.experiment_id)
            # query = """ 
            # UPDATE experiments SET img_width = %s, 
            # img_height = %s, 
            # img_mask_asphalt=%s, 
            # img_mask_aggregate=%s,
            # expert_guess=%s, 
            # info=%s, 
            # current_state=%s, 
            # asphalt_ratio=%s,
            # entropy_min_threshold=%s, 
            # entropy_max_threshold=%s, 
            # intensity_min_threshold_0=%s, 
            # intensity_max_threshold_0=%s, 
            # intensity_min_threshold_1=%s, 
            # intensity_max_threshold_1=%s,
            # blur=%s, 
            # img_mask_asphalt_manual_correction = %s, 
            # img_mask_aggregate_manual_correction=%s
            # WHERE id=%s"""
            # values = (ts[session['user_id']].color_original.shape[1],
            #           ts[session['user_id']].color_original.shape[0],
            #           ts[session['user_id']].asphalt_mask.tobytes(),
            #           ts[session['user_id']].aggregate_mask.tobytes(),
            #           ts[session['user_id']].values.expert_guess,
            #           ts[session['user_id']].values.info,
            #           state,
            #           evaluate_asphalt(),
            #           ts[session['user_id']].values.entropy_min_threshold,
            #           ts[session['user_id']].values.entropy_max_threshold,
            #           ts[session['user_id']].values.intensity_min_threshold_0,
            #           ts[session['user_id']].values.intensity_max_threshold_0,
            #           ts[session['user_id']].values.intensity_min_threshold_1,
            #           ts[session['user_id']].values.intensity_max_threshold_1,
            #           ts[session['user_id']].values.blur,
            #           ts[session['user_id']].asphalt_mask_manual_corrections.tobytes(),
            #           ts[session['user_id']].aggregate_mask_manual_corrections.tobytes(),
            #           ts[session['user_id']].experiment_id)
            # execute_query(query, values)
        
        if state.lower() == 'finished':
            # delete temporary storage and create a new one
            print('Experiment finished.')
            ts.pop(session['user_id'])
            # storage = UserTemporaryStorage() # TODO: check if this is needed >>> should be created dynamically when needed by lambda function in storage definition
        return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}
    # except Exception as e:
    #     return json.dumps({'status': 'error', 'message': str(e)}), 500, {'Content-Type': 'application/json'}


@app.route('/backup-storage',methods=['POST', 'GET'])
@check_authentication
def backup_temporal_storage():
    # This function bacups the temporary storage of the user and creates a new one
    # it should be called when the user wants to upload new images without harming the current experiment
    ts[str(session['user_id'])+"&backup"] = ts[session['user_id']]
    ts[session['user_id']] = UserTemporaryStorage()
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

@app.route('/restore-storage',methods=['POST', 'GET'])
@check_authentication
def restore_temporal_storage():
    # This function restores the temporary storage of the user from the backup
    # it should be called when the user wants to restore the previous experiment
    ts[session['user_id']] = ts[str(session['user_id'])+"&backup"]
    ts.pop(str(session['user_id'])+"&backup")
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
    if scale_factor is None:
        # compute scale factor based on the image size such that the maximum dimension is 1200 pixels
        scale_factor = 1.0
        max_dimension = max(image.shape[:2])
        if max_dimension > 1200:
            scale_factor = max_dimension / 1200.0
    elif scale_factor <= 0:
        raise ValueError("Scale factor must be greater than 0.")

    new_size = (int(image.shape[1] / scale_factor), int(image.shape[0] / scale_factor))
    downscaled_image = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
    return downscaled_image

def polish_input_image_file(file) -> np.ndarray: 
    """
    This function processes the input image file and returns the image as a numpy array.
    It handles HEIC files by converting them to PNG format and ensures the image has no alpha channel.
    """

    print('Polishing input image file.')
    image = Image.open(file.stream)
    print('1')

    if file.filename.split('.')[-1].upper() == 'HEIC':
        unique_query = str(request.args.get('nocache')) + '_' + str(session['user_id'])
        path = f'temp/temp_{unique_query}.png'
        image.save(path)
        image = Image.open(path)

        np_image = np.concatenate((np.array(image), np.ones((image.size[1], image.size[0], 1), dtype=np.uint8)*255), axis=2)
    else:
        np_image = np.array(image)

    print('1.5')
    # if the image is BW image, convert it to RGB
    if len(np_image.shape) == 2:
        np_image = np.stack((np_image,)*3, axis=-1)

    print('2')
    if file.filename.split('.')[-1].upper() == 'HEIC':
        # delete the temporary file
        os.remove(path)
    
    print('3')
    # if the image has more than 4 channels, convert it to RGB
    if np_image.shape[2] > 3:
        np_image = np_image[:, :, :3]
    print('4')

    # downscale the image if it is larger than 1200 pixels in any dimension
    np_image = downscale_image(np_image, scale_factor=None)
    print('5')

    return np_image.astype(np.uint8)


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
    })

    # save the data to database
    save_experiment(state='started')
    # inference


    response_dict = {
        'status': 'success',
        'color': storage.color,
        'gray': grayscale_image(storage.color),  # convert to list for JSON serialization
    }
    response_json = dict_to_json(response_dict)


    return response_json, 200, {'Content-Type': 'application/json'}

def postprocess_model_prediction(prediction: torch.Tensor):
    """
    Postprocess the model prediction to save separated masks.

    
    Parameters:
    prediction (torch.Tensor): 
        expected to be a tensor with shape (batch_size, num_classes, height, width).
        containig the probabilities for each class.
        the class are expected
        - 0 is asphalt, 
        - 1 is aggregate,
        - 2 is background

    """
    prediction = prediction.squeeze(0).cpu().numpy()  # Remove batch dimension and convert to numpy array
    boolean_prediction = np.argmax(prediction, axis=0)  # Get the class with the highest probability

    asphalt_mask = boolean_prediction == 0
    aggregate_mask = boolean_prediction == 1
    background_mask = boolean_prediction == 2

    return asphalt_mask, aggregate_mask, background_mask

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


    if storage.inference_model is None:
        return json.dumps({'status': 'error', 'message': 'Model name is required.'}), 400, {'Content-Type': 'application/json'}

    input_data = torch.from_numpy(storage.color).unsqueeze(0).float()  # Add batch channel dimension
    input_data = input_data.permute(0, 3, 1, 2)  # Change to torch (batch_size, channels, height, width)
    
    print("input_data.shape")
    print(input_data.shape)

    model_prediction = inference(model_name=storage.inference_model,
                                 input_data=input_data,
                                 session_id=session['user_id'])
    
    # get model prediction and save it to the sessions
    asphalt_mask, aggregate_mask, background_mask = postprocess_model_prediction(model_prediction)

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
@check_authentication
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

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/node_modules/<path:path>')
def send_node_modules(path):
    return send_from_directory('node_modules', path)

if __name__ == "__main__":
    debug = True
    if debug:
        app.secret_key='test_secret_key'
    app.run(debug=debug)

