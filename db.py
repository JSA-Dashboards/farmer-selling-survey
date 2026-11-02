"""
db.py -- Snowflake storage for the farmer selling survey (JSA.FARMER_SURVEY).

Credentials come from st.secrets, then the environment, then a local .env (dev only).
With no credentials the app falls back to the CSVs in data/, so it still runs locally.
Do not set SNOWFLAKE_SCHEMA or SNOWFLAKE_DATABASE: the schema is pinned here.
"""
import os

import pandas as pd
import streamlit as st

try:  # local dev only; Cloud uses secrets
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

DB, SCHEMA = "JSA", "FARMER_SURVEY"


def _secret(key: str, default: str = "") -> str:
    try:
        v = st.secrets.get(key, "")
        if v:
            return str(v).strip()
    except Exception:
        pass
    return os.environ.get(key, default).strip()


def configured() -> bool:
    return bool(_secret("SNOWFLAKE_ACCOUNT") and _secret("SNOWFLAKE_USER"))


def _private_key():
    pem, path = _secret("SNOWFLAKE_PRIVATE_KEY"), _secret("SNOWFLAKE_PRIVATE_KEY_PATH")
    if not pem and not path:
        return None
    from cryptography.hazmat.primitives import serialization
    data = open(path, "rb").read() if path else pem.encode()
    pwd = _secret("SNOWFLAKE_PRIVATE_KEY_PWD") or None
    key = serialization.load_pem_private_key(data, password=pwd.encode() if pwd else None)
    return key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def connect():
    import snowflake.connector
    kw = dict(account=_secret("SNOWFLAKE_ACCOUNT"), user=_secret("SNOWFLAKE_USER"),
              role=_secret("SNOWFLAKE_ROLE") or None, warehouse=_secret("SNOWFLAKE_WAREHOUSE") or None,
              database=DB, schema=SCHEMA, login_timeout=30)
    pkey = _private_key()
    if pkey is not None:
        kw["private_key"] = pkey
    else:
        kw["password"] = _secret("SNOWFLAKE_PASSWORD")
    return snowflake.connector.connect(**kw)


def _query(sql: str) -> pd.DataFrame:
    conn = connect()
    try:
        df = pd.read_sql(sql, conn)
    finally:
        conn.close()
    df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=600, show_spinner="Loading survey data…")
def load_monthly() -> pd.DataFrame:
    if not configured():
        return pd.read_csv("data/monthly.csv")
    return _query("SELECT COMMODITY, KIND, CROP_YEAR, MONTH, PCT FROM MONTHLY")


@st.cache_data(ttl=600, show_spinner=False)
def load_surveys() -> pd.DataFrame:
    if not configured():
        return pd.read_csv("data/surveys.csv", parse_dates=["date"])
    df = _query("SELECT COMMODITY, CROP_YEAR, SURVEY_DATE, PCT FROM SURVEYS")
    df = df.rename(columns={"survey_date": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df


def save_monthly(rows: pd.DataFrame) -> None:
    """Upsert rows (commodity, kind, crop_year, month, pct); CSV when Snowflake is not configured."""
    keys = ["commodity", "kind", "crop_year", "month"]
    if not configured():
        merged = pd.concat([pd.read_csv("data/monthly.csv"), rows]).drop_duplicates(keys, keep="last")
        merged.to_csv("data/monthly.csv", index=False)
        return
    conn = connect()
    try:
        cur = conn.cursor()
        for r in rows.itertuples(index=False):
            cur.execute(
                "MERGE INTO MONTHLY t USING (SELECT %s AS COMMODITY, %s AS KIND, %s AS CROP_YEAR, %s AS MONTH, "
                "%s AS PCT) s ON t.COMMODITY = s.COMMODITY AND t.KIND = s.KIND AND t.CROP_YEAR = s.CROP_YEAR "
                "AND t.MONTH = s.MONTH WHEN MATCHED THEN UPDATE SET PCT = s.PCT, UPDATED_AT = CURRENT_TIMESTAMP() "
                "WHEN NOT MATCHED THEN INSERT (COMMODITY, KIND, CROP_YEAR, MONTH, PCT) "
                "VALUES (s.COMMODITY, s.KIND, s.CROP_YEAR, s.MONTH, s.PCT)",
                (r.commodity, r.kind, r.crop_year, r.month, float(r.pct)))
    finally:
        conn.close()


# -- client survey: access codes + monthly responses (Snowflake only) ----------------------------
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def _hash(code: str) -> str:
    import hashlib
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def _run(sql: str, params=None, fetch: bool = False):
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur.fetchall() if fetch else None
    finally:
        conn.close()


def client_for_code(code: str):
    """(client_id, name) for an active client's access code, else None."""
    rows = _run("SELECT CLIENT_ID, NAME FROM CLIENTS WHERE CODE_HASH = %s AND ACTIVE", [_hash(code)], fetch=True)
    return rows[0] if rows else None


def list_clients() -> pd.DataFrame:
    return _query("SELECT CLIENT_ID, NAME, ACTIVE, CREATED_AT FROM CLIENTS ORDER BY CREATED_AT")


def add_client(name: str) -> str:
    """Create a client and return its access code; only the hash is stored, so this is the one time it is visible."""
    import secrets
    import uuid
    code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
    _run("INSERT INTO CLIENTS (CLIENT_ID, NAME, CODE_HASH, ACTIVE) VALUES (%s, %s, %s, TRUE)",
         [uuid.uuid4().hex, name.strip(), _hash(code)])
    return code


def set_client_active(client_id: str, active: bool) -> None:
    _run("UPDATE CLIENTS SET ACTIVE = %s WHERE CLIENT_ID = %s", [active, client_id])


def load_client_responses(client_id: str, month_key: str) -> pd.DataFrame:
    conn = connect()
    try:
        df = pd.read_sql("SELECT COMMODITY, KIND, CROP_YEAR, PCT FROM RESPONSES WHERE CLIENT_ID = %s AND MONTH_KEY = %s",
                         conn, params=[client_id, month_key])
    finally:
        conn.close()
    df.columns = [c.lower() for c in df.columns]
    return df


def save_responses(client_id: str, month_key: str, rows: pd.DataFrame) -> None:
    """Upsert one client's answers (commodity, kind, crop_year, pct) for a month; resubmitting overwrites."""
    conn = connect()
    try:
        cur = conn.cursor()
        for r in rows.itertuples(index=False):
            cur.execute(
                "MERGE INTO RESPONSES t USING (SELECT %s AS CLIENT_ID, %s AS MONTH_KEY, %s AS COMMODITY, %s AS KIND, "
                "%s AS CROP_YEAR, %s AS PCT) s ON t.CLIENT_ID = s.CLIENT_ID AND t.MONTH_KEY = s.MONTH_KEY "
                "AND t.COMMODITY = s.COMMODITY AND t.KIND = s.KIND "
                "WHEN MATCHED THEN UPDATE SET CROP_YEAR = s.CROP_YEAR, PCT = s.PCT, SUBMITTED_AT = CURRENT_TIMESTAMP() "
                "WHEN NOT MATCHED THEN INSERT (CLIENT_ID, MONTH_KEY, COMMODITY, KIND, CROP_YEAR, PCT) "
                "VALUES (s.CLIENT_ID, s.MONTH_KEY, s.COMMODITY, s.KIND, s.CROP_YEAR, s.PCT)",
                (client_id, month_key, r.commodity, r.kind, r.crop_year, float(r.pct)))
    finally:
        conn.close()


def load_responses(month_key: str) -> pd.DataFrame:
    """Every client's answers for a month, with the client name (admin use)."""
    conn = connect()
    try:
        df = pd.read_sql(
            "SELECT c.NAME, r.COMMODITY, r.KIND, r.CROP_YEAR, r.PCT, r.SUBMITTED_AT FROM RESPONSES r "
            "JOIN CLIENTS c ON c.CLIENT_ID = r.CLIENT_ID WHERE r.MONTH_KEY = %s ORDER BY c.NAME, r.COMMODITY, r.KIND",
            conn, params=[month_key])
    finally:
        conn.close()
    df.columns = [c.lower() for c in df.columns]
    return df
