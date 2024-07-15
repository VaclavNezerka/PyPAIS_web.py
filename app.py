# Packages
from flask import Flask, render_template, request, send_from_directory, flash, redirect, session, url_for, g, make_response, send_file
# from flask_login import login_manager, UserMixin, login_required,
import werkzeug.security as ws
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
import json 
import base64



# Apps
import forms 

app = Flask(__name__)

# app.permanent_session_lifetime=timedelta(days=5)

def generate_rnd_string(length):
    possible_chars=string.ascii_letters+string.digits+string.punctuation
    return ''.join(secrets.choice(possible_chars) for _ in range(int(length))) 

app.secret_key=generate_rnd_string(os.environ['SECRET_KEY_LENGTH'])

ts = {} # temporary storages for the users... ts[user_id] = UserTemporaryStorage()

class UserValues:
    def __init__(self):
        self.blur = 0
        self.threshold = 128
        self.entropy_threshold = 128
        self.info = 'No info available'

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
    def __init__(self):
        self.username = None
        self.user_id = None
        # values
        self.values = UserValues()
        # info
        self.experiment_id = None
        self.expert_guess = 0.        
        # images
        self.color_original = None
        self.gray_original = None
        self.color = None
        self.gray = None        
        # masks
        self.aggregate_mask = None # [auto - rembg] all the pixels that are not background
        self.asphalt_mask = None # [auto - sliders] all the pixels that are asphalt and not background
        self.aggregate_mask_manual_adjustments = None # [manual] all the pixels that are not background or are background (defined by the user)
        self.asphalt_mask_manual_adjustments = None # [manual] all the pixels that are asphalt and not background (defined by the user)        

# @app.before_request        
def check_authentication(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # try:
        if 'authenticated' in session and session['authenticated']:
            return func(*args, **kwargs)
        else:
            flash('You must be logged in to access this page.','error')
            return redirect(url_for('login'))
        # except:
        #     return redirect(url_for('login'))
    return wrapper

@app.route('/')
@check_authentication
def index():
    return render_template('index.html', session=session), 200

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html', session=session), 404

@app.errorhandler(500)
def internal_server_error(error):
    flash('An internal server error has occured.','error')
    return redirect(url_for('index'))

"""
"""

@app.route('/logout')
def logout():
    session.pop('username',None)
    session.pop('authenticated',None)
    return redirect(url_for('login'))

@app.route('/login',methods=['GET','POST'])
def login():
    logout()
    if request.method=='GET':
        form=forms.LoginForm()
        return render_template('form.html',dynamic_content='Login ',form=form, session=session)
    elif request.method=='POST':
        if 'username' in session:   
            # TODO - do not allow user to go to the login page if they are authenticated/logged in 
            return redirect('/')
        form=forms.LoginForm()
        if form.validate_on_submit():
            query='SELECT pwd FROM public_users WHERE username=%s OR e_mail=%s'
            values=(form.usernameXe_mail.data,form.usernameXe_mail.data)
            pwd_hash=execute_query(query=query,values=values)[0][0]
            authenticated=ws.check_password_hash(pwhash=pwd_hash,password=form.password.data)
            if authenticated:
                query='SELECT e_mail FROM public_users WHERE username=%s OR e_mail=%s'
                mail=execute_query(query=query,values=values)[0][0]
                session['authenticated']=True
                session['username']=mail
                session['user_id']=execute_query('SELECT id FROM public_users WHERE e_mail=%s',(mail,))[0][0]
                
                # create a new user temporary storage for the user
                if session['user_id'] not in ts:
                    ts[session['user_id']] = UserTemporaryStorage()
                
                return redirect('/')   
            else:
                flash('The password or username/email is incorrect.')
                return render_template('form.html',dynamic_content='Login ',form=form,session=session)
        else:
            return render_template('form.html',dynamic_content='Login ',form=form,session=session)
    else:
        return redirect('/')


@app.route('/queue',methods=['GET','POST'])
@check_authentication
def queue():
    records=[('id','time_stamp','current_state')]
    columnames=['id','date','state','actions']
    actions=['Edit','Cancel']
    records.append(execute_query("SELECT id, time_stamp, current_state FROM experiments where added_by_user=%s AND current_state!='finished' ",(session['user_id'],)))
    return render_template('queue.html',records=records,session=session,dynamic_content='Experiment Queue',columnames=columnames, actions = actions)

@app.route('/experiments',methods=['GET','POST'])
@check_authentication
def experiments():
    records=[('id','time_stamp','expert_guess', 'asphalt_ratio')]
    records.append(execute_query("SELECT id, time_stamp, expert_guess, asphalt_ratio FROM experiments where added_by_user=%s AND current_state='finished' ",(session['user_id'],)))
    return render_template('experiments.html',records=records,session=session,dynamic_content='Experiments')

@app.route('/register',methods=['GET','POST'])
def register():
    logout()
    if request.method=='GET':
        form=forms.RegistrationFormUser()
        return render_template('form.html',dynamic_content='Register new user',form=form,session=session)
    elif request.method=='POST':
        form=forms.RegistrationFormUser()
        if form.validate_on_submit():
            form.password.data=ws.generate_password_hash(form.password.data,method=os.environ['HASH_METHOD'],salt_length=int(os.environ['SALT_LENGTH']))
            try:
                form.company_id.data=int(form.company_id.data)
                save_new_user_db(values=[field.data for field in form][:6])
                flash(message='Registration was successful.',category='success')
            except:
                flash(message='The data was not provided in the requested format.',category='error')
                return render_template('form.html',dynamic_content='Register new user',form=form,session=session)    
            return render_template('form.html',dynamic_content='Register new user',form=form,session=session)    
        else:
            return render_template('form.html',dynamic_content='Register new user',form=form,session=session)
    else:
        return redirect('/')

@app.route('/grayscale-data', methods=['POST'])
def get_grayscale_data():
    file = request.files['file']
    if file:
        image = Image.open(file.stream)        
        gray_image = image.convert('L')
        np_gray = np.array(gray_image)
        ts[session['user_id']].gray = np_gray
        ts[session['user_id']].gray_original = np_gray
        
        # cv2.imwrite('temp/gray_temp.jpg', np_gray)
        print('Image loaded.')

        img_byte_arr = io.BytesIO()
        gray_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)  # Rewind the buffer to the beginning

        img_byte_arr = io.BytesIO()
        Image.fromarray(np_gray).save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        return img_byte_arr, 200, {'Content-Type': 'image/png'}

@app.route('/rembg',methods=['GET'])
@check_authentication
def rembg():
    return render_template('rembg.html')


def evaluate_asphalt():
    non_bg_pixels = np.sum(ts[session['user_id']].aggregate_mask)
    asphalt_pixels = np.sum(ts[session['user_id']].asphalt_mask) 
    print('Asphalt pixels:', asphalt_pixels)
    print('Non-bg pixels:', non_bg_pixels)
    print('Asphalt ratio:', asphalt_pixels / non_bg_pixels)
    return asphalt_pixels / non_bg_pixels

@app.route('/evaluate-asphalt',methods=['POST'])
def evaluate_asphalt_caller():
    evaluation = evaluate_asphalt()
    save_asphalt_record(state='finished')
    print('Asphalt evaluated.')
    print(evaluation)
    return json.dumps({'evaluation': evaluation}), 200, {'Content-Type': 'application/json'}

@app.route('/save',methods=['POST'])
def save_asphalt_record(**kwargs):
    if 'state' in kwargs.keys():
        state = kwargs['state']
    else:
        state = 'started'
    print('Saving record.')
    print('state:', state)  
        
    if ts[session['user_id']].experiment_id is None:
        print('Inserting new record.')
        query = 'INSERT INTO experiments (added_by_user, img, img_mask_asphalt, img_mask_aggregate, expert_guess, info, current_state, asphalt_ratio) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id'
        values = (session['user_id'], 
                  ts[session['user_id']].color_original.tobytes(),
                  ts[session['user_id']].asphalt_mask.tobytes(),
                  ts[session['user_id']].aggregate_mask.tobytes(),
                  ts[session['user_id']].expert_guess,
                  ts[session['user_id']].values.info,
                  state,
                  evaluate_asphalt())
        ts[session['user_id']].experiment_id = execute_query(query, values)[0][0]
        print(ts[session['user_id']].experiment_id)
    else:
        print('Updating record.')
        query = 'UPDATE experiments SET img=%s, img_mask_asphalt=%s, img_mask_aggregate=%s, expert_guess=%s, info=%s, current_state=%s, asphalt_ratio=%s WHERE id=%s'
        values = (ts[session['user_id']].color_original.tobytes(),
                    ts[session['user_id']].asphalt_mask.tobytes(),
                    ts[session['user_id']].aggregate_mask.tobytes(),
                    ts[session['user_id']].expert_guess,
                    ts[session['user_id']].values.info,
                    state,
                    evaluate_asphalt(),
                    ts[session['user_id']].experiment_id)
        execute_query(query, values)
        
    if state == 'finished':
        # delete temporary storage and create a new one
        print('Experiment finished.')
        ts.pop(session['user_id'])
        ts[session['user_id']] = UserTemporaryStorage()
            
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}




@app.route('/remove-background',methods=['POST'])
def remove_picture_background():
    # this function returns a suggested mask, i.e. boolean matrix  
    # denoting wether a pixel should (T) or should not (F) be taken into
    # account during the other computations
    # adjust the mask by setting a manual threshold 
    
    
    # read the necessary properties
    file = request.files['file']
    # check wether the file is .heic and if so, convert it to .png
    if file.filename[-len('.HEIC'):].upper() == '.HEIC':
        image = Image.open(file.stream)
        unique_query = str(request.args.get('nocache')) + '_' + str(session['user_id'])
        path = f'temp/temp_{unique_query}.png'
        image.save(path)
        image = Image.open(path)
    else:
        image = Image.open(file.stream)
    # image = request.form.get('image')
    # image=np.array(request.form.get('image'),dtype=np.int8)
    
    
    threshold=128 #consider changing this to a value from the form that user can set # threshold=request.form.get('threshold')

    # deepcopy the image
    ts[session['user_id']].color_original = np.array(image)

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
    ts[session['user_id']].aggregate_mask=np.array(mask, dtype=bool)
    ts[session['user_id']].values.threshold=threshold
    ts[session['user_id']].color=image
 
    
    # return the mask
    print('Background removed')
    if file.filename[-len('.HEIC'):].upper() == '.HEIC':
        # delete the temporary file
        os.remove(path)
    return encode_to_png(image), 200, {'Content-Type': 'image/png'}


@app.route('/entropy', methods=['POST'])
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
    print('ci shape',ts[session['user_id']].color.shape)
    print('mask shape',ts[session['user_id']].aggregate_mask.shape)
    
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
def apply_mask():
    # Assuming the image's ID or a unique identifier is sent as part of the form data for key lookup
    image_id = request.form.get('imageId')
    min_threshold = int(request.form.get('minThreshold', 0))
    max_threshold = int(request.form.get('maxThreshold', 255))
    entropy_min_threshold = int(request.form.get('entropyMinThreshold', 0))
    entropy_max_threshold = int(request.form.get('entropyMaxThreshold', 255))
    
    print('Mask applied')
    # np_gray = cv2.imread('temp/gray_temp.jpg', cv2.IMREAD_GRAYSCALE)
    # np_entropy = cv2.imread('temp/entropy_temp.jpg', cv2.IMREAD_GRAYSCALE)
    np_gray = ts[session['user_id']].gray
    np_entropy = ts[session['user_id']].entropy
    if image_id == 'gray':
        overlay_image = apply_red_overlay(np_gray, np_gray, np_entropy, min_threshold, max_threshold,
                                          entropy_min_threshold, entropy_max_threshold)
    else:
        overlay_image = apply_red_overlay(np_entropy, np_gray, np_entropy, min_threshold, max_threshold,
                                          entropy_min_threshold, entropy_max_threshold)

    img_byte_arr=encode_to_png(overlay_image) #should be equivalent to the 3 rows bellow
    entropy_byte_arr = encode_to_png(np_entropy)    
    # stringify the image
    img_byte_arr = base64.b64encode(img_byte_arr).decode('utf-8')
    entropy_byte_arr = base64.b64encode(entropy_byte_arr).decode('utf-8')
    return json.dumps({'overlay': img_byte_arr, 'entropy': entropy_byte_arr}), 200, {'Content-Type': 'application/json'}
    # img_byte_arr = io.BytesIO()
    # overlay_image.save(img_byte_arr, format='PNG')
    # img_byte_arr = img_byte_arr.getvalue()
    # return img_byte_arr, 200, {'Content-Type': 'image/png'}


def apply_red_overlay(masked_img, intensity_img, entropy_img, min_threshold, max_threshold, entropy_min_threshold,
                      entropy_max_threshold):
    intensity_mask = (intensity_img >= min_threshold) & (intensity_img <= max_threshold)
    entropy_mask = (entropy_img >= entropy_min_threshold) & (entropy_img <= entropy_max_threshold)
    # combined_mask = intensity_mask & entropy_mask 

    combined_mask = intensity_mask & entropy_mask
    combined_mask *= ts[session['user_id']].aggregate_mask.astype(bool)  
   
    # Create an RGBA version of the processed data
    rgba_image = np.dstack([masked_img] * 3 + [np.full(masked_img.shape, 255, dtype=np.uint8)])

    # Prepare the red overlay
    red_overlay = np.zeros_like(rgba_image, dtype=np.uint8)
    red_overlay[..., 0] = 255  # Red channel full intensity
    red_overlay[combined_mask] = [255, 0, 0, 128]  # Semi-transparent red overlay where mask is True
    # Combine the original image with the overlay
    # overlay_image = Image.alpha_composite(Image.fromarray(rgba_image), Image.fromarray(red_overlay))
    ts[session['user_id']].asphalt_mask = (red_overlay[:,:,-1] == 128).astype(bool)
    print('Overlay applied.')

    return red_overlay

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == "__main__":
    app.run(debug=True)
