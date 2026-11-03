-- Anonymous monthly survey responses. Run once as ACCOUNTADMIN (after setup.sql).
-- Replaces the per-client CLIENTS / RESPONSES design (sql/client_survey.sql, dropped): answers carry no names.
CREATE TABLE IF NOT EXISTS JSA.FARMER_SURVEY.SURVEY_RESPONSES (
    RESPONSE_ID  VARCHAR NOT NULL,
    MONTH_KEY    VARCHAR NOT NULL,         -- YYYY-MM
    COMMODITY    VARCHAR NOT NULL,         -- Corn | Soybeans
    CROP_YEAR    VARCHAR NOT NULL,         -- e.g. 26/27
    PCT_LO       NUMBER(3,0),              -- chosen 5% range, e.g. 26 and 30
    PCT_HI       NUMBER(3,0),
    PRICE_TARGET FLOAT,                    -- next futures price point that "buys the next 5%"
    LOCATION     VARCHAR,
    SUBMITTED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (RESPONSE_ID)
);

-- The survey app (FARMER_SURVEY_ROLE) and the admin portal mirror (ADMIN_PORTAL_ROLE) both serve the form and Admin.
GRANT SELECT, INSERT ON TABLE JSA.FARMER_SURVEY.SURVEY_RESPONSES TO ROLE FARMER_SURVEY_ROLE;
GRANT SELECT, INSERT ON TABLE JSA.FARMER_SURVEY.SURVEY_RESPONSES TO ROLE ADMIN_PORTAL_ROLE;

-- Only if sql/client_survey.sql was already run, remove its tables (nothing uses them now):
-- DROP TABLE IF EXISTS JSA.FARMER_SURVEY.CLIENTS;
-- DROP TABLE IF EXISTS JSA.FARMER_SURVEY.RESPONSES;
