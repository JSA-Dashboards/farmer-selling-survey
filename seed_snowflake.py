"""
Seed JSA.FARMER_SURVEY from data/*.csv (run sql/setup.sql first).

    py seed_snowflake.py

Needs an .env in this folder with SNOWFLAKE_ACCOUNT / USER / ROLE / WAREHOUSE and a key
(SNOWFLAKE_PRIVATE_KEY_PATH [+ _PWD]). Use a role that can write the tables (ACCOUNTADMIN or SYSADMIN).
Replaces the contents of both tables.
"""
import os

import pandas as pd
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
assert load_dotenv(os.path.join(HERE, ".env")), "no .env in the app folder"

import db  # after load_dotenv so the credentials are visible

assert db.configured(), "SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER missing from .env"

monthly = pd.read_csv(os.path.join(HERE, "data", "monthly.csv"))
surveys = pd.read_csv(os.path.join(HERE, "data", "surveys.csv"), parse_dates=["date"])

conn = db.connect()
cur = conn.cursor()
print("connected as", cur.execute("select current_user(), current_role()").fetchone())
cur.execute("DELETE FROM MONTHLY")
cur.executemany("INSERT INTO MONTHLY (COMMODITY, KIND, CROP_YEAR, MONTH, PCT) VALUES (%s,%s,%s,%s,%s)",
                [tuple(r) for r in monthly[["commodity", "kind", "crop_year", "month", "pct"]].itertuples(index=False)])
cur.execute("DELETE FROM SURVEYS")
cur.executemany("INSERT INTO SURVEYS (COMMODITY, CROP_YEAR, SURVEY_DATE, PCT) VALUES (%s,%s,%s,%s)",
                [(r.commodity, r.crop_year, r.date.date(), float(r.pct)) for r in surveys.itertuples(index=False)])
for t in ("MONTHLY", "SURVEYS"):
    print(t, cur.execute(f"select count(*) from {t}").fetchone()[0], "rows")
conn.close()
