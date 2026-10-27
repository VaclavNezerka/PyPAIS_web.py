-- Since the feature/manu-cam version the coating (wrapping) temperature is entered separately for the
-- aggregate and the binder, and the user defaults include a comment. The production database still had
-- the single column info_wrapping_temperature - saving a sample then failed with a database error.
-- The old value becomes the aggregate temperature; the old column is kept (no longer used by the app).
-- Must be applied BEFORE deploying the matching app version. Safe to run more than once.
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS info_wrapping_temperature_aggregate real;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS info_wrapping_temperature_binder real;
ALTER TABLE default_info ADD COLUMN IF NOT EXISTS info_wrapping_temperature_aggregate real;
ALTER TABLE default_info ADD COLUMN IF NOT EXISTS info_wrapping_temperature_binder real;
ALTER TABLE default_info ADD COLUMN IF NOT EXISTS info_comment character varying(1024);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'
               AND table_name = 'experiments' AND column_name = 'info_wrapping_temperature') THEN
        UPDATE experiments SET info_wrapping_temperature_aggregate = info_wrapping_temperature
         WHERE info_wrapping_temperature_aggregate IS NULL AND info_wrapping_temperature IS NOT NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'
               AND table_name = 'default_info' AND column_name = 'info_wrapping_temperature') THEN
        UPDATE default_info SET info_wrapping_temperature_aggregate = info_wrapping_temperature
         WHERE info_wrapping_temperature_aggregate IS NULL AND info_wrapping_temperature IS NOT NULL;
    END IF;
END $$;
