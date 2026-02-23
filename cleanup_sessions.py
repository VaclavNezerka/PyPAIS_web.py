# cleanup_sessions.py - a script to clean up expired sessions from the database, to be run as a background task in gunicorn
# out of request workers, so it runs just once, not n_workers times
from sqlalchemy import create_engine, text
from db_api import db_name, db_user, dbpwd, db_host
# raw engine, independent of Flask app
engine = create_engine(f"postgresql://{db_user}:{dbpwd}@{db_host}/{db_name}")

def cleanup_expired_sessions():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sessions WHERE expiry < (NOW() AT TIME ZONE 'UTC')"))