-- Anonymous monthly survey responses. Run once as ACCOUNTADMIN (after setup.sql).
-- Replaces the per-client CLIENTS / RESPONSES design (sql/client_survey.sql, dropped): answers carry no names.
-- If you already ran an earlier version of this script (it has no data yet), drop its table first, because
-- CREATE TABLE IF NOT EXISTS will not change an existing layout:
--   DROP TABLE IF EXISTS JSA.FARMER_SURVEY.SURVEY_RESPONSES;
CREATE TABLE IF NOT EXISTS JSA.FARMER_SURVEY.SURVEY_RESPONSES (
    RESPONSE_ID  VARCHAR NOT NULL,
    MONTH_KEY    VARCHAR NOT NULL,         -- YYYY-MM
    COMMODITY    VARCHAR NOT NULL,         -- Corn | Soybeans
    CROP_YEAR    VARCHAR NOT NULL,         -- e.g. 26/27
    PCT_LO       NUMBER(3,0),              -- chosen 5% range, e.g. 26 and 30
    PCT_HI       NUMBER(3,0),
    PRICE_TARGET NUMBER(10,4),             -- next futures price point that "buys the next 5%"
    LOCATION     VARCHAR,
    SUBMITTED_ON DATE DEFAULT CURRENT_DATE(),  -- date only, so a location + exact time can't single out a respondent
    PRIMARY KEY (RESPONSE_ID)
);

-- The survey app (FARMER_SURVEY_ROLE) and the admin portal mirror (ADMIN_PORTAL_ROLE) both serve the form and Admin.
GRANT SELECT, INSERT ON TABLE JSA.FARMER_SURVEY.SURVEY_RESPONSES TO ROLE FARMER_SURVEY_ROLE;
GRANT SELECT, INSERT ON TABLE JSA.FARMER_SURVEY.SURVEY_RESPONSES TO ROLE ADMIN_PORTAL_ROLE;

-- Only if sql/client_survey.sql was already run, remove its tables (nothing uses them now):
-- DROP TABLE IF EXISTS JSA.FARMER_SURVEY.CLIENTS;
-- DROP TABLE IF EXISTS JSA.FARMER_SURVEY.RESPONSES;
