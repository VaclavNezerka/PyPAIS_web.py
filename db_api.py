# DB API
import os
import psycopg2 as psql
from functools import wraps
from flask import flash

def open_db_connection() -> object:
    # Opens a connection and its cursor
    connection=psql.connect(
        host='localhost',
        database="pypais",
        user=os.environ['DB_USERNAME'],
        password=os.environ['DB_PASSWORD'])
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
        finally:
            close_all(conn,cur)
        return result
    return wrapper

@db_connection
def change_password(cur, conn, values):
    cur.execute('UPDATE users SET pwd=%s WHERE username=%s', values)
    conn.commit()

@db_connection
def save_new_user_db(cur, conn , values):
    try:
        cur.execute('INSERT INTO users (username, e_mail, first_name, last_name, company, pwd) '
                    'VALUES (%s,%s,%s,%s,%s,%s)',
                    values)
        conn.commit()
        print('User successfully inserted into database')
        return None  # Success
    except Exception as exception:
        print(f'Database error: {exception}')
        conn.rollback()  # Rollback the transaction on error
        return exception  # Return the exception for error handling

@db_connection
def load_experiment_from_db(cur,conn, id):
    cur.execute("""SELECT img_width, img_height,
                img, img_mask_asphalt, img_mask_aggregate,
                expert_guess, info,
                entropy_min_threshold, entropy_max_threshold, 
                intensity_min_threshold_0,intensity_max_threshold_0,
                intensity_min_threshold_1,intensity_max_threshold_1,
                blur,
                img_mask_asphalt_manual_correction,
                img_mask_aggregate_manual_correction
                FROM experiments WHERE id=%s""", (id,))
    response = cur.fetchall()
    return response

@db_connection
def return_active_experiment_id(cur,conn, user_id):
    cur.execute('SELECT id FROM experiments WHERE added_by_user=%s AND active=True', (user_id,))
    experiment_id=cur.fetchall()
    return experiment_id[0][0]

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

@db_connection
def return_table_users(cur,conn):
    cur.execute('SELECT * FROM public_users;')
    users=cur.fetchall()
    print(users)

