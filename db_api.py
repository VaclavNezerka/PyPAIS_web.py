# DB API
import os
import psycopg2 as psql
from psycopg2.extras import RealDictCursor
from functools import wraps
from flask import flash
from dataclasses import dataclass
from typing_extensions import deprecated

# # TODO: ***** 
# # TODO: CONSIDER a switch to SQLModel 
# # TODO: ***** 
# import numpy as np
# import sqlmodel as sm
# from sqlmodel import Field, Relationship

# DATABASE_URL = os.getenv('DATABASE_URL', None)
# if DATABASE_URL is None:
#     raise ValueError("DATABASE_URL environment variable is not set.")
# engine = sm.create_engine(DATABASE_URL)
# if not sm.SQLModel.metadata.tables: 
#     sm.SQLModel.metadata.create_all(engine)

# class User(sm.SQLModel, table=True):
#     id: int | None = Field(default=None, primary_key=True)
#     username: str
#     e_mail: str 
#     first_name: str | None = None
#     last_name: str | None = None
#     company: str | None = None
#     pwd: str

#     def __repr__(self):
#         return f"User(id={self.id}, username={self.username}, e_mail={self.e_mail})"
    
#     def to_dict(self):
#         return {
#             "id": self.id,
#             "username": self.username,
#             "e_mail": self.e_mail,
#             "first_name": self.first_name,
#             "last_name": self.last_name,
#             "company": self.company
#         }
    
#     def check_password(self, password: str) -> bool:
#         """
#         Check if the provided password matches the stored password.
        
#         Args:
#             password (str): The hashed password to check.

#         Returns:
#             bool: True if the password matches, False otherwise.
#         """
#         return self.pwd == password
    
#     def set_properties(self, properties: dict) -> None:
#         for key, value in properties.items():
#             if hasattr(self, key):
#                 setattr(self, key, value)
    
#     def get_properties(self) -> dict:
#         return self.to_dict()   

# class Experiment(sm.SQLModel, table=True):
#     id: int | None = Field(default=None, primary_key=True)
#     img_width: int
#     img_height: int
#     img: bytes
#     img_mask_asphalt: bytes | None = None
#     img_mask_aggregate: bytes | None = None
#     expert_guess: str | None = None
#     info: str | None = None
#     img_mask_asphalt_manual_correction: bytes | None = None
#     img_mask_aggregate_manual_correction: bytes | None = None
#     user_id: int | None = Field(default=None, foreign_key="user.id")
#     active: bool = Field(default=True)
#     # internal information
#     processed_by_model: str | None = None # e.g., "model_UNET_v1"

#     def __repr__(self):
#         return f"Experiment(id={self.id}, user_id={self.user_id}, active={self.active})"
    
#     def to_dict(self):
#         return self.__dict__
    
#     def save_to_db(self, session: sm.Session) -> None:
#         session.add(self)
#         session.commit()
#         session.refresh(self)

#     def set_properties(self, properties: dict) -> None:
#         for key, value in properties.items():
#             if hasattr(self, key):
#                 setattr(self, key, value)
#         session = sm.Session(engine)
#         self.save_to_db(session)

#     def get_properties(self) -> dict:
#         return self.to_dict()
    
#     def set_properties(self, properties: dict) -> None:
#         for key, value in properties.items():
#             if hasattr(self, key):
#                 if isinstance(value, np.ndarray):
#                     value = value.tobytes()
#                 setattr(self, key, value)

# class Company(sm.SQLModel, table=True):
#     id: int | None = Field(default=None, primary_key=True)
#     name: str
#     address: str | None = None
#     admins: list["Admin"] = Relationship(back_populates="company")
#     users: list[User] = Relationship(back_populates="company")
#     company_key: str | None = None  # New field for company key

# class Admin(sm.SQLModel, table=True):
#     id: int | None = Field(default=None, primary_key=True)
#     user_id: int = Field(foreign_key="user.id")
#     company_id: int = Field(foreign_key="company.id")
#     user: User = Relationship(back_populates="admins")
#     company: Company = Relationship(back_populates="admins")

# def load_experiment_by_id(experiment_id: int) -> Experiment | None:
#     with sm.Session(engine) as session:
#         response = session.get(Experiment, experiment_id)
#     return response

# def load_user_by_username(username: str) -> User | None:
#     with sm.Session(engine) as session:
#         statement = sm.select(User).where(User.username == username)
#         response = session.exec(statement).first()
#     return response

# def load_user_by_email(e_mail: str) -> User | None:
#     with sm.Session(engine) as session:
#         statement = sm.select(User).where(User.e_mail == e_mail)
#         response = session.exec(statement).first()
#     return response

# def load_user_by_id(user_id: int) -> User | None:
#     with sm.Session(engine) as session:
#         response = session.get(User, user_id)
#     return response

# # TODO: ***** 
# # TODO: END --- CONSIDER a switch to SQLModel 
# # TODO: ***** 

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
    cur.execute('UPDATE users SET pwd=%s WHERE username=%s', values)
    conn.commit()

@db_connection
def get_password_hash(cur, conn, user_id: int) -> str:
    query='SELECT pwd FROM public_users WHERE id=%s'
    values=(user_id,)
    pwd_hash=execute_query(query=query,values=values)[0][0]
    return pwd_hash

@db_connection
def get_user_id(cur, conn, username: str = None, email: str = None) -> int | None:
    query = 'SELECT id FROM public_users WHERE username=%s OR e_mail=%s'
    user_id = execute_query(query, (username, email))[0][0]
    return user_id

@db_connection
def get_user_id_of_experiment(cur, conn, id: str) -> int | None:
    query = 'SELECT user_id FROM experiments WHERE experiment_id=%s'
    user_id = execute_query(query, (id,))[0][0]
    return user_id

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
    query = 'UPDATE companies SET company_key=%s WHERE id=%s'
    is_unique = False
    while not is_unique:
        company_key = os.urandom(4).hex()
        is_unique = not execute_query('SELECT id FROM companies WHERE company_key=%s', (company_key,))
    execute_query(query, (company_key, company_id))
    return company_key

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
    return result

@db_connection
def save_new_user_db(cur, conn , values: dict):
    # cur.execute('INSERT INTO users (username, e_mail, first_name, last_name, company, pwd) '
    #             'VALUES (%s,%s,%s,%s,%s,%s)', values)
    # conn.commit()
    valid_keys = {'username', 'e_mail', 'first_name', 'last_name', 'company', 'pwd'}
    filtered_values = {k: v for k, v in values.items() if k in valid_keys}

    query = f"INSERT INTO public_users ({', '.join(filtered_values.keys())}) VALUES ({', '.join(['%s'] * len(filtered_values))})"
    cur.execute(query, tuple(filtered_values.values()))
    conn.commit()
    # execute_query('INSERT INTO public_users (username, e_mail, first_name, last_name, company, pwd) '
    #             'VALUES (%s,%s,%s,%s,%s,%s)')
    # print('User successfully inserted into database')
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

@db_connection
def update_experiment_active_status(cur, conn, experiment_id, active: bool):
    query = 'UPDATE experiments SET active=%s WHERE experiment_id=%s'
    execute_query(query, (active, experiment_id))


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
    command = f'UPDATE experiments SET ' + ', '.join([f"{key}=%s" for key in values_dict.keys()]) + ' WHERE experiment_id=%s'
    # print(command)
    values = tuple(values_dict.values()) + (str(experiment_id),)
    cur.execute(command, values)
    conn.commit()

@db_connection
def update_users_table(cur,conn, values_dict: dict, user_id: int) -> None:
    command = f'UPDATE users SET ' + ', '.join([f"{key}=%s" for key in values_dict.keys()]) + ' WHERE id=%s'
    values = tuple(values_dict.values()) + (user_id,)
    execute_query(command, values)


@db_connection
def return_active_experiment_id(cur,conn, user_id) -> int | None:
    cur.execute('SELECT experiment_id FROM experiments WHERE user_id=%s AND active=True', (user_id,))
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
