-- Add applicant_data storage to investigations table
-- Allows structured applicant/case data to be stored and retrieved for analysis

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS applicant_data JSONB DEFAULT NULL;

-- Index for fast filtering on applicant_data presence
CREATE INDEX IF NOT EXISTS idx_investigations_has_applicant_data
    ON investigations (tenant_id, created_at DESC)
    WHERE applicant_data IS NOT NULL;

COMMENT ON COLUMN investigations.applicant_data IS 'Structured applicant/case data JSON for bias detection, demographic analysis, and compliance assessment. Example: {"applicant_id", "race", "age", "income", "loan_amount", "credit_score", "denied", "denial_reason"}';
