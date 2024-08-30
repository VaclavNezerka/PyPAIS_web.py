# Packages
from flask import Flask, render_template, request, send_from_directory, flash, redirect, session, url_for, g, make_response, send_file
from flask_mail import Mail, Message
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

# configuration of the mail server
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@example.com'
app.config['MAIL_PASSWORD'] = 'your-email-password'
app.config['MAIL_DEFAULT_SENDER'] = ('Your Name', 'your-email@example.com')


def generate_rnd_string(length):
    possible_chars=string.ascii_letters+string.digits+string.punctuation
    return ''.join(secrets.choice(possible_chars) for _ in range(int(length))) 

app.secret_key=generate_rnd_string(os.environ['SECRET_KEY_LENGTH'])

ts = {} # temporary storages for the users... ts[user_id] = UserTemporaryStorage()

class UserValues:
    def __init__(self):
        self.threshold = 128
        self.entropy_threshold = 128
        self.info = 'No info available'
        
        # values currently accessible by the users
        self.blur = 0
        self.intensity_min_threshold_0 = None 
        self.intensity_max_threshold_0 = None 
        self.intensity_min_threshold_1 = None 
        self.intensity_max_threshold_1 = None 
        self.entropy_min_threshold = None 
        self.entropy_max_threshold = None 
        self.expert_guess = None # 0. old value        
    

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

def check_data_ownership(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            query = 'SELECT added_by_user FROM experiments WHERE id=%s'
            user_id = execute_query(query, (kwargs['id'],))[0][0]   
            if user_id == session['user_id']:
                return func(id=kwargs['id'])
            else:
                flash('You do not have permission to access this data.','error')
                return redirect('/')
        except:
            flash('Hmm You do not have permission to access this data.','error')
            return redirect('/')
    return wrapper

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
    return redirect(url_for('/logout'))




"""
"""

@app.route('/logout')
def logout():
    session.pop('username',None)
    session.pop('authenticated',None)
    return redirect(url_for('login'))

@app.route('/change-email',methods=['GET','POST'])
@check_authentication
def change_email():
    if request.method=='GET':
        form=forms.ChangeEmailForm()
        return render_template('form.html',dynamic_content='Change email',form=form,session=session)
    elif request.method=='POST':
        form=forms.ChangeEmailForm()
        if form.validate_on_submit():
            query='UPDATE public_users SET e_mail=%s WHERE id=%s'
            values=(form.e_mail.data,session['user_id'])
            execute_query(query,values)
            flash('Email changed successfully.','success')
            return redirect('/user')
        else:
            return render_template('form.html',dynamic_content='Change email',form=form,session=session)
    else:
        return redirect('/')

@app.route('/edit-personal-information',methods=['GET','POST'])
@check_authentication
def edit_personal_information():
    if request.method=='GET':
        form=forms.EditPersonalInformationForm()
        return render_template('form.html',dynamic_content='Change personal information',form=form,session=session)
    elif request.method=='POST':
        form=forms.EditPersonalInformationForm()
        if form.validate_on_submit():
            for field in form:
                if field.data:
                    print(field)
                    print(field.name)
                    if field.name == 'csrf_token':
                        continue
                    query = f'UPDATE public_users SET {field.name}=%s WHERE id=%s'
                    values = (field.data, session['user_id'])
                    execute_query(query, values)
            flash('Personal information changed successfully.','success')
            return redirect('/user')
        else:
            return render_template('form.html',dynamic_content='Change personal info',form=form,session=session)
    else:
        return redirect('/')

@app.route('/change-password',methods=['GET','POST'])
@check_authentication
def change_password():
    if request.method=='GET':
        form=forms.ChangePasswordForm()
        return render_template('form.html',dynamic_content='Change password',form=form,session=session)
    elif request.method=='POST':
        form=forms.ChangePasswordForm()
        if form.validate_on_submit():
            query='SELECT pwd FROM public_users WHERE id=%s'
            values=(session['user_id'],)
            pwd_hash=execute_query(query=query,values=values)[0][0]
            authenticated=ws.check_password_hash(pwhash=pwd_hash,password=form.old_password.data)
            if authenticated:
                query='UPDATE public_users SET pwd=%s WHERE id=%s'
                values=(ws.generate_password_hash(form.new_password.data,method=os.environ['HASH_METHOD'],salt_length=int(os.environ['SALT_LENGTH']),),session['user_id'])
                execute_query(query=query,values=values)
                flash('Password changed successfully.','success')
                return redirect('/user')
            else:
                flash('The old password is incorrect.','error')
                return render_template('form.html',dynamic_content='Change password',form=form,session=session)
        else:
            return render_template('form.html',dynamic_content='Change password',form=form,session=session)
    else:
        return redirect('/')

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

def sort_records(records,sort_order,sort_by,page_limit):
    if sort_order=='asc':
        records.sort(key=lambda x: x[sort_by])
    elif sort_order=='desc':
        records.sort(key=lambda x: x[sort_by],reverse=True)
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
    records.append(execute_query("SELECT id, time_stamp, current_state FROM experiments where added_by_user=%s AND current_state!='finished' ",(session['user_id'],)))
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
    records.append(execute_query("SELECT id, time_stamp, expert_guess, asphalt_ratio FROM experiments where added_by_user=%s AND current_state='finished' ",(session['user_id'],)))

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
    return render_template('experiments.html',records=records,session=session,dynamic_content='Experiments')



@app.route('/user',methods=['GET'])
@check_authentication
def user():
    user_id = session['user_id']
    if user_id!=session['user_id']:
        flash('You do not have permission to access this page.','error')
        return redirect('/')
    query = 'SELECT first_name, last_name, username, e_mail, company FROM public_users WHERE id=%s'
    user_data = execute_query(query, (user_id,))
    user_data_dict = {'first_name': user_data[0][0],
                      'last_name': user_data[0][1],
                      'username': user_data[0][2],
                      'e_mail': user_data[0][3],
                      'company': user_data[0][4]}
    return render_template('user.html',session=session,dynamic_content=user_data_dict)

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

@app.route('/update_value/<string:value_name>',methods=['POST'])
@check_authentication
def update_specific_value(value_name):
    value = request.form.get(value_name)
    ts[session['user_id']].values.__dict__[value_name] = value
    response = save_specific_value(value_name)
    print('Value updated.', value_name, value)
    return response    
   
    
def evaluate_asphalt():
    non_bg_pixels = np.sum(ts[session['user_id']].aggregate_mask)
    asphalt_pixels = np.sum(ts[session['user_id']].asphalt_mask) 
    return asphalt_pixels / non_bg_pixels

@app.route('/evaluate-asphalt',methods=['POST'])
@check_authentication
def evaluate_asphalt_caller():
    evaluation = evaluate_asphalt()
    save_asphalt_record(state='finished')
    return json.dumps({'evaluation': evaluation}), 200, {'Content-Type': 'application/json'}


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

@app.route('/deactivate-experiment/<int:id>',methods=['GET', 'POST'])
@check_authentication
@check_data_ownership
def deactivate_experiment_caller(id):
    print('Deactivating experiment.', id)
    return deactivate_experiment(id)

def deactivate_experiment(id):
    if id is None:
        id = ts[session['user_id']].experiment_id
        if id is None:
            flash('No active experiment found.','error')
            return redirect('/queue')
    print('Deactivating experiment.')
    print(id)
    query = 'UPDATE experiments SET active=%s WHERE id=%s'
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
        id = ts[session['user_id']].experiment_id
        if id is None:
            flash('No active experiment found.','error')
            return redirect('/queue')
    # check if the experiment is already active if it is, deactivate it
    query = 'SELECT id FROM experiments WHERE added_by_user=%s AND active=True'
    active_id = execute_query(query, (session['user_id'],))
    print(active_id)
    if active_id:
        for i in active_id:
            print(i[0])
            r=deactivate_experiment(i[0])

    # activate the experiment
    query = 'UPDATE experiments SET active=%s WHERE id=%s'
    values = (True, id)
    execute_query(query, values)
    ts [session['user_id']].experiment_id = id    
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

@app.route('/load-experiment/<int:id>',methods=['GET', 'POST'])
@check_authentication
def load_experiment(id):
    # try:        
        if id is None:
            id = ts[session['user_id']].experiment_id
            if id is None:
                flash('NO ID No active experiment found.','error')
                return redirect('/queue')          

        response = load_experiment_from_db(id)
        image_width = response[0][0]
        image_height = response[0][1]
        print('Image width:', image_width)
        print('Image height:', image_height)
        print(response[0][-3])
        ts[session['user_id']].color_original = np.frombuffer(response[0][2], dtype=np.uint8).reshape(image_height, image_width, 4)
        ts[session['user_id']].asphalt_mask = np.frombuffer(response[0][3], dtype=bool).reshape(image_height, image_width)
        ts[session['user_id']].aggregate_mask = np.frombuffer(response[0][4], dtype=bool).reshape(image_height, image_width)
        print('shapes')
        print(response[0][3].shape)
        print(ts[session['user_id']].aggregate_mask.shape)
        print(ts[session['user_id']].asphalt_mask.shape)
        print(ts[session['user_id']].color_original.shape)
        ts[session['user_id']].values.expert_guess = response[0][5]
        ts[session['user_id']].values.info = response[0][6]
        ts[session['user_id']].values.entropy_min_threshold = response[0][7]
        ts[session['user_id']].values.entropy_max_threshold = response[0][8]
        ts[session['user_id']].values.intensity_min_threshold_0 = response[0][9]
        ts[session['user_id']].values.intensity_max_threshold_0 = response[0][10]
        ts[session['user_id']].values.intensity_min_threshold_1 = response[0][11]
        ts[session['user_id']].values.intensity_max_threshold_1 = response[0][12]
        ts[session['user_id']].values.blur = response[0][13]
        ts[session['user_id']].color = blur_image(ts[session['user_id']].values.blur, ts[session['user_id']].color_original)
        # gray image
        image = Image.fromarray(ts[session['user_id']].color_original)        
        gray_image = image.convert('L')
        ts[session['user_id']].gray_original = np.array(gray_image)        
        ts[session['user_id']].gray = blur_image(ts[session['user_id']].values.blur, ts[session['user_id']].gray_original) 
                
        # encode the images to string
        encoded_gray = encode_to_png(ts[session['user_id']].gray_original)
        encoded_color = encode_to_png(ts[session['user_id']].color_original)
        encoded_no_bg = encode_to_png(ts[session['user_id']].color_original*ts[session['user_id']].aggregate_mask[:,:,None])
        encoded_gray = base64.b64encode(encoded_gray).decode('utf-8')
        encoded_color = base64.b64encode(encoded_color).decode('utf-8')
        encoded_no_bg = base64.b64encode(encoded_no_bg).decode('utf-8')
        # blur the images
        encoded_no_bg_blur = encode_to_png(ts[session['user_id']].color*ts[session['user_id']].aggregate_mask[:,:,None])
        encoded_gray_blur = encode_to_png(ts[session['user_id']].gray)
        encoded_color_blur = encode_to_png(ts[session['user_id']].color)
        encoded_no_bg_blur = base64.b64encode(encoded_no_bg_blur).decode('utf-8')
        encoded_gray_blur = base64.b64encode(encoded_gray_blur).decode('utf-8')
        encoded_color_blur = base64.b64encode(encoded_color_blur).decode('utf-8')
        
        try:
            expert_guess = int(ts[session['user_id']].values.expert_guess*100)
        except:
            expert_guess = 'NaN'
    
        json_response = {'status': 'success',
                        'minThreshold0': ts[session['user_id']].values.intensity_min_threshold_0,
                        'maxThreshold0': ts[session['user_id']].values.intensity_max_threshold_0,
                        'minThreshold1': ts[session['user_id']].values.intensity_min_threshold_1,
                        'maxThreshold1': ts[session['user_id']].values.intensity_max_threshold_1,
                        'entropyMinThreshold': ts[session['user_id']].values.entropy_min_threshold,
                        'entropyMaxThreshold': ts[session['user_id']].values.entropy_max_threshold,
                        'info': ts[session['user_id']].values.info,
                        'blurValue': ts[session['user_id']].values.blur,
                        'expertGuess': expert_guess,
                        'gray': encoded_gray,
                        'color': encoded_color,
                        'nobg': encoded_no_bg,
                        'gray_blur': encoded_gray_blur,
                        'color_blur': encoded_color_blur,
                        'nobg_blur': encoded_no_bg_blur
                        }
        return json.dumps(json_response), 200, {'Content-Type': 'application/json'}      
                        
    #     print('Experiment loaded.')
    #     redirect('/')
    # except:
    #     flash('ERR No active experiment found.','error')
    #     redirect('/')
    #     return json.dumps({'status': 'error'}), 200, {'Content-Type': 'application/json'}
    # return json.dumps(json_response), 200, {'Content-Type': 'application/json'}      

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

@app.route('/save_value/<string:value_name>',methods=['POST','GET'])
def save_specific_value(value_name):
    try:
        value_name = value_name.lower()
        value = ts[session['user_id']].values.__dict__[value_name]
        query = f'UPDATE experiments SET {value_name}=%s, asphalt_ratio=%s, img_mask_asphalt=%s WHERE id=%s'
        values = (value,
                  evaluate_asphalt(),
                  ts[session['user_id']].asphalt_mask.tobytes(),
                  ts[session['user_id']].experiment_id)
        execute_query(query, values)
        return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return json.dumps({'status': 'error'}), 200, {'Content-Type': 'application/json'}

@app.route('/save',methods=['POST'])
def save_asphalt_record(**kwargs):
    if 'state' in kwargs.keys():
        state = kwargs['state']
    else:
        state = request.args.get('state') or request.form.get('state') or 'started'
        # state = 'started'    

    print('Saving record.')
    print(kwargs)
    print(state)
    try:        
        if ts[session['user_id']].experiment_id is None:
            print('Inserting new record.')
            query = 'INSERT INTO experiments (added_by_user, img_width, img_height, img, img_mask_asphalt, img_mask_aggregate, expert_guess, info, current_state, asphalt_ratio, entropy_min_threshold, entropy_max_threshold, intensity_min_threshold_0, intensity_max_threshold_0, intensity_min_threshold_1, intensity_max_threshold_1, blur) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id'
            # print(ts[session['user_id']].color_original.shape)
            # print('shape!!!')
            values = (session['user_id'], 
                    ts[session['user_id']].color_original.shape[1],
                    ts[session['user_id']].color_original.shape[0],
                    ts[session['user_id']].color_original.tobytes(),
                    ts[session['user_id']].asphalt_mask.tobytes(),
                    ts[session['user_id']].aggregate_mask.tobytes(),
                    ts[session['user_id']].values.expert_guess,
                    ts[session['user_id']].values.info,
                    state,
                    evaluate_asphalt(),
                    ts[session['user_id']].values.entropy_min_threshold,
                    ts[session['user_id']].values.entropy_max_threshold,
                    ts[session['user_id']].values.intensity_min_threshold_0,
                    ts[session['user_id']].values.intensity_max_threshold_0,
                    ts[session['user_id']].values.intensity_min_threshold_1,
                    ts[session['user_id']].values.intensity_max_threshold_1,
                    ts[session['user_id']].values.blur)
            ts[session['user_id']].experiment_id = execute_query(query, values)[0][0]
            activate_experiment(ts[session['user_id']].experiment_id)
            print(ts[session['user_id']].experiment_id)            
        else:
            print('Updating record.')
            print('state', state)
            print(ts[session['user_id']].experiment_id)
            query = 'UPDATE experiments SET img_width = %s, img_height = %s, img_mask_asphalt=%s, img_mask_aggregate=%s, expert_guess=%s, info=%s, current_state=%s, asphalt_ratio=%s, entropy_min_threshold=%s, entropy_max_threshold=%s, intensity_min_threshold_0=%s, intensity_max_threshold_0=%s, intensity_min_threshold_1=%s, intensity_max_threshold_1=%s, blur=%s WHERE id=%s'
            values = (ts[session['user_id']].color_original.shape[1],
                      ts[session['user_id']].color_original.shape[0],
                      ts[session['user_id']].asphalt_mask.tobytes(),
                      ts[session['user_id']].aggregate_mask.tobytes(),
                      ts[session['user_id']].values.expert_guess,
                      ts[session['user_id']].values.info,
                      state,
                      evaluate_asphalt(),
                      ts[session['user_id']].values.entropy_min_threshold,
                      ts[session['user_id']].values.entropy_max_threshold,
                      ts[session['user_id']].values.intensity_min_threshold_0,
                      ts[session['user_id']].values.intensity_max_threshold_0,
                      ts[session['user_id']].values.intensity_min_threshold_1,
                      ts[session['user_id']].values.intensity_max_threshold_1,
                      ts[session['user_id']].values.blur,
                      ts[session['user_id']].experiment_id)
            execute_query(query, values)
            print('Record up.')
        
        print(state.lower())
        print(state.lower() == 'finished')
        if state.lower() == 'finished':
            # delete temporary storage and create a new one
            print('Experiment finished.')
            ts.pop(session['user_id'])
            ts[session['user_id']] = UserTemporaryStorage()
        status = 'success'
    except Exception as e:
        status = 'error'        
    return json.dumps({'status': status}), 200, {'Content-Type': 'application/json'}


@app.route('/backup-storage',methods=['POST'])
@check_authentication
def backup_temporal_storage():
    # This function bacups the temporary storage of the user and creates a new one
    # it should be called when the user wants to upload new images without harming the current experiment
    ts[str(session['user_id'])+"&backup"] = ts[session['user_id']]
    ts[session['user_id']] = UserTemporaryStorage()
    return json.dumps({'status': 'success'}), 200, {'Content-Type': 'application/json'}

@app.route('/restore-storage',methods=['POST'])
@check_authentication
def restore_temporal_storage():
    # This function restores the temporary storage of the user from the backup
    # it should be called when the user wants to restore the previous experiment
    ts[session['user_id']] = ts[str(session['user_id'])+"&backup"]
    ts.pop(str(session['user_id'])+"&backup")
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
    threshold=128 #consider changing this to a value from the form that user can set # threshold=request.form.get('threshold')
    if file.filename[-len('.HEIC'):].upper() == '.HEIC':
        image = Image.open(file.stream)
        unique_query = str(request.args.get('nocache')) + '_' + str(session['user_id'])
        path = f'temp/temp_{unique_query}.png'
        image.save(path)
        image = Image.open(path)
        print('SHAPE ORIGINAL', image.size)
        image = np.concatenate((np.array(image), np.ones((image.size[1], image.size[0], 1), dtype=np.uint8)*255), axis=2)
        ts[session['user_id']].color_original = image
    else:
        image = Image.open(file.stream)
        ts[session['user_id']].color_original = np.array(image)
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
    ts[session['user_id']].aggregate_mask = np.array(mask, dtype=bool)
    ts[session['user_id']].values.threshold = threshold
    ts[session['user_id']].color = image
 
    
    # return the mask
    print('Background removed')
    if file.filename[-len('.HEIC'):].upper() == '.HEIC':
        # delete the temporary file
        os.remove(path)
        
    json_response = {'original_image': base64.b64encode(encode_to_png(ts[session['user_id']].color_original)).decode('utf-8'),
                     'nobg': base64.b64encode(encode_to_png(ts[session['user_id']].color)).decode('utf-8')}
    return json.dumps(json_response), 200, {'Content-Type': 'application/json'}
    # return encode_to_png(image), 200, {'Content-Type': 'image/png'}


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
    min_threshold_0 = int(request.form.get('minThreshold0', 0))
    max_threshold_0 = int(request.form.get('maxThreshold0', 100))
    min_threshold_1 = int(request.form.get('minThreshold1', 100))
    max_threshold_1 = int(request.form.get('maxThreshold1', 255))
    entropy_min_threshold = int(request.form.get('entropyMinThreshold', 0))
    entropy_max_threshold = int(request.form.get('entropyMaxThreshold', 255))
    
    # save the values
    ts[session['user_id']].values.intensity_min_threshold_0 = min_threshold_0
    ts[session['user_id']].values.intensity_max_threshold_0 = max_threshold_0
    ts[session['user_id']].values.intensity_min_threshold_1 = min_threshold_1
    ts[session['user_id']].values.intensity_max_threshold_1 = max_threshold_1
    ts[session['user_id']].values.entropy_min_threshold = entropy_min_threshold
    ts[session['user_id']].values.entropy_max_threshold = entropy_max_threshold    
    
    print('Mask applied')
    # np_gray = cv2.imread('temp/gray_temp.jpg', cv2.IMREAD_GRAYSCALE)
    # np_entropy = cv2.imread('temp/entropy_temp.jpg', cv2.IMREAD_GRAYSCALE)
    np_gray = ts[session['user_id']].gray
    np_entropy = ts[session['user_id']].entropy
    
    min_thresholds = [min_threshold_0, min_threshold_1]
    max_thresholds = [max_threshold_0, max_threshold_1]    
    print('Thresholds:', min_thresholds, max_thresholds)
    print('Entropy thresholds:', entropy_min_threshold, entropy_max_threshold)
    if image_id == 'gray':
        print('Gray image selected.')
        overlay_image = apply_red_overlay(np_gray, np_gray, np_entropy, min_thresholds, max_thresholds,
                                          entropy_min_threshold, entropy_max_threshold)
    else:
        print('Color image selected.')
        overlay_image = apply_red_overlay(np_entropy, np_gray, np_entropy, min_thresholds, max_thresholds,
                                          entropy_min_threshold, entropy_max_threshold)

    img_byte_arr=encode_to_png(overlay_image) #should be equivalent to the 3 rows bellow
    entropy_byte_arr = encode_to_png(np_entropy)    
    # stringify the image
    img_byte_arr = base64.b64encode(img_byte_arr).decode('utf-8')
    entropy_byte_arr = base64.b64encode(entropy_byte_arr).decode('utf-8')
    return json.dumps({'overlay': img_byte_arr, 'entropy': entropy_byte_arr}), 200, {'Content-Type': 'application/json'}

def apply_red_overlay(masked_img, intensity_img, entropy_img, min_thresholds, max_thresholds, entropy_min_threshold,
                      entropy_max_threshold):        
    intensity_mask_0 = (intensity_img >= min_thresholds[0]) & (intensity_img <= max_thresholds[0])
    intensity_mask_1 = (intensity_img >= min_thresholds[1]) & (intensity_img <= max_thresholds[1])
    entropy_mask = (entropy_img >= entropy_min_threshold) & (entropy_img <= entropy_max_threshold)
    # combined_mask = intensity_mask & entropy_mask 

    intensity_mask = intensity_mask_0 | intensity_mask_1
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
