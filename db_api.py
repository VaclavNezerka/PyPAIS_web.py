# DB API
import os
import psycopg2 as psql

def open_db_connection() -> object:
    connection=psql.connect(
        host='localhost',
        database="pypais",
        user=os.environ['DB_USERNAME'],
        password=os.environ['DB_PASSWORD'])
    return connection

def save_record_to_db(**args):
    conn = open_db_connection()
    cur=conn.cursor()

def return_table_users(**args):
    conn = open_db_connection()
    cur=conn.cursor()
    cur.execute('SELECT * FROM users;')
    users=cur.fetchall()
    print(users)
    cur.close()
    conn.close()
    
    
return_table_users()
    
    