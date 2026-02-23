# gunicorn.conf.py
from cleanup_sessions import cleanup_expired_sessions
from apscheduler.schedulers.background import BackgroundScheduler

def when_ready(server):
    """
    Called before the worker processes are forked. 
    I.e. all background tasks should be started here, so they run just ones, not n_workers times.
    """
    scheduler = BackgroundScheduler()
    scheduler.start()
    scheduler.add_job(cleanup_expired_sessions, 'interval', seconds=300)  # run every 5 minutes