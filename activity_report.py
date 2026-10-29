"""The developers' report of the site's activity (/developer): the queries over activity_log (written by activity.py)
and the existing tables, and the geometry of its charts. The pages are templates/developer*.html.

Times are shown in REPORT_TIMEZONE. Samples, users and companies come from their own tables, so their totals reach
back before the activity log existed; everything people did (visits, logins, uploads, exports, errors) comes from
the log and starts with it.
"""
import math
import os
from datetime import datetime, timedelta, timezone

import pendulum as pdl
from flask_babel import get_locale, gettext as _, lazy_gettext

import db_api
from app_report_exporter import get_CSN_73_6161_classification

TZ = os.getenv('REPORT_TIMEZONE', 'Europe/Prague')
PERIODS = {1: lazy_gettext('24 hours'), 7: lazy_gettext('7 days'), 30: lazy_gettext('30 days'),
           90: lazy_gettext('90 days'), 365: lazy_gettext('1 year')}
DEFAULT_PERIOD = 30
EVENTS_PER_PAGE = 100
CSV_LIMIT = 100_000

# what the events mean, for the feed and the filter of the event log
EVENT_LABELS = {
    'page': lazy_gettext('Page view'),
    'api': lazy_gettext('Request'),
    'autosave': lazy_gettext('Autosave'),
    'login': lazy_gettext('Signed in'),
    'login_failed': lazy_gettext('Failed login'),
    'logout': lazy_gettext('Signed out'),
    'session_ended_blocked': lazy_gettext('Blocked user signed out'),
    'user_registered': lazy_gettext('User registered'),
    'company_registered': lazy_gettext('Company registered'),
    'company_confirmed': lazy_gettext('Company confirmed'),
    'email_confirmed': lazy_gettext('E-mail confirmed'),
    'invitation_accepted': lazy_gettext('Company admin set password'),
    'password_reset_requested': lazy_gettext('Password reset requested'),
    'password_reset': lazy_gettext('Password reset'),
    'password_changed': lazy_gettext('Password changed'),
    'email_change_requested': lazy_gettext('E-mail change requested'),
    'email_changed': lazy_gettext('E-mail changed'),
    'company_email_changed': lazy_gettext('Company e-mail changed'),
    'profile_edited': lazy_gettext('Profile edited'),
    'company_edited': lazy_gettext('Company details edited'),
    'user_blocked': lazy_gettext('User blocked'),
    'user_unblocked': lazy_gettext('User unblocked'),
    'admin_granted': lazy_gettext('Admin rights granted'),
    'admin_revoked': lazy_gettext('Admin rights removed'),
    'company_key_regenerated': lazy_gettext('Company key regenerated'),
    'link_expired': lazy_gettext('Expired link opened'),
    'link_invalid': lazy_gettext('Invalid link opened'),
    'recaptcha_failed': lazy_gettext('reCAPTCHA failed'),
    'contact_sent': lazy_gettext('Contact form sent'),
    'language_switched': lazy_gettext('Language switched'),
    'photo_uploaded': lazy_gettext('Photo uploaded'),
    'photo_rejected': lazy_gettext('Photo rejected'),
    'inference': lazy_gettext('AI detection'),
    'sample_evaluated': lazy_gettext('Sample evaluated'),
    'evaluation_refused': lazy_gettext('Evaluation refused (no sample)'),
    'sample_opened': lazy_gettext('Sample opened'),
    'sample_closed': lazy_gettext('New sample started'),
    'sample_deleted': lazy_gettext('Sample deleted'),
    'report_exported': lazy_gettext('Report exported'),
    'defaults_updated': lazy_gettext('Default values changed'),
}
# changes of accounts and rights - the audit trail of the security section
ACCOUNT_EVENTS = ('user_registered', 'company_registered', 'company_confirmed', 'email_confirmed', 'invitation_accepted',
                  'password_reset', 'password_changed', 'email_changed', 'company_email_changed', 'profile_edited',
                  'company_edited', 'user_blocked', 'user_unblocked', 'admin_granted', 'admin_revoked',
                  'company_key_regenerated', 'session_ended_blocked')
# what people did, without the noise of single requests - the feed of latest actions and the weekly pattern
ACTION_FILTER = "a.event NOT IN ('api', 'autosave')"
HUMAN_PAGE = "a.event = 'page' AND a.status = 200 AND NOT a.is_bot"
CLASSES = ('A', 'B', 'C', 'D', 'E', 'F', 'G')


def period_days(value) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PERIOD
    return days if days in PERIODS else DEFAULT_PERIOD


def _rows(query: str, params: dict) -> list[dict]:
    return db_api.fetch_dicts(query, params) or []


def _one(query: str, params: dict) -> dict:
    rows = _rows(query, params)
    return rows[0] if rows else {}


def _locale() -> str:
    return str(get_locale() or 'cs')


def _scope(include_developers: bool) -> str:
    # developers' own clicking around while testing is left out of the numbers unless asked for
    return '' if include_developers else ' AND (a.user_id IS NULL OR a.user_id NOT IN (SELECT id FROM users WHERE is_developer))'


def build_report(days: int, include_developers: bool) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    params = {'since': since, 'until': now, 'before': since - timedelta(days=days), 'tz': TZ,
              'since_local': pdl.instance(since).in_tz(TZ).naive(), 'days': days}
    scope = _scope(include_developers)
    log_info = _one("SELECT count(*) AS rows, min(time) AS first, pg_total_relation_size('activity_log') AS bytes "
                    "FROM activity_log", {})
    return {
        'days': days,
        'since': since,
        'include_developers': include_developers,
        'log': log_info,
        'kpis': kpis(params, scope),
        'timeline': timeline(params, scope, days),
        'heatmap': heatmap(params, scope),
        'latest': latest_actions(params, scope),
        'companies': companies(params, scope),
        'users': users(params, scope),
        'samples': samples(params, scope),
        'traffic': traffic(params, scope),
        'performance': performance(params, scope),
        'errors': errors(params, scope),
        'security': security(params, scope),
    }


# ---------- overview ----------
KPI_SQL = """
SELECT
  count(*) FILTER (WHERE {page}) AS page_views,
  count(DISTINCT a.visitor) FILTER (WHERE NOT a.is_bot) AS visitors,
  count(*) FILTER (WHERE {page} AND a.user_id IS NULL) AS guest_page_views,
  count(DISTINCT a.user_id) AS active_users,
  count(DISTINCT u.company) AS active_companies,
  count(*) FILTER (WHERE a.event = 'login') AS logins,
  count(*) FILTER (WHERE a.event = 'login_failed') AS failed_logins,
  count(*) FILTER (WHERE a.event = 'user_registered') AS registrations,
  count(*) FILTER (WHERE a.event = 'company_registered') AS company_registrations,
  count(*) FILTER (WHERE a.event = 'photo_uploaded') AS uploads,
  count(*) FILTER (WHERE a.event = 'photo_uploaded' AND a.user_id IS NULL) AS demo_uploads,
  count(*) FILTER (WHERE a.event = 'inference') AS inferences,
  count(*) FILTER (WHERE a.event = 'sample_evaluated') AS evaluations,
  count(*) FILTER (WHERE a.event = 'report_exported') AS reports,
  coalesce(sum((a.details->>'samples')::int) FILTER (WHERE a.event = 'report_exported'), 0) AS reported_samples,
  count(*) FILTER (WHERE a.status >= 500) AS server_errors,
  count(*) FILTER (WHERE a.status = 429) AS rate_limited,
  count(*) FILTER (WHERE NOT a.is_bot) AS requests,
  count(*) FILTER (WHERE a.is_bot) AS bot_requests,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY a.duration_ms) FILTER (WHERE {page}) AS page_ms,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY (a.details->>'ms')::numeric) FILTER (WHERE a.event = 'inference') AS inference_ms
FROM activity_log a LEFT JOIN users u ON u.id = a.user_id
WHERE a.time >= %({start})s AND a.time < %({end})s {scope}
"""

# (key, label, whether more is better: True, False, or None when neither)
KPI_TILES = (
    ('visitors', lazy_gettext('Visitors'), True),
    ('page_views', lazy_gettext('Page views'), True),
    ('active_users', lazy_gettext('Signed-in users'), True),
    ('active_companies', lazy_gettext('Active companies'), True),
    ('logins', lazy_gettext('Logins'), True),
    ('registrations', lazy_gettext('New users'), True),
    ('uploads', lazy_gettext('Photos uploaded'), True),
    ('demo_uploads', lazy_gettext('Demo uploads by guests'), True),
    ('evaluations', lazy_gettext('Samples evaluated'), True),
    ('reports', lazy_gettext('Reports exported'), True),
    ('server_errors', lazy_gettext('Server errors'), False),
    ('page_ms', lazy_gettext('Median page time'), False),
)


def kpis(params: dict, scope: str) -> list[dict]:
    current = _one(KPI_SQL.format(page=HUMAN_PAGE, start='since', end='until', scope=scope), params)
    previous = _one(KPI_SQL.format(page=HUMAN_PAGE, start='before', end='since', scope=scope), params)
    tiles = []
    for key, label, more_is_better in KPI_TILES:
        value, before = current.get(key), previous.get(key)
        delta = None
        if value is not None and before:
            delta = (float(value) - float(before)) / float(before) * 100
        tone = None
        if delta is not None and abs(delta) >= 0.5 and more_is_better is not None:
            tone = 'good' if (delta > 0) == more_is_better else 'bad'
        tiles.append({'key': key, 'label': label, 'value': value, 'previous': before, 'delta': delta, 'tone': tone,
                      'unit': 'ms' if key.endswith('_ms') else ''})
    return {'tiles': tiles, 'current': current, 'previous': previous}


TIMELINE_SERIES = (
    ('visitors', lazy_gettext('Visitors')),
    ('users', lazy_gettext('Signed-in users')),
    ('uploads', lazy_gettext('Photos uploaded')),
    ('evaluations', lazy_gettext('Samples evaluated')),
)


def timeline(params: dict, scope: str, days: int) -> dict:
    unit = 'hour' if days <= 2 else 'day' if days <= 92 else 'week'
    rows = _rows(f"""
        SELECT date_trunc(%(unit)s, a.time AT TIME ZONE %(tz)s) AS bucket,
          count(DISTINCT a.visitor) FILTER (WHERE NOT a.is_bot) AS visitors,
          count(DISTINCT a.user_id) AS users,
          count(*) FILTER (WHERE a.event = 'photo_uploaded') AS uploads,
          count(*) FILTER (WHERE a.event = 'sample_evaluated') AS evaluations
        FROM activity_log a WHERE a.time >= %(since)s {scope} GROUP BY 1 ORDER BY 1""", {**params, 'unit': unit})
    key_format = {'hour': 'YYYY-MM-DD HH', 'day': 'YYYY-MM-DD', 'week': 'YYYY-MM-DD'}[unit]
    by_bucket = {pdl.instance(r['bucket'], tz=TZ).format(key_format): r for r in rows}
    # every bucket of the period, also the empty ones
    end = pdl.now(TZ)
    cursor = pdl.instance(params['since']).in_tz(TZ).start_of(unit)
    buckets = []
    while cursor <= end:
        buckets.append(cursor)
        cursor = cursor.add(**{f'{unit}s': 1})
    label_format = {'hour': 'HH:mm', 'day': 'D. M.', 'week': 'D. M. YYYY'}[unit]
    tip_format = {'hour': 'D. M. HH:mm', 'day': 'dd D. M. YYYY', 'week': 'D. M. YYYY'}[unit]
    labels = [b.format(label_format) for b in buckets]
    week_of = _('Week of')
    tips = [b.format(tip_format, locale=_locale()) if unit != 'week' else week_of + ' ' + b.format(tip_format)
            for b in buckets]
    charts = []
    for key, label in TIMELINE_SERIES:
        values = [int(by_bucket.get(b.format(key_format), {}).get(key) or 0) for b in buckets]
        charts.append({'key': key, 'label': label, 'total': sum(values),
                       'chart': column_chart(labels, [[v] for v in values], tips),
                       'table': list(zip(tips, values))})
    return {'unit': unit, 'charts': charts}


def heatmap(params: dict, scope: str) -> dict:
    rows = _rows(f"""
        SELECT extract(isodow FROM a.time AT TIME ZONE %(tz)s)::int AS dow,
               extract(hour FROM a.time AT TIME ZONE %(tz)s)::int AS hour, count(*) AS n
        FROM activity_log a WHERE a.time >= %(since)s AND NOT a.is_bot AND {ACTION_FILTER} {scope} GROUP BY 1, 2""", params)
    counts = {(r['dow'], r['hour']): r['n'] for r in rows}
    top = max(counts.values(), default=0)
    weekdays = [lazy_gettext('Mon'), lazy_gettext('Tue'), lazy_gettext('Wed'), lazy_gettext('Thu'),
                lazy_gettext('Fri'), lazy_gettext('Sat'), lazy_gettext('Sun')]
    grid = []
    for dow in range(1, 8):
        cells = []
        for hour in range(24):
            n = counts.get((dow, hour), 0)
            # 5 steps of one hue, square-root scaled - a few busy hours would otherwise leave the rest blank
            level = 0 if n == 0 else max(1, math.ceil(math.sqrt(n / top) * 5))
            cells.append({'hour': hour, 'n': n, 'level': level})
        grid.append({'day': weekdays[dow - 1], 'cells': cells, 'total': sum(c['n'] for c in cells)})
    return {'grid': grid, 'max': top, 'total': sum(counts.values())}


def latest_actions(params: dict, scope: str, limit: int = 30) -> list[dict]:
    return _rows(f"""
        SELECT a.time, a.event, a.user_id, a.status, a.path, a.experiment_id, a.details, a.device, a.browser,
               u.first_name, u.last_name, u.username, c.company_name
        FROM activity_log a LEFT JOIN users u ON u.id = a.user_id LEFT JOIN companies c ON c.company_id = u.company
        WHERE a.time >= %(since)s AND {ACTION_FILTER} AND a.event <> 'page' AND NOT a.is_bot {scope}
        ORDER BY a.time DESC LIMIT {int(limit)}""", params)


# ---------- people ----------
def companies(params: dict, scope: str) -> list[dict]:
    return _rows(f"""
        SELECT c.company_id, c.company_name, c.e_mail, c.confirmed_by_admin, c.e_mail_confirmed, c.created_at,
               coalesce(m.users, 0) AS users, coalesce(m.confirmed_users, 0) AS confirmed_users, coalesce(m.admins, 0) AS admins,
               coalesce(x.samples, 0) AS samples, coalesce(x.finished, 0) AS finished, x.last_sample,
               coalesce(x.period_samples, 0) AS period_samples,
               coalesce(p.active_users, 0) AS active_users, coalesce(p.page_views, 0) AS page_views,
               coalesce(p.uploads, 0) AS uploads, coalesce(p.evaluations, 0) AS evaluations,
               coalesce(p.reports, 0) AS reports, p.last_seen
        FROM companies c
        LEFT JOIN (SELECT company, count(*) AS users, count(*) FILTER (WHERE e_mail_confirmed) AS confirmed_users,
                          count(*) FILTER (WHERE is_company_admin) AS admins FROM users GROUP BY company) m
               ON m.company = c.company_id
        LEFT JOIN (SELECT u.company, count(*) AS samples, count(*) FILTER (WHERE e.current_state = 'finished') AS finished,
                          max(e.time_stamp) AS last_sample, count(*) FILTER (WHERE e.time_stamp >= %(since_local)s) AS period_samples
                   FROM experiments e JOIN users u ON u.id = e.user_id
                   WHERE NOT coalesce(e.fake_deleted, false) GROUP BY u.company) x ON x.company = c.company_id
        LEFT JOIN (SELECT u.company, count(DISTINCT a.user_id) AS active_users,
                          count(*) FILTER (WHERE {HUMAN_PAGE}) AS page_views,
                          count(*) FILTER (WHERE a.event = 'photo_uploaded') AS uploads,
                          count(*) FILTER (WHERE a.event = 'sample_evaluated') AS evaluations,
                          count(*) FILTER (WHERE a.event = 'report_exported') AS reports, max(a.time) AS last_seen
                   FROM activity_log a JOIN users u ON u.id = a.user_id
                   WHERE a.time >= %(since)s {scope} GROUP BY u.company) p ON p.company = c.company_id
        ORDER BY p.last_seen DESC NULLS LAST, x.last_sample DESC NULLS LAST, c.company_name""", params)


def users(params: dict, scope: str) -> list[dict]:
    return _rows(f"""
        SELECT u.id, u.first_name, u.last_name, u.username, u.e_mail, u.company, c.company_name,
               coalesce(u.is_company_admin, false) AS is_admin, u.is_developer, coalesce(u.is_blocked, false) AS is_blocked,
               coalesce(u.e_mail_confirmed, false) AS e_mail_confirmed, u.created_at,
               coalesce(x.samples, 0) AS samples, coalesce(x.finished, 0) AS finished, x.last_sample,
               coalesce(p.page_views, 0) AS page_views, coalesce(p.logins, 0) AS logins,
               coalesce(p.uploads, 0) AS uploads, coalesce(p.evaluations, 0) AS evaluations,
               coalesce(p.reports, 0) AS reports, p.last_seen, p.devices, l.last_login
        FROM users u
        LEFT JOIN companies c ON c.company_id = u.company
        LEFT JOIN (SELECT user_id, count(*) AS samples, count(*) FILTER (WHERE current_state = 'finished') AS finished,
                          max(time_stamp) AS last_sample
                   FROM experiments WHERE NOT coalesce(fake_deleted, false) GROUP BY user_id) x ON x.user_id = u.id
        LEFT JOIN (SELECT a.user_id, count(*) FILTER (WHERE {HUMAN_PAGE}) AS page_views,
                          count(*) FILTER (WHERE a.event = 'login') AS logins,
                          count(*) FILTER (WHERE a.event = 'photo_uploaded') AS uploads,
                          count(*) FILTER (WHERE a.event = 'sample_evaluated') AS evaluations,
                          count(*) FILTER (WHERE a.event = 'report_exported') AS reports, max(a.time) AS last_seen,
                          string_agg(DISTINCT a.device, ', ') AS devices
                   FROM activity_log a WHERE a.time >= %(since)s AND a.user_id IS NOT NULL {scope} GROUP BY a.user_id) p
               ON p.user_id = u.id
        LEFT JOIN (SELECT user_id, max(time) AS last_login FROM activity_log WHERE event = 'login' GROUP BY user_id) l
               ON l.user_id = u.id
        ORDER BY p.last_seen DESC NULLS LAST, l.last_login DESC NULLS LAST, x.last_sample DESC NULLS LAST, u.id""", params)


# ---------- samples and the model ----------
def samples(params: dict, scope: str) -> dict:
    stored = _rows("""
        SELECT e.current_state, coalesce(e.fake_deleted, false) AS deleted, e.asphalt_ratio, e.expert_guess,
               e.inference_model
        FROM experiments e WHERE e.user_id IS NOT NULL AND e.time_stamp >= %(since_local)s""", params)
    live = [s for s in stored if not s['deleted']]
    finished = [s for s in live if s['current_state'] == 'finished']
    classes = {c: 0 for c in CLASSES}
    unclassifiable = 0
    for s in finished:
        if s['asphalt_ratio'] is None:
            continue
        cls = get_CSN_73_6161_classification(float(s['asphalt_ratio']) * 100)
        if cls in classes:
            classes[cls] += 1
        else:
            unclassifiable += 1
    class_rows = [{'label': c, 'n': n} for c, n in classes.items()]
    class_rows.append({'label': _('Unclassifiable'), 'n': unclassifiable})
    pairs = [(float(s['asphalt_ratio']) * 100, float(s['expert_guess']) * 100) for s in finished
             if s['asphalt_ratio'] is not None and s['expert_guess'] is not None]
    agreement = None
    if pairs:
        differences = [ai - expert for ai, expert in pairs]
        agreement = {
            'n': len(pairs),
            'mae': sum(abs(d) for d in differences) / len(pairs),
            'bias': sum(differences) / len(pairs),
            'within_10': sum(abs(d) <= 10 for d in differences) / len(pairs) * 100,
            'within_5': sum(abs(d) <= 5 for d in differences) / len(pairs) * 100,
        }
    model_counts = {}
    for s in live:
        name = (s['inference_model'] or '').removesuffix('.pth') or '—'
        model_counts[name] = model_counts.get(name, 0) + 1

    log = _one(f"""
        SELECT count(*) FILTER (WHERE a.event = 'photo_uploaded') AS uploads,
          count(*) FILTER (WHERE a.event = 'photo_uploaded' AND a.details->>'source' = 'camera') AS camera_uploads,
          count(*) FILTER (WHERE a.event = 'photo_uploaded' AND a.user_id IS NULL) AS demo_uploads,
          count(*) FILTER (WHERE a.event = 'photo_rejected') AS rejected,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY (a.details->>'megapixels')::numeric)
            FILTER (WHERE a.event = 'photo_uploaded') AS megapixels,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY (a.details->>'kb')::numeric) FILTER (WHERE a.event = 'photo_uploaded') AS kb,
          count(*) FILTER (WHERE a.event = 'inference') AS inferences,
          count(*) FILTER (WHERE a.event = 'inference' AND a.user_id IS NULL) AS demo_inferences,
          count(*) FILTER (WHERE a.event = 'inference' AND a.details->>'sample_found' = 'false') AS no_sample,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY (a.details->>'ms')::numeric) FILTER (WHERE a.event = 'inference') AS ms_p50,
          percentile_cont(0.95) WITHIN GROUP (ORDER BY (a.details->>'ms')::numeric) FILTER (WHERE a.event = 'inference') AS ms_p95,
          max((a.details->>'ms')::numeric) FILTER (WHERE a.event = 'inference') AS ms_max,
          count(*) FILTER (WHERE a.event = 'evaluation_refused') AS refused,
          count(*) FILTER (WHERE a.event = 'sample_opened') AS opened,
          count(*) FILTER (WHERE a.event = 'sample_opened' AND a.details->>'own' = 'false') AS opened_colleague,
          count(*) FILTER (WHERE a.event = 'sample_deleted') AS deleted,
          count(*) FILTER (WHERE a.event = 'autosave') AS autosaves,
          count(*) FILTER (WHERE a.event = 'report_exported') AS reports,
          coalesce(sum((a.details->>'samples')::int) FILTER (WHERE a.event = 'report_exported'), 0) AS reported_samples,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY a.duration_ms) FILTER (WHERE a.event = 'report_exported') AS report_ms
        FROM activity_log a WHERE a.time >= %(since)s {scope}""", params)
    inference_models = _rows(f"""
        SELECT coalesce(a.details->>'model', '—') AS label, count(*) AS n FROM activity_log a
        WHERE a.time >= %(since)s AND a.event = 'inference' {scope} GROUP BY 1 ORDER BY 2 DESC LIMIT 8""", params)
    for row in inference_models:
        row['label'] = row['label'].removesuffix('.pth')
    reporters = _rows(f"""
        SELECT u.first_name, u.last_name, u.username, c.company_name, count(*) AS reports,
               coalesce(sum((a.details->>'samples')::int), 0) AS samples
        FROM activity_log a JOIN users u ON u.id = a.user_id LEFT JOIN companies c ON c.company_id = u.company
        WHERE a.time >= %(since)s AND a.event = 'report_exported' {scope}
        GROUP BY u.id, u.first_name, u.last_name, u.username, c.company_name ORDER BY reports DESC LIMIT 10""", params)
    monthly = _rows("""
        SELECT date_trunc('month', time_stamp) AS month,
               count(*) FILTER (WHERE current_state = 'finished') AS finished,
               count(*) FILTER (WHERE current_state <> 'finished') AS unfinished
        FROM experiments WHERE user_id IS NOT NULL AND NOT coalesce(fake_deleted, false) AND time_stamp IS NOT NULL
        GROUP BY 1 ORDER BY 1""", {})
    month_labels, month_values, month_tips = [], [], []
    if monthly:
        by_month = {r['month'].strftime('%Y-%m'): r for r in monthly}
        cursor = pdl.datetime(monthly[0]['month'].year, monthly[0]['month'].month, 1)
        last = pdl.now(TZ)
        while (cursor.year, cursor.month) <= (last.year, last.month):
            row = by_month.get(cursor.format('YYYY-MM'), {})
            month_labels.append(cursor.format('M/YY'))
            month_values.append([int(row.get('finished') or 0), int(row.get('unfinished') or 0)])
            month_tips.append(cursor.format('MMMM YYYY', locale=_locale()))
            cursor = cursor.add(months=1)
    return {
        'created': len(live), 'finished': len(finished), 'unfinished': len(live) - len(finished),
        'deleted': len(stored) - len(live),
        'classes': bars(class_rows), 'models': bars([{'label': k, 'n': v} for k, v in
                                                     sorted(model_counts.items(), key=lambda kv: -kv[1])]),
        'inference_models': bars(inference_models), 'agreement': agreement, 'log': log, 'reporters': reporters,
        'monthly': column_chart(month_labels, month_values, month_tips, width=1220) if month_values else None,
        'monthly_table': list(zip(month_tips, month_values)),
    }


# ---------- traffic ----------
def traffic(params: dict, scope: str) -> dict:
    def top(column: str, where: str = HUMAN_PAGE, limit: int = 10) -> dict:
        return bars(_rows(f"""
            SELECT coalesce({column}::text, '—') AS label, count(*) AS n, count(DISTINCT a.visitor) AS visitors
            FROM activity_log a WHERE a.time >= %(since)s AND {where} {scope}
            GROUP BY 1 ORDER BY 2 DESC LIMIT {int(limit)}""", params))
    return {
        'pages': top('a.path', limit=15),
        'referrers': top('a.referrer', where='a.referrer IS NOT NULL AND NOT a.is_bot', limit=12),
        'languages': top('a.lang'),
        'devices': top('a.device'),
        'browsers': top('a.browser'),
        'systems': top('a.os'),
        'bots': top('a.browser', where='a.is_bot', limit=10),
        'guests': top("CASE WHEN a.user_id IS NULL THEN 'guest' ELSE 'user' END"),
    }


# ---------- operations ----------
def performance(params: dict, scope: str) -> list[dict]:
    return _rows(f"""
        SELECT a.endpoint, count(*) AS n,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY a.duration_ms) AS p50,
          percentile_cont(0.95) WITHIN GROUP (ORDER BY a.duration_ms) AS p95,
          max(a.duration_ms) AS max, sum(a.duration_ms) AS total,
          count(*) FILTER (WHERE a.status BETWEEN 400 AND 499) AS client_errors,
          count(*) FILTER (WHERE a.status >= 500) AS server_errors
        FROM activity_log a WHERE a.time >= %(since)s AND a.endpoint IS NOT NULL {scope}
        GROUP BY 1 ORDER BY total DESC NULLS LAST LIMIT 30""", params)


def errors(params: dict, scope: str) -> dict:
    return {
        'server': _rows(f"""
            SELECT a.time, a.method, a.path, a.status, a.details, a.user_id, u.username, a.browser, a.device
            FROM activity_log a LEFT JOIN users u ON u.id = a.user_id
            WHERE a.time >= %(since)s AND a.status >= 500 {scope} ORDER BY a.time DESC LIMIT 30""", params),
        'by_status': _rows(f"""
            SELECT a.status, count(*) AS n, count(*) FILTER (WHERE a.is_bot) AS bots FROM activity_log a
            WHERE a.time >= %(since)s AND a.status >= 400 {scope} GROUP BY 1 ORDER BY 1""", params),
        'not_found': bars(_rows(f"""
            SELECT a.path AS label, count(*) AS n FROM activity_log a
            WHERE a.time >= %(since)s AND a.status = 404 {scope} GROUP BY 1 ORDER BY 2 DESC LIMIT 12""", params)),
    }


def security(params: dict, scope: str) -> dict:
    return {
        'failed_logins': bars(_rows(f"""
            SELECT coalesce(a.details->>'reason', '—') AS label, count(*) AS n FROM activity_log a
            WHERE a.time >= %(since)s AND a.event = 'login_failed' {scope} GROUP BY 1 ORDER BY 2 DESC""", params)),
        'networks': _rows(f"""
            SELECT a.ip_prefix, count(*) FILTER (WHERE a.event = 'login_failed') AS failed_logins,
                   count(*) FILTER (WHERE a.event = 'recaptcha_failed') AS recaptcha_failed,
                   count(*) FILTER (WHERE a.status = 429) AS rate_limited,
                   count(*) FILTER (WHERE a.status = 404) AS not_found, max(a.time) AS last
            FROM activity_log a
            WHERE a.time >= %(since)s AND (a.event IN ('login_failed', 'recaptcha_failed') OR a.status IN (404, 429)) {scope}
            GROUP BY 1 ORDER BY count(*) DESC LIMIT 12""", params),
        'recaptcha': _one(f"""
            SELECT count(*) AS checks, count(*) FILTER (WHERE (a.details->>'recaptcha')::numeric < 0.85) AS low,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY (a.details->>'recaptcha')::numeric) AS median,
                   min((a.details->>'recaptcha')::numeric) AS min
            FROM activity_log a WHERE a.time >= %(since)s AND a.details ? 'recaptcha' {scope}""", params),
        'counts': _one(f"""
            SELECT count(*) FILTER (WHERE a.event = 'recaptcha_failed') AS recaptcha_failed,
                   count(*) FILTER (WHERE a.event = 'password_reset_requested') AS reset_requests,
                   count(*) FILTER (WHERE a.event = 'password_reset') AS resets,
                   count(*) FILTER (WHERE a.event IN ('link_expired', 'link_invalid')) AS bad_links,
                   count(*) FILTER (WHERE a.status = 429) AS rate_limited,
                   count(*) FILTER (WHERE a.status = 403) AS forbidden
            FROM activity_log a WHERE a.time >= %(since)s {scope}""", params),
        'audit': _rows(f"""
            SELECT a.time, a.event, a.details, a.user_id, u.first_name, u.last_name, u.username, c.company_name
            FROM activity_log a LEFT JOIN users u ON u.id = a.user_id LEFT JOIN companies c ON c.company_id = u.company
            WHERE a.time >= %(since)s AND a.event = ANY(%(account_events)s) {scope}
            ORDER BY a.time DESC LIMIT 40""", {**params, 'account_events': list(ACCOUNT_EVENTS)}),
    }


# ---------- the event log ----------
def event_filters(args) -> dict:
    def as_int(name):
        try:
            return int(args.get(name))
        except (TypeError, ValueError):
            return None
    status = args.get('status')
    return {
        'days': period_days(args.get('days')),
        'event': args.get('event') if args.get('event') in EVENT_LABELS else None,
        'user': as_int('user'),
        'company': as_int('company'),
        'experiment': as_int('experiment'),
        'status': status if status in ('2', '3', '4', '5') else None,
        'path': (args.get('path') or '').strip()[:100] or None,
        'bots': args.get('bots') == '1',
    }


def _event_where(filters: dict) -> tuple[str, dict]:
    since = datetime.now(timezone.utc) - timedelta(days=filters['days'])
    where, params = ['a.time >= %(since)s'], {'since': since}
    if filters['event']:
        where.append('a.event = %(event)s')
        params['event'] = filters['event']
    if filters['user'] is not None:
        where.append('a.user_id = %(user)s')
        params['user'] = filters['user']
    if filters['company'] is not None:
        where.append('u.company = %(company)s')
        params['company'] = filters['company']
    if filters['experiment'] is not None:
        where.append('a.experiment_id = %(experiment)s')
        params['experiment'] = filters['experiment']
    if filters['status']:
        where.append('a.status >= %(status_from)s AND a.status < %(status_to)s')
        params.update(status_from=int(filters['status']) * 100, status_to=int(filters['status']) * 100 + 100)
    if filters['path']:
        where.append("(a.path ILIKE %(path)s OR a.endpoint ILIKE %(path)s)")
        params['path'] = '%' + filters['path'].replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    if not filters['bots']:
        where.append('NOT a.is_bot')
    return ' AND '.join(where), params


EVENT_SELECT = """
    SELECT a.id, a.time, a.event, a.user_id, u.username, u.first_name, u.last_name, c.company_name, a.visitor, a.method,
           a.endpoint, a.path, a.status, a.duration_ms, a.lang, a.device, a.browser, a.os, a.is_bot, a.ip_prefix,
           a.referrer, a.experiment_id, a.details
    FROM activity_log a LEFT JOIN users u ON u.id = a.user_id LEFT JOIN companies c ON c.company_id = u.company"""


def events(filters: dict, page: int) -> tuple[list[dict], int]:
    where, params = _event_where(filters)
    total = _one(f"SELECT count(*) AS n FROM activity_log a LEFT JOIN users u ON u.id = a.user_id WHERE {where}", params).get('n', 0)
    offset = (max(1, page) - 1) * EVENTS_PER_PAGE
    rows = _rows(f"{EVENT_SELECT} WHERE {where} ORDER BY a.time DESC, a.id DESC LIMIT {EVENTS_PER_PAGE} OFFSET {int(offset)}", params)
    return rows, total


def events_for_csv(filters: dict) -> list[dict]:
    where, params = _event_where(filters)
    return _rows(f"{EVENT_SELECT} WHERE {where} ORDER BY a.time DESC, a.id DESC LIMIT {CSV_LIMIT}", params)


def filter_choices() -> dict:
    return {
        'events': sorted(((key, str(label)) for key, label in EVENT_LABELS.items()), key=lambda kv: kv[1].lower()),
        'users': _rows("SELECT u.id, u.first_name, u.last_name, u.username, c.company_name FROM users u "
                       "LEFT JOIN companies c ON c.company_id = u.company ORDER BY c.company_name, u.last_name, u.first_name", {}),
        'companies': _rows("SELECT company_id, company_name FROM companies ORDER BY company_name", {}),
    }


# ---------- chart geometry (rendered by templates/macros/charts.html) ----------
def nice_max(value: float) -> tuple[float, float]:
    """A round top of the y axis and its tick step, e.g. 37 -> (40, 10)."""
    if value <= 0:
        return 1, 1
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (0.1, 0.2, 0.5, 1, 2, 5, 10):
        tick = round(step * magnitude, 9)
        if tick < 1:  # counts - no fractional ticks
            continue
        if value / tick <= 4:
            return math.ceil(value / tick) * tick, tick
    return value, value


def column_chart(labels: list[str], values: list[list[int]], tips: list[str], width: int = 640, height: int = 168) -> dict:
    """
    Columns of one series, or of a stack of two (values: one list per column, the emphasised part first).
    Bars at most 24 px wide with a 2 px gap, rounded data ends; y ticks on round numbers; every n-th x label.
    """
    left, right, top, bottom = 34, 6, 20, 24  # the top leaves room for the label of the highest column
    plot_w, plot_h = width - left - right, height - top - bottom
    totals = [sum(v) for v in values]
    y_max, tick = nice_max(max(totals, default=0))
    n = max(1, len(values))
    band = plot_w / n
    bar_w = max(1.0, min(24.0, band - 2 if band > 4 else band * 0.7))
    columns = []
    for i, (parts, label, tip) in enumerate(zip(values, labels, tips)):
        x = left + i * band + (band - bar_w) / 2
        y_base = top + plot_h
        segments = []
        for k, value in enumerate(parts):
            h = plot_h * value / y_max if y_max else 0
            if h <= 0:
                continue
            gap = 2 if segments else 0  # surface gap between stacked parts
            y = y_base - h
            segments.append({'part': k, 'path': _bar_path(x, y, bar_w, max(0.0, h - gap),
                                                          rounded=k == len(parts) - 1 or not any(parts[k + 1:]))})
            y_base = y
        columns.append({'x': x, 'w': bar_w, 'top': y_base, 'band_x': left + i * band, 'band_w': band, 'segments': segments,
                        'label': label, 'tip': tip, 'values': parts, 'total': sum(parts)})
    ticks = []
    value = 0.0
    while value <= y_max + 1e-9:
        ticks.append({'y': top + plot_h - plot_h * value / y_max, 'label': _compact(value)})
        value += tick
    every = max(1, math.ceil(n / 8))
    x_labels = [{'x': c['band_x'] + c['band_w'] / 2, 'label': c['label']} for i, c in enumerate(columns) if i % every == 0]
    peak = max(range(len(totals)), key=lambda i: totals[i]) if totals and max(totals) > 0 else None
    return {'width': width, 'height': height, 'left': left, 'right': width - right, 'baseline': top + plot_h,
            'ticks': ticks, 'columns': columns, 'x_labels': x_labels, 'stacked': any(len(v) > 1 for v in values),
            'peak': columns[peak] | {'value': totals[peak]} if peak is not None else None}


def _bar_path(x: float, y: float, w: float, h: float, rounded: bool) -> str:
    r = min(4.0, w / 2, h) if rounded else 0.0
    if r <= 0:
        return f'M{x:.1f},{y + h:.1f}V{y:.1f}H{x + w:.1f}V{y + h:.1f}Z'
    return (f'M{x:.1f},{y + h:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}'
            f'H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{y + h:.1f}Z')


def _compact(value: float) -> str:
    if value >= 1_000_000:
        return f'{value / 1_000_000:g}M'
    if value >= 1000:
        return f'{value / 1000:g}K'
    return f'{value:g}'


def bars(rows: list[dict]) -> dict:
    """Rows with 'label' and 'n' for a list of horizontal bars (their share of the largest)."""
    top = max((r['n'] for r in rows), default=0)
    total = sum(r['n'] for r in rows)
    return {'rows': [{**r, 'share': r['n'] / top if top else 0, 'percent': r['n'] / total * 100 if total else 0}
                     for r in rows], 'total': total}
