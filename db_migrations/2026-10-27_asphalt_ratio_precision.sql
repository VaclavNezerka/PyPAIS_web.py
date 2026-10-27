-- The AI assessment (asphalt_ratio, 0-1) was stored with two decimals only, so the sample records and the
-- PDF report showed 54.0 % for a sample the app had evaluated as 53.8 %. Five decimals keep the value as
-- computed. Values stored before keep their two decimals. Safe to run more than once, before or after
-- deploying the app.
ALTER TABLE experiments ALTER COLUMN asphalt_ratio TYPE numeric(6,5);
