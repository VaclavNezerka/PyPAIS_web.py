-- Sample designation entered by the user ("Označení vzorku"), shown in the sample records table and the PDF report.
-- Must be applied BEFORE deploying the matching app version: new experiments are inserted with this column.
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS info_sample_label varchar(256);
