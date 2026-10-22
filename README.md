# Farmer Selling Survey Dashboard

Streamlit dashboard of the share of the crop farmers report sold (corn, soybeans, HRW/SRW/HRS wheat), current-crop and new-crop.

Tabs: Snapshot, Monthly view, Data, Admin (add monthly results).

Data: `JSA.FARMER_SURVEY` in Snowflake (`MONTHLY`, `SURVEYS`). Create with `sql/setup.sql`, seed with `py seed_snowflake.py` (needs a local `.env`). With no Snowflake credentials the app reads `data/*.csv`.

Secrets: SNOWFLAKE_ACCOUNT/USER/ROLE (FARMER_SURVEY_ROLE)/WAREHOUSE, SNOWFLAKE_PRIVATE_KEY (+ _PWD), optional EDIT_PASSWORD for the Admin tab. Do not set SNOWFLAKE_SCHEMA or SNOWFLAKE_DATABASE.

Rebuild the CSVs from the workbook: `py build_data.py "<path to xlsx>"`.
