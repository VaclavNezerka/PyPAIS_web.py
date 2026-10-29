-- Developer accounts and the activity log behind their report (/developer).
-- Safe to run more than once. Run it before deploying the app version that writes the log (the app logs nothing
-- and the report page fails while the table is missing).
--
-- The developer role is granted only here, never in the app:
--   UPDATE users SET is_developer = true WHERE username = '<username>';
-- (the user sees the report link after the next login).

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_developer boolean NOT NULL DEFAULT false;

-- when accounts and companies were registered; NULL for those registered before this migration
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at timestamptz;
ALTER TABLE users ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE companies ADD COLUMN IF NOT EXISTS created_at timestamptz;
ALTER TABLE companies ALTER COLUMN created_at SET DEFAULT now();

-- One row per request (see activity.py). No IP addresses: visitor is a daily-changing hash of address and browser,
-- ip_prefix only the network part of the address (/24, /48). Rows older than ACTIVITY_RETENTION_DAYS are deleted.
CREATE TABLE IF NOT EXISTS activity_log (
    id bigserial PRIMARY KEY,
    time timestamptz NOT NULL DEFAULT now(),
    event varchar(40) NOT NULL,
    user_id integer REFERENCES users(id) ON DELETE SET NULL,
    visitor varchar(16),
    method varchar(8),
    endpoint varchar(64),
    path varchar(256),
    status smallint,
    duration_ms integer,
    lang varchar(8),
    device varchar(10),
    browser varchar(32),
    os varchar(24),
    is_bot boolean NOT NULL DEFAULT false,
    ip_prefix varchar(48),
    referrer varchar(128),
    experiment_id integer,  -- no foreign key: unfinished samples are deleted for good
    details jsonb
);
CREATE INDEX IF NOT EXISTS activity_log_time_idx ON activity_log (time);
CREATE INDEX IF NOT EXISTS activity_log_event_time_idx ON activity_log (event, time);
CREATE INDEX IF NOT EXISTS activity_log_user_time_idx ON activity_log (user_id, time);
