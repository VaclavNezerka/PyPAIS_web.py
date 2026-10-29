"""Activity log of the website - the data behind the developers' report (/developer, activity_report.py).

Every request (except static files and health probes) becomes one row of activity_log: who (the signed-in user, or an
anonymous visitor), what (the event, page, status and details), with what (device, browser, language) and how fast.
Routes name what happened with track('event', **details); other requests are logged as 'page' (an HTML page),
'autosave' or 'api'.

Privacy: no cookies and no IP addresses are stored. Visitors are told apart by a hash of their address and browser
that changes every day (nobody can be followed from one day to the next), and only the network part of the address
(/24 for IPv4, /48 for IPv6) is kept for the security statistics. Rows older than ACTIVITY_RETENTION_DAYS are deleted.

The rows are written by a background thread in batches - a slow or unavailable database never delays a request,
and logging can never break one.
"""
import atexit
import hashlib
import ipaddress
import os
import queue
import re
import threading
import time
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from flask import g, request, session

import db_api

ENABLED = os.getenv('ACTIVITY_LOG', '1') != '0'
RETENTION_DAYS = int(os.getenv('ACTIVITY_RETENTION_DAYS', '400'))
BATCH_SIZE = 200
FLUSH_SECONDS = 2.0  # how long rows wait for a batch
PURGE_SECONDS = 6 * 3600
QUEUE_LIMIT = 20_000  # rows kept while the database is unavailable; beyond that new rows are dropped

# files and data the pages load for themselves - they say nothing about what people do
SKIPPED_ENDPOINTS = {'static', 'send_static', 'send_node_modules', 'download_file', 'translations_alerts'}
AUTOSAVE_ENDPOINTS = {'update_specific_value', 'save_experiment_info', 'save_experiment', 'update_default_experiment_info'}
# a URL token (confirmation links) must never be stored - matched routes are logged by their rule, e.g. /confirm_email/<token>
MAX_PATH = 256

BOT_PATTERN = re.compile(
    r'(googlebot|bingbot|yandex\w*|baiduspider|duckduckbot|applebot|petalbot|semrushbot|ahrefsbot|mj12bot|dotbot|'
    r'gptbot|claudebot|ccbot|bytespider|amazonbot|facebookexternalhit|twitterbot|slackbot|linkedinbot|telegrambot|'
    r'whatsapp|discordbot|headlesschrome|lighthouse|python-requests|python-urllib|aiohttp|httpx|go-http-client|'
    r'curl|wget|okhttp|java/|libwww|scrapy|uptime\w*|pingdom|statuscake|monitor\w*|[\w-]*bot\b|[\w-]*crawler|[\w-]*spider)',
    re.IGNORECASE)
BROWSERS = (('Edge', r'Edg(e|A|iOS)?/'), ('Opera', r'OPR/|Opera'), ('Samsung Internet', r'SamsungBrowser/'),
            ('Firefox', r'Firefox/|FxiOS/'), ('Chrome', r'Chrome/|CriOS/'), ('Safari', r'Safari/'))
SYSTEMS = (('Windows', r'Windows'), ('iOS', r'iPhone|iPad|iPod'), ('Android', r'Android'), ('ChromeOS', r'CrOS'),
           ('macOS', r'Macintosh|Mac OS X'), ('Linux', r'Linux|X11'))


def parse_user_agent(user_agent: str) -> dict:
    """Device class, browser and operating system from the User-Agent header (bots get their own name as browser)."""
    ua = user_agent or ''
    bot = BOT_PATTERN.search(ua) if ua else None
    if re.search(r'iPad|Tablet', ua) or ('Android' in ua and 'Mobile' not in ua):
        device = 'tablet'
    elif re.search(r'Mobi|iPhone|iPod|Android', ua):
        device = 'mobile'
    else:
        device = 'desktop'
    browser = next((name for name, pattern in BROWSERS if re.search(pattern, ua)), 'Other')
    system = next((name for name, pattern in SYSTEMS if re.search(pattern, ua)), 'Other')
    return {'device': device, 'browser': bot.group(1)[:32] if bot else browser, 'os': system,
            'is_bot': bool(bot) or not ua}


def network_prefix(address: str | None) -> str | None:
    """The network part of a client address: 147.32.10.0/24, 2001:718:2::/48."""
    try:
        ip = ipaddress.ip_address(address)
    except (TypeError, ValueError):
        return None
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return str(ipaddress.ip_network(f'{ip}/{24 if ip.version == 4 else 48}', strict=False))


def track(event: str, experiment_id: int | None = None, **details) -> None:
    """
    Names what the current request did, e.g. track('sample_evaluated', experiment_id=12, ai_percent=54.4).
    One event per request - a later call replaces the name and adds its details. The signed-in user is taken now,
    so a request that ends the session (logout) is still logged as that user's.
    """
    g.activity_event = event
    if experiment_id is not None:
        g.activity_experiment = experiment_id
    add_details(**details)
    if session.get('authenticated'):
        g.activity_user = session.get('user_id')


def add_details(**details) -> None:
    """Adds details to the current request's row without naming its event (e.g. the reCAPTCHA score)."""
    g.activity_details = {**g.get('activity_details', {}), **{k: v for k, v in details.items() if v is not None}}


class ActivityLog:
    def __init__(self, app=None):
        self.salt = ''
        self._queue = None
        self._pid = None
        self._lock = threading.Lock()
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        # the hash of visitors is keyed with the app's secret: without it the daily hashes could be recomputed
        self.salt = app.secret_key or ''
        if ENABLED:
            app.before_request(self._start)
            app.after_request(self._log)

    # -- per request --
    @staticmethod
    def _start():
        g.activity_start = time.perf_counter()

    def _log(self, response):
        try:
            if request.method not in ('HEAD', 'OPTIONS') and request.endpoint not in SKIPPED_ENDPOINTS:
                user_agent = request.headers.get('User-Agent', '')
                if not user_agent.startswith('kube-probe'):  # health checks of the cluster
                    self._enqueue(self._row(response, user_agent))
        except Exception as e:  # the log must never break a request
            print(f'Activity log: {e!r}')
        return response

    def _row(self, response, user_agent: str) -> dict:
        address = request.remote_addr or ''
        day = date.today().isoformat()
        visitor = hashlib.sha256(f'{self.salt}|{day}|{address}|{user_agent}'.encode()).hexdigest()[:16]
        if request.url_rule is not None:
            path = request.url_rule.rule
        else:  # unknown addresses (404) as requested - they show scans and broken links
            path = request.path
        referrer = urlsplit(request.referrer or '').hostname
        if referrer and referrer == request.host.split(':')[0]:
            referrer = None
        if 'activity_user' in g:
            user_id = g.activity_user
        else:
            user_id = session.get('user_id') if session.get('authenticated') else None  # guests have a random user_id
        event = g.get('activity_event')
        if event is None:
            if request.endpoint in AUTOSAVE_ENDPOINTS:
                event = 'autosave'
            elif request.method == 'GET' and response.mimetype == 'text/html':
                event = 'page'
            else:
                event = 'api'
        details = g.get('activity_details') or {}
        if event == 'autosave' and request.method == 'POST':
            details = {**details, 'fields': sorted(request.form.keys())[:20]} if request.form else details
        experiment_id = g.get('activity_experiment')
        if experiment_id is None and request.view_args and isinstance(request.view_args.get('id'), int):
            experiment_id = request.view_args['id']
        start = g.get('activity_start')
        return {
            'time': datetime.now(timezone.utc),
            'event': event[:40],
            'user_id': user_id,
            'visitor': visitor,
            'method': request.method[:8],
            'endpoint': (request.endpoint or '')[:64] or None,
            'path': path[:MAX_PATH],
            'status': response.status_code,
            'duration_ms': round((time.perf_counter() - start) * 1000) if start else None,
            'lang': (session.get('lang') or '')[:8] or None,
            **parse_user_agent(user_agent),
            'ip_prefix': network_prefix(address),
            'referrer': referrer[:128] if referrer else None,
            'experiment_id': experiment_id,
            'details': details or None,
        }

    # -- background writer (one per process: gunicorn workers fork after the app is imported) --
    def _enqueue(self, row: dict) -> None:
        if self._pid != os.getpid():
            with self._lock:
                if self._pid != os.getpid():
                    self._queue = queue.Queue(maxsize=QUEUE_LIMIT)
                    threading.Thread(target=self._write_loop, args=(self._queue,), name='activity-log', daemon=True).start()
                    atexit.register(self._flush, self._queue)  # rows of the last seconds when the worker stops
                    self._pid = os.getpid()
        try:
            self._queue.put_nowait(row)
        except queue.Full:
            pass

    @staticmethod
    def _take_batch(rows_queue: queue.Queue, wait: bool) -> list[dict]:
        rows = []
        deadline = time.monotonic() + FLUSH_SECONDS
        while len(rows) < BATCH_SIZE:
            try:
                if not wait:
                    rows.append(rows_queue.get_nowait())
                elif not rows:
                    rows.append(rows_queue.get())  # sleeps until there is something to write
                else:
                    rows.append(rows_queue.get(timeout=max(0.0, deadline - time.monotonic())))
            except queue.Empty:
                break
        return rows

    def _write_loop(self, rows_queue: queue.Queue) -> None:
        last_purge = 0.0
        while True:
            rows = self._take_batch(rows_queue, wait=True)
            if not db_api.insert_activity_rows(rows=rows):
                time.sleep(5)  # the database is unavailable (db_api printed why); these rows are lost
            if time.monotonic() - last_purge > PURGE_SECONDS:
                db_api.purge_activity_log(retention_days=RETENTION_DAYS)
                last_purge = time.monotonic()

    def _flush(self, rows_queue: queue.Queue) -> None:
        while rows := self._take_batch(rows_queue, wait=False):
            db_api.insert_activity_rows(rows=rows)
