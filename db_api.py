# DB API
import os
import psycopg2 as psql
from psycopg2.extras import RealDictCursor
from functools import wraps
from flask import app, flash
from dataclasses import dataclass
from sqlalchemy import values
from typing_extensions import deprecated
import imagehash
import numpy as np
from getpass import getpass
# from imagehash import 
from dotenv import load_dotenv

load_dotenv()

# dbpwd = getpass("Enter database password: ")
# dbpwd = os.environ['DB_PASSWORD']
dbpwd = os.getenv('DB_PASSWORD')
db_user = os.getenv('DB_USERNAME')
db_name = os.getenv('DB_NAME')
db_host = os.getenv('DB_HOST')
def open_db_connection() -> object:
    # Opens a connection and its cursor
    connection=psql.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=dbpwd)
    
    # Disable autocommit to allow for FOR UPDATE queries (lock) and manual transaction control
    connection.autocommit = False
    
    return connection, connection.cursor()

def close_all(*args):
    # closes all given objects (assume connection() and cursor())
    for arg in args:
        arg.close()

def db_connection(func):
    # This function, used as decorator automatically handles the  opening and closing of connections and cursors in functions.
    @wraps(func)
    def wrapper(*args,**kwargs):
        conn, cur = open_db_connection()
        try:
            result=func(cur,conn,*args,**kwargs)
        except Exception as e:
            print(f'Database error calling {func.__name__}: \n {e}')
            flash('Database error.', 'error')
            conn.rollback()
            result = None
        finally:
            close_all(conn,cur)
        return result
    return wrapper

@db_connection
def change_password(cur, conn, values):
    cur.execute('SELECT 1 FROM users WHERE username=%s FOR UPDATE', (values[1],))
    cur.execute('UPDATE users SET pwd=%s WHERE username=%s', values)
    conn.commit()

@db_connection
def change_user_blockade(cur, conn, user_id: int, is_blocked: bool) -> None:
    cur.execute('SELECT 1 FROM users WHERE id=%s FOR UPDATE', (user_id,))
    query='UPDATE users SET is_blocked=%s WHERE id=%s'
    values=(is_blocked, user_id)
    cur.execute(query, values)
    conn.commit()

@db_connection
def is_user_blocked(cur, conn, user_id: int) -> bool:
    query='SELECT is_blocked FROM users WHERE id=%s'
    values=(user_id,)
    response=execute_query(query=query,values=values)
    if not response:
        return False
    is_blocked=response[0][0]
    return is_blocked

@db_connection
def get_password_hash(cur, conn, user_id: int) -> str:
    query='SELECT pwd FROM public_users WHERE id=%s'
    values=(user_id,)
    response=execute_query(query=query,values=values)
    if not response:
        return None
    pwd_hash=response[0][0]
    return pwd_hash

@db_connection
def get_user_id(cur, conn, username: str = None, email: str = None) -> int | None:
    query = 'SELECT id FROM public_users WHERE username=%s OR e_mail=%s'
    response = execute_query(query, (username, email))
    if not response:
        return None
    return response[0][0]

@db_connection
def get_user_id_of_experiment(cur, conn, id: str) -> int | None:
    query = 'SELECT user_id FROM experiments WHERE experiment_id=%s'
    response = execute_query(query, (id,))
    if not response:
        return None
    return response[0][0]

def hex_to_colorhash(colorhash:str, nbits=42, nbins=3):
    """Convert a hexadecimal string to an ImageHash object representing a colorhash."""
    bits = bin(int(colorhash, 16))[2:].zfill(nbits)
    hash_array = np.array(list(map(int, bits)), dtype=bool).reshape((nbits // nbins, nbins))
    return imagehash.ImageHash(hash_array)

@db_connection
def store_similar_images(cur, conn, experiment_id: int, similar_by_histogram: list[int, float], similar_by_ssim: list[int, float]) -> None:
    cur.execute('SELECT 1 FROM experiments WHERE experiment_id=%s FOR UPDATE', (experiment_id,))
    query = 'UPDATE experiments SET similarity_controll_done=True, similar_hist_id=%s, similar_ssim_id=%s, similar_hist_value=%s, similar_ssim_value=%s WHERE experiment_id=%s'
    print('image storing')
    cur.execute(query, (
        int(similar_by_histogram[1]), int(similar_by_ssim[1]), 
        float(similar_by_histogram[0]), float(similar_by_ssim[0]), experiment_id))
    print('ok')
    conn.commit()

@db_connection
def update_default_experiment_info(cur, conn, user_id: int, field: str, value: str) -> None:
    valid_fields = {'info_aggregate', 'info_binder', 'info_place_of_experiment', 'info_sample_collection_data', 'info_test_procedure', 'info_exposing_water_temperature', 'info_wrapping_temperature'}
    if field not in valid_fields:
        raise ValueError(f"Invalid field: {field}. Valid fields are: {valid_fields}")
    record = execute_query(f'SELECT user_id FROM default_info WHERE user_id=%s', (user_id,))
    if not value:
        value = None
    
    if not record:
        query = f'INSERT INTO default_info (user_id, {field}) VALUES (%s, %s)'
        cur.execute(query, (user_id, value))
    else:
        cur.execute('SELECT 1 FROM default_info WHERE user_id=%s FOR UPDATE', (user_id,))
        query = f'UPDATE default_info SET {field}=%s WHERE user_id=%s'
        cur.execute(query, (value, user_id))
    conn.commit()
    

@db_connection
def get_default_experiment_info(cur, conn, user_id: int) -> dict:
    query = 'SELECT * FROM default_info WHERE user_id=%s'
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, (user_id,))
    response = cursor.fetchone()
    if not response:
        return {}
    return dict(response)

@db_connection
def load_image_by_experiment_id(cur, conn, experiment_id: int) -> bytes | None:
    query = 'SELECT color FROM experiments WHERE experiment_id=%s'
    response = execute_query(query, (experiment_id,))
    if not response:
        return None
    return response[0][0]

# TODO: consider joining with get_comparing_image_hashes
@db_connection
def get_all_company_employees(cur, conn, company_id: int) -> list[dict]:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT first_name, last_name, username, e_mail, is_company_admin, is_blocked FROM users WHERE company=%s AND e_mail_confirmed=True;'
    cursor.execute(query, (company_id,))
    result = cursor.fetchall()
    if not result:
        return []
    # Convert RealDictRow to a regular dict
    result = [dict(row) for row in result]
    return result

# TODO: consider joining with get_comparing_image_hashes
@db_connection
def get_all_company_experiments(cur, conn, company_id: int) -> list[dict]:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT experiment_id, time_stamp, u.first_name, u.last_name, u.e_mail, expert_guess, asphalt_ratio  FROM experiments e JOIN users u ON e.user_id = u.id  WHERE u.company=%s AND e.fake_deleted=false;'
    cursor.execute(query, (company_id,))
    result = cursor.fetchall()
    if not result:
        return []
    # Convert RealDictRow to a regular dict
    result = [dict(row) for row in result]
    return result


# TODO: consider joining with get_all_company_experiments
@db_connection
def get_comparing_image_hashes(cur, conn, user_id: int, experiment_id: int) -> tuple[list, dict]:
    query = 'SELECT experiment_id, phash, ahash, dhash, colorhash FROM experiments e JOIN users u_exp ON e.user_id = u_exp.id JOIN users u ON u_exp.company = u.company WHERE u.id=%s AND e.experiment_id !=%s'
    response = execute_query(query, (user_id, experiment_id))
    # 
    # return response
    experiment_ids = [row[0] for row in response]
    hashes = {
        "phash": [imagehash.hex_to_hash(row[1]) for row in response],
        "ahash": [imagehash.hex_to_hash(row[2]) for row in response],
        "dhash": [imagehash.hex_to_hash(row[3]) for row in response],
        "colorhash": [hex_to_colorhash(row[4]) for row in response]
    }
    return experiment_ids, hashes

@db_connection
def save_image_hash_by_experiment_id(cur, conn, experiment_id: int, values: dict) -> None:
    valid_keys = {'phash', 'ahash', 'dhash', 'colorhash'}
    filtered_values = {k: v for k, v in values.items() if k in valid_keys}
    cur.execute('SELECT 1 FROM experiments WHERE experiment_id=%s FOR UPDATE', (experiment_id,))
    query = 'UPDATE experiments SET phash=%s, ahash=%s, dhash=%s, colorhash=%s WHERE experiment_id=%s '
    cur.execute(query, (filtered_values.get('phash'), filtered_values.get('ahash'), filtered_values.get('dhash'), filtered_values.get('colorhash'), experiment_id))
    conn.commit()

@db_connection
def get_image_hashes_by_experiment_id(cur, conn, experiment_id: int) -> dict:
    query = 'SELECT phash, ahash, dhash, colorhash FROM experiments WHERE experiment_id=%s'
    response = execute_query(query, (experiment_id,))
    if not response:
        return {}
    row = response[0]
    hashes = {
        "phash": imagehash.hex_to_hash(row[0]),
        "ahash": imagehash.hex_to_hash(row[1]),
        "dhash": imagehash.hex_to_hash(row[2]),
        "colorhash": hex_to_colorhash(row[3])
    }
    return hashes

@dataclass
class User:
    first_name: str
    last_name: str
    username: str
    e_mail: str
    company: str

    def to_dict(self) -> dict:
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "username": self.username,
            "e_mail": self.e_mail,
            "company": self.company
        }

# @dataclass
# class Experiment:
#     id: int
#     time_stamp: str
#     user_id: int | None
#     img_width: int
#     img_height: int
#     img: bytes
#     img_mask_asphalt: bytes | None = None
#     img_mask_aggregate: bytes | None = None
#     expert_guess: str | None = None
#     info: str | None = None
#     img_mask_asphalt_manual_correction: bytes | None = None
#     img_mask_aggregate_manual_correction: bytes | None = None
#     user_id: int | None = None
#     active: bool = True
#     processed_by_model: str | None = None

#     def to_dict(self) -> dict:
#         return self.__dict__


@db_connection 
def get_company_id_by_key(cur, conn, company_key: str) -> int | None:
    query = "SELECT company_id FROM public_companies WHERE company_key=%s"
    result = execute_query(query, (str(company_key),))
    if not result:
        return None
    return result[0][0]

@db_connection 
def update_company_key(cur, conn, company_id: str) -> int | None:
    cur.execute('SELECT 1 FROM companies WHERE company_id=%s FOR UPDATE', (company_id,))
    query = 'UPDATE companies SET company_key=%s WHERE company_id=%s'
    is_unique = False
    while not is_unique:
        company_key = os.urandom(4).hex()
        is_unique = not cur.execute('SELECT company_id FROM companies WHERE company_key=%s', (company_key,))
    cur.execute(query, (company_key, company_id))
    conn.commit()
    return company_key

@db_connection
def get_experiment_timestamp_by_id(cur, conn, experiment_id: str) -> str:
    query = 'SELECT time_stamp FROM experiments WHERE experiment_id=%s'
    response = execute_query(query, (experiment_id,))
    if not response:
        return ""
    return response[0][0]

@db_connection
def get_users_by_company(cur, conn, company_id: int) -> list[dict]:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT id, first_name, last_name, e_mail FROM users WHERE company=%s AND e_mail_confirmed=True'
    cursor.execute(query, (company_id,))
    result = cursor.fetchall()
    if not result:
        return {}
    # Convert RealDictRow to a regular dict
    result = [dict(row) for row in result]
    return result

@db_connection
def get_experiment_by_id_and_user(cur, conn, experiment_id: str, user_id: str) -> dict | None:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT experiment_id FROM experiments AS e JOIN public_users AS u ON e.user_id = u.id WHERE e.experiment_id=%s AND e.user_id=%s'
    cursor.execute(query, (experiment_id, user_id))
    result = cursor.fetchone()
    if not result:
        return {}
    # Convert RealDictRow to a regular dict
    result = dict(result)
    return result

@db_connection
def get_experiment_by_id_and_company(cur, conn, experiment_id: str, company_id: str) -> dict | None:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT experiment_id FROM experiments AS e JOIN public_users AS u ON e.user_id = u.id WHERE e.experiment_id=%s AND u.company=%s'
    cursor.execute(query, (experiment_id, company_id))
    result = cursor.fetchone()
    if not result:
        return {}
    # Convert RealDictRow to a regular dict
    result = dict(result)
    return result

@db_connection
def get_user_by_id(cur, conn, user_id: int) -> dict | None:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT first_name, last_name, username, e_mail, company, is_company_admin FROM public_users WHERE id=%s'
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    if not result:
        return None
    # Convert RealDictRow to a regular dict
    result = dict(result)
    print(result)
    return result

@db_connection
def get_user_info_by_id(cur, conn, user_id: str) -> dict | None:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT u.first_name, u.last_name, u.username, u.e_mail, c.company_name FROM public_users AS u JOIN public_companies AS c ON u.company = c.company_id WHERE u.id=%s'
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    if not result:
        return None
    # Convert RealDictRow to a regular dict
    result = dict(result)
    return result

@db_connection
def get_experiment_by_id(cur, conn, experiment_id: str) -> dict | None:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT * FROM experiments WHERE experiment_id=%s'
    cursor.execute(query, (experiment_id,))
    result = cursor.fetchone()
    if not result:
        return None
    # Convert RealDictRow to a regular dict
    result = dict(result)
    # for key in ['mask_asphalt', 'mask_aggregate', 'mask_asphalt_manual_correction', 'mask_aggregate_manual_correction']:
    #     print(f"Checking field {key} with value {result.get(key)} and type {type(result.get(key))}")
    #     if isinstance(result.get(key), str):
    #         result[key] = None
    return result

@db_connection
def get_company_info_by_id(cur, conn, company_id: str) -> dict:
    cursor = conn.cursor(cursor_factory=RealDictCursor) 
    query = 'SELECT company_name, company_address, e_mail FROM public_companies WHERE company_id=%s'
    cursor.execute(query, (company_id,))
    result = cursor.fetchone()
    if not result:
        return {}
    # Convert RealDictRow to a regular dict
    result = dict(result)
    return result

@db_connection
def save_new_company_db(cur, conn , values: dict):
    valid_keys = {'company_name', 'company_address', 'company_key', 'e_mail'}
    filtered_values = {k: v for k, v in values.items() if k in valid_keys}
    
    query = f"INSERT INTO public_companies ({', '.join(filtered_values.keys())}) VALUES ({', '.join(['%s'] * len(filtered_values))})"
    cur.execute(query, tuple(filtered_values.values()))
    conn.commit()
    return None  # Success

@db_connection
def get_company_key(cur, conn, company_id: str) -> str:
    query = "SELECT company_key FROM public_companies WHERE company_id=%s"
    result = execute_query(query, (str(company_id),))
    return result[0][0]

@db_connection
def check_company_key_exists(cur, conn, company_key: str) -> bool:
    """Check if a company key already exists in the database."""
    query = "SELECT company_id FROM public_companies WHERE company_key=%s"
    result = execute_query(query, (str(company_key),))
    return bool(result)

@db_connection
def confirm_user_email(cur, conn, email: str) -> None:
    cur.execute('SELECT 1 FROM public_users WHERE e_mail=%s FOR UPDATE', (email,))
    query = "UPDATE public_users SET e_mail_confirmed=True WHERE e_mail=%s"
    cur.execute(query, (email,))
    conn.commit()

@db_connection
def confirm_company_registration(cur, conn, email: str) -> None:
    cur.execute('SELECT 1 FROM public_companies WHERE e_mail=%s FOR UPDATE', (email,))
    query = "UPDATE public_companies SET confirmed_by_admin=True WHERE e_mail=%s"
    cur.execute(query, (email,))
    conn.commit()

@db_connection

def confirm_company_email(cur, conn, email: str) -> None:
    cur.execute('SELECT 1 FROM public_companies WHERE e_mail=%s FOR UPDATE', (email,))
    query = "UPDATE public_companies SET e_mail_confirmed=True WHERE e_mail=%s"
    cur.execute(query, (email,))
    conn.commit()

@db_connection
def is_user_email_confirmed(cur, conn, user_id: int) -> bool:
    query = "SELECT e_mail_confirmed FROM public_users WHERE id=%s"
    result = execute_query(query, (user_id,))
    if not result:
        return False
    return result[0][0]

@db_connection
def is_company_email_confirmed(cur, conn, company_id: int) -> bool:
    query = "SELECT e_mail_confirmed FROM public_companies WHERE company_id=%s"
    result = execute_query(query, (company_id,))
    if not result:
        return False
    return result[0][0]

@db_connection
def change_admin_privileges(cur, conn , user_id: int, is_admin: bool):
    cur.execute('SELECT 1 FROM public_users WHERE id=%s FOR UPDATE', (user_id,))
    query = "UPDATE public_users SET is_company_admin=%s WHERE id=%s"
    cur.execute(query, (is_admin, user_id))
    conn.commit()

@db_connection
def save_new_user_db(cur, conn , values: dict):
    cur.execute('SELECT 1 FROM public_users WHERE username=%s OR e_mail=%s FOR UPDATE', (values.get('username'), values.get('e_mail')))
    # cur.execute('INSERT INTO users (username, e_mail, first_name, last_name, company, pwd) '
    #             'VALUES (%s,%s,%s,%s,%s,%s)', values)
    # conn.commit()
    valid_keys = {'username', 'e_mail', 'first_name', 'last_name', 'company', 'pwd'}
    filtered_values = {k: v for k, v in values.items() if k in valid_keys}

    query = f"INSERT INTO public_users ({', '.join(filtered_values.keys())}) VALUES ({', '.join(['%s'] * len(filtered_values))})"
    cur.execute(query, tuple(filtered_values.values()))
    conn.commit()
    return None  # Success

@deprecated("This function is deprecated. Use get_experiment_by_id instead.")
@db_connection
def load_experiment_from_db(cur,conn, id):
    # cur.execute("""SELECT img_width, img_height,
                # img, img_mask_asphalt, img_mask_aggregate,
                # expert_guess, info,
                # entropy_min_threshold, entropy_max_threshold, 
                # intensity_min_threshold_0,intensity_max_threshold_0,
                # intensity_min_threshold_1,intensity_max_threshold_1,
                # blur,
                # img_mask_asphalt_manual_correction,
                # img_mask_aggregate_manual_correction
                # FROM experiments WHERE id=%s""", (id,))
    cur.execute("SELECT * FROM experiments WHERE experiment_id=%s", (id,))
    response = cur.fetchall()[0]
    return response

# @db_connection
# def update_experiment_active_status(cur, conn, experiment_id, active: bool):
#     query = 'UPDATE experiments SET active=%s WHERE experiment_id=%s'
#     execute_query(query, (active, experiment_id))

@db_connection
def update_experiment_active_status(cur, conn, user_id, active: bool, experiment_id: int = None):
    cur.execute('SELECT 1 FROM users WHERE id=%s FOR UPDATE', (user_id,))   
    if active:
        query = 'UPDATE users SET active_experiment_id=%s WHERE id=%s'
        values=(experiment_id, user_id)
    else:
        query = 'UPDATE users SET active_experiment_id=NULL WHERE id=%s'
        values=(user_id,)
    cur.execute(query, values)
    conn.commit()


@db_connection
def insert_experiment_to_db(cur ,conn, values_dict: dict) -> None:
    query = f"INSERT INTO experiments ({', '.join(f'{k}' for k in values_dict.keys())}) VALUES ({', '.join(['%s'] * len(values_dict))}) RETURNING experiment_id"
    # command = f'INSERT INTO experiments {tuple(values_dict.keys())} VALUES {("%s,"*len(values_dict))[:-1]}'
    values = tuple(values_dict.values())
    cur.execute(query, values)
    conn.commit()
    return cur.fetchone()[0]  # Return the ID of the newly inserted experiment

@db_connection
def update_experiment_in_db(cur ,conn, values_dict: dict, experiment_id: str) -> None:
    cur.execute('SELECT 1 FROM experiments WHERE experiment_id=%s FOR UPDATE', (experiment_id,))
    command = f'UPDATE experiments SET ' + ', '.join([f"{key}=%s" for key in values_dict.keys()]) + ' WHERE experiment_id=%s'
    # values = tuple(values_dict.values()) + (str(experiment_id),)
    
    #  
    # values = tuple((v if v is not None else None) for v in values_dict.values()) + (str(experiment_id),)
    values = tuple(values_dict.values()) + (str(experiment_id),)
    cur.execute(command, values)
    conn.commit()

@db_connection
def update_users_table(cur,conn, values_dict: dict, user_id: int) -> None:
    cur.execute('SELECT 1 FROM users WHERE id=%s FOR UPDATE', (user_id,))
    command = f'UPDATE users SET ' + ', '.join([f"{key}=%s" for key in values_dict.keys()]) + ' WHERE id=%s'
    values = tuple(values_dict.values()) + (user_id,)
    cur.execute(command, values)   
    conn.commit()

@db_connection
def update_companies_table(cur,conn, values_dict: dict, company_id: int) -> None:
    cur.execute('SELECT 1 FROM companies WHERE company_id=%s FOR UPDATE', (company_id,))
    command = f'UPDATE companies SET ' + ', '.join([f"{key}=%s" for key in values_dict.keys()]) + ' WHERE company_id=%s'
    values = tuple(values_dict.values()) + (company_id,)
    cur.execute(command, values)   
    conn.commit()


# @db_connection
# def return_active_experiment_id(cur,conn, user_id) -> int | None:
#     cur.execute('SELECT experiment_id FROM experiments WHERE user_id=%s AND active=True', (user_id,))
#     experiment_id=cur.fetchall()
#     experiment_id = experiment_id[0][0] if experiment_id else None
#     return experiment_id

@db_connection
def return_active_experiment_id(cur,conn, user_id) -> int | None:
    cur.execute('SELECT active_experiment_id FROM users WHERE id=%s', (user_id,))
    experiment_id=cur.fetchall()
    experiment_id = experiment_id[0][0] if experiment_id else None
    return experiment_id

@db_connection
def execute_query(cur,conn,query,values):
    cur.execute(query,values)
    try:
        response=cur.fetchall()
    except Exception as e:
        response=e
    finally:
        conn.commit()
    return response
