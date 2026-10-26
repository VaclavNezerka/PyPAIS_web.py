# gunicorn.conf.py (gunicorn reads it from the working directory; run_prod.sh adds --bind and --workers)
import os
import sys
from cleanup_sessions import cleanup_expired_sessions
from apscheduler.schedulers.background import BackgroundScheduler

# One CPU inference takes about 30-60 s (a GPU is much faster) and a report export may run the model for samples
# without stored masks - the default 30 s would kill the worker in the middle of the request.
timeout = int(os.getenv('GUNICORN_TIMEOUT', 180))

def when_ready(server):
    """
    Called before the worker processes are forked.
    I.e. all background tasks should be started here, so they run just ones, not n_workers times.
    """
    scheduler = BackgroundScheduler()
    scheduler.start()
    scheduler.add_job(cleanup_expired_sessions, 'interval', seconds=300)  # run every 5 minutes

def post_fork(server, worker):
    """
    Torch uses all CPU cores in every process - with several workers they would fight over them.
    Each worker gets cores / workers threads unless TORCH_NUM_THREADS is set (models.py applies it when imported).
    """
    threads = os.environ.setdefault('TORCH_NUM_THREADS', str(max(1, (os.cpu_count() or 1) // server.cfg.workers)))
    if 'torch' in sys.modules:  # the app was preloaded before the fork (preload_app)
        sys.modules['torch'].set_num_threads(int(threads))
