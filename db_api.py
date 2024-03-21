# DB API
import os
import psycopg2 as psql
from functools import wraps

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
def save_new_user_db(cur, conn , values):
    try:
        cur.execute('INSERT INTO users (username, e_mail, first_name, last_name, company, pwd) '
                    'VALUES (%s,%s,%s,%s,%s,%s)',
                    values)
        b=conn.commit()
        print(b)
        response=None
    except Exception as exception:
        response=exception
    finally:
        print(response)
        return response

@db_connection
def execute_query(cur,conn,query,values):
    cur.execute(query,values)
    response=cur.fetchall()
    return response

@db_connection
def return_table_users(cur,conn):
    cur.execute('SELECT * FROM public_users;')
    users=cur.fetchall()
    print(users)
