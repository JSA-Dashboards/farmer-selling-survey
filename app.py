"""
Farmer Selling Survey Dashboard
Share of the crop farmers report sold, by crop year: current-crop and new-crop forward sales
for corn, soybeans and HRW / SRW / HRS wheat.

John Stewart & Associates
Data: Snowflake JSA.FARMER_SURVEY (seeded from the Farmer Selling Survey workbook, extended monthly
from the Admin tab); falls back to data/*.csv when no Snowflake credentials are set.
Visual language follows the CFTC COT dashboard (sage palette, tiles, uppercase section headers,
50-year watermark on charts and tables).
"""
import base64
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
from loader import MONTHS, BLOCKS, load_workbook_tables

st.set_page_config(page_title="Farmer selling survey", page_icon=":material/agriculture:", layout="wide")

# -- palette (matches cftc-cot-dashboard) -------------------------------------
JSA_GREEN = "#5e7164"
DM_BG, DM_SURFACE, DM_BORDER = "#f6f8f7", "#ffffff", "#d7e2dc"
DM_TEXT, DM_MUTED = "#32373c", "#5f7267"
COL_POS, COL_NEG = "#16a34a", "#dc2626"
YEAR_COLORS = ["#b8c4bc", "#6fa8c4", "#c4785a", JSA_GREEN]  # oldest -> newest

START = {c: m for c, m in BLOCKS.values()}  # marketing-year start month
COMMODITIES = list(START)

HERE = Path(__file__).parent
WATERMARK = HERE / "assets" / "logo-50yr.png"
WATERMARK_OPACITY = 0.10


@st.cache_data(show_spinner=False)
def watermark_uri() -> str | None:
    try:
        return "data:image/png;base64," + base64.b64encode(WATERMARK.read_bytes()).decode()
    except OSError:
        return None


AXIS = dict(gridcolor=DM_BORDER, linecolor=DM_BORDER, showgrid=True,
            tickfont=dict(color=DM_MUTED, size=11), title_font=dict(color=DM_MUTED, size=11), zeroline=False)

_wm = watermark_uri()
# The dataframe grid paints on an opaque canvas, so the mark is overlaid (pointer-events:none).
table_wm_css = (f"""
[class*="st-key-tablewrap_"] {{ position: relative; }}
[class*="st-key-tablewrap_"]::after {{
  content: ""; position: absolute; inset: 0; pointer-events: none; z-index: 5;
  background-image: url('{_wm}'); background-repeat: no-repeat; background-position: center center;
  background-size: min(34%, 260px); opacity: {WATERMARK_OPACITY};
}}""" if _wm else "")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:wght@500;600&family=Source+Sans+3:wght@400;600;700&display=swap');
html, body, [data-testid="stAppViewContainer"] {{ background-color:{DM_BG}; color:{DM_TEXT}; }}
html, body, p, span, div, label, button, td, th {{ font-family:'Source Sans 3','Source Sans Pro',sans-serif; }}
.block-container {{ padding-top: 3.2rem; max-width: 1400px; }}
.dash-header {{ display:flex; align-items:center; gap:18px; padding-bottom:10px;
    border-bottom:1px solid {DM_BORDER}; margin-bottom:14px; }}
.dash-header img {{ height:40px; }}
.dash-header .t b {{ font-family:'EB Garamond',Georgia,serif; font-size:1.7rem; color:{DM_TEXT}; font-weight:600; }}
.dash-header .t div {{ font-size:.85rem; color:{DM_MUTED}; }}
@media (max-width: 640px) {{ .dash-header img {{ display:none; }} }}
.tile {{ background:{DM_SURFACE}; border:1px solid {DM_BORDER}; border-top:3px solid {JSA_GREEN};
    border-radius:10px; padding:16px 20px; text-align:center; height:100%; }}
.tile-label {{ color:{DM_MUTED}; font-size:0.68rem; text-transform:uppercase; letter-spacing:0.09em; margin-bottom:6px; }}
.tile-value {{ color:{DM_TEXT}; font-size:1.8rem; font-weight:700; line-height:1.1; }}
.tile-sub {{ color:{DM_MUTED}; font-size:0.72rem; margin-top:5px; }}
.tile-value.up {{ color:{COL_POS}; }} .tile-value.down {{ color:{COL_NEG}; }}
.sec-header {{ color:{DM_MUTED}; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.1em;
    padding:10px 0 4px; border-bottom:1px solid {DM_BORDER}; margin-bottom:12px; }}
.asof {{ background:{DM_SURFACE}; border:1px solid {DM_BORDER}; border-radius:8px; padding:10px 16px;
    color:{DM_MUTED}; font-size:0.82rem; margin-bottom:12px; }}
.asof b {{ color:{DM_TEXT}; }}
.cy-card {{ background:{DM_SURFACE}; border:1px solid {DM_BORDER}; border-top:3px solid {JSA_GREEN};
    border-radius:10px; padding:14px 16px; }}
.cy-row {{ color:{DM_TEXT}; font-size:1.05rem; padding:3px 0; }}
.cy-row.cy-new {{ font-weight:700; font-size:1.2rem; }}
.sum-wrap {{ background:{DM_SURFACE}; border:1px solid {DM_BORDER}; border-top:3px solid {JSA_GREEN};
    border-radius:10px; padding:6px 12px; overflow-x:auto; }}
table.sum {{ width:100%; border-collapse:collapse; font-size:0.95rem; }}
table.sum th {{ color:{DM_MUTED}; font-size:0.68rem; text-transform:uppercase; letter-spacing:0.09em;
    text-align:left; padding:10px 8px; border-bottom:1px solid {DM_BORDER}; font-weight:600; }}
table.sum td {{ padding:11px 8px; border-bottom:1px solid {DM_BORDER}; color:{DM_TEXT}; }}
table.sum tr:last-child td {{ border-bottom:none; }}
table.sum .num {{ text-align:right; white-space:nowrap; }}
table.sum td.big {{ font-size:1.25rem; font-weight:700; }}
table.sum td.up {{ color:{COL_POS}; font-weight:600; }} table.sum td.down {{ color:{COL_NEG}; font-weight:600; }}
hr {{ border-color:{DM_BORDER}; }}
{table_wm_css}
#MainMenu, footer {{ visibility:hidden; }}
.stDeployButton {{ display:none; }}
</style>
<div class="dash-header">
  <img src="https://www.jpsi.com/wp-content/themes/gate39media/img/logo-full.png">
  <div class="t"><b>Farmer selling survey</b>
  <div>Share of the crop sold, by crop year &middot; John Stewart &amp; Associates</div></div>
</div>
""", unsafe_allow_html=True)


# -- helpers --------------------------------------------------------------------
def sec(text: str):
    st.markdown(f'<div class="sec-header">{text}</div>', unsafe_allow_html=True)


def tile(lbl, value, sub="", cls=""):
    return (f'<div class="tile"><div class="tile-label">{lbl}</div>'
            f'<div class="tile-value {cls}">{value}</div><div class="tile-sub">{sub}</div></div>')


def pts(v):
    return f"{v:+.0f} pts", ("up" if v > 0 else "down" if v < 0 else "")


def year_color(cy, years):
    n = len(years)
    return YEAR_COLORS[-(n - years.index(cy))] if n <= len(YEAR_COLORS) else YEAR_COLORS[-1]


def style_fig(fig, height=400, title=None):
    wm = watermark_uri()
    if wm:
        fig.add_layout_image(dict(source=wm, xref="paper", yref="paper", x=0.5, y=0.5, sizex=0.5, sizey=0.5,
                                  xanchor="center", yanchor="middle", sizing="contain",
                                  opacity=WATERMARK_OPACITY, layer="below"))
    if title:
        fig.update_layout(title=dict(text=title, x=0.5, xanchor="center", y=0.97,
                                     font=dict(size=22, color=DM_TEXT, family="EB Garamond, Georgia, serif")))
    fig.update_layout(height=height, margin=dict(l=60, r=20, t=90 if title else 10, b=50), paper_bgcolor=DM_SURFACE,
                      plot_bgcolor=DM_SURFACE, hovermode="x unified",
                      legend=dict(orientation="h", y=1.06 if title else 1.12, x=0.5 if title else 0,
                                  xanchor="center" if title else "left", font=dict(size=12, color=DM_MUTED)),
                      xaxis={**AXIS, "automargin": True, "tickfont": dict(color=DM_TEXT, size=13)},
                      yaxis={**AXIS, "automargin": True, "title": "% sold", "range": [0, 100], "ticksuffix": "%",
                             "tickfont": dict(color=DM_TEXT, size=13)})
    return fig


def show_table(df, key, **kw):
    with st.container(key=f"tablewrap_{key}"):
        st.dataframe(df, width="stretch", **kw)


@st.cache_data(show_spinner=False)
def load_upload(data: bytes):
    import io
    return load_workbook_tables(io.BytesIO(data))


def crop_years(com, now):
    """(current, new) crop-year labels for a commodity as of `now`, from its marketing-year start month."""
    y = now.year if now.month >= START[com] else now.year - 1
    fmt = lambda a: "%02d/%02d" % (a % 100, (a + 1) % 100)
    return fmt(y), fmt(y + 1)


def survey_page():
    """Client-facing monthly survey (?survey=1): access code, then % sold per commodity; shows no dashboard data."""
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'] {display:none}</style>",
                unsafe_allow_html=True)
    sec("Monthly farmer selling survey")
    if not db.configured():
        st.error("The survey is not available right now. Please try again later.")
        return
    ss = st.session_state
    if "svy_client" not in ss:
        st.write("Enter the access code we sent you.")
        code = st.text_input("Access code", key="svy_code", max_chars=16)
        if st.button("Continue", type="primary"):
            if ss.get("svy_tries", 0) >= 5:
                st.error("Too many attempts. Please contact us for a new code.")
                return
            hit = db.client_for_code(code)
            if hit:
                ss["svy_client"] = (hit[0], hit[1])
                st.rerun()
            ss["svy_tries"] = ss.get("svy_tries", 0) + 1
            st.error("That code was not recognised.")
        return
    client_id, name = ss["svy_client"]
    now = pd.Timestamp.now(tz="America/Chicago")
    month_key = now.strftime("%Y-%m")
    st.write(f"Hello, **{name}**. How much of your crop had you sold as of today ({MONTHS[now.month - 1]} {now.year})? "
             "Enter a percent from 0 to 100, and leave a box empty for crops you do not grow.")
    prev = {(r.commodity, r.kind): r.pct for r in db.load_client_responses(client_id, month_key).itertuples()}
    entries = []
    with st.form("svy_form"):
        for com in COMMODITIES:
            st.markdown(f"**{com}**")
            cols = st.columns(2)
            cur, new = crop_years(com, now)
            for col, knd, lbl, cy in ((cols[0], "current", "Current crop", cur), (cols[1], "new", "New crop", new)):
                v = col.number_input(f"{lbl} ({cy}), % sold", min_value=0.0, max_value=100.0, value=prev.get((com, knd)),
                                     step=1.0, placeholder="not reported", key=f"svy_{com}_{knd}")
                entries.append((com, knd, cy, v))
        sent = st.form_submit_button("Submit", type="primary")
    if sent:
        answered = [e for e in entries if e[3] is not None]
        if not answered:
            st.warning("Please answer at least one box.")
        else:
            db.save_responses(client_id, month_key,
                              pd.DataFrame(answered, columns=["commodity", "kind", "crop_year", "pct"]))
            st.success("Thank you! Your answers are saved. You can come back this month to change them.")


def client_survey_admin():
    """Admin: responses by month, the average roll-up (publish into the dashboard data), and client access codes."""
    sec("Client survey")
    if not db.configured():
        st.info("The client survey needs the Snowflake connection.")
        return
    now = pd.Timestamp.now(tz="America/Chicago")
    keys = [(now - pd.DateOffset(months=i)).strftime("%Y-%m") for i in range(12)]
    mk = st.selectbox("Survey month", keys, key="svy_admin_month")
    try:
        resp = db.load_responses(mk)
        clients = db.list_clients()
    except Exception:
        st.warning("Survey tables not found. Run sql/client_survey.sql in Snowflake first.")
        return
    n_resp = resp.name.nunique() if len(resp) else 0
    st.caption(f"{n_resp} of {int(clients.active.sum()) if len(clients) else 0} active clients have responded for {mk}.")
    if len(resp):
        roll = resp.groupby(["commodity", "kind", "crop_year"], as_index=False).agg(pct=("pct", "mean"), n=("pct", "size"))
        roll["pct"] = roll.pct.round(0)
        st.markdown("**Average of responses** (what gets published)")
        st.dataframe(roll.rename(columns={"pct": "avg % sold", "n": "responses"}), hide_index=True, width="stretch")
        if st.button("Publish averages to monthly data", icon=":material/publish:", key="svy_publish"):
            out = roll.assign(month=MONTHS[int(mk[5:]) - 1])[["commodity", "kind", "crop_year", "month", "pct"]]
            db.save_monthly(out)
            st.cache_data.clear()
            st.toast(f"Published {len(out)} value(s) for {MONTHS[int(mk[5:]) - 1]}.", icon=":material/check:")
        with st.expander("Individual responses"):
            st.dataframe(resp, hide_index=True, width="stretch")
    st.markdown("**Client access codes**")
    st.caption("Send each client the survey link (this app's address followed by `?survey=1`) and their code.")
    with st.form("svy_new_client", clear_on_submit=True):
        new_name = st.text_input("New client name")
        if st.form_submit_button("Create access code") and new_name.strip():
            st.session_state["svy_new_code"] = (new_name.strip(), db.add_client(new_name))
            st.rerun()
    if "svy_new_code" in st.session_state:
        nm, cd = st.session_state.pop("svy_new_code")
        st.success(f"Access code for {nm} (shown once, copy it now):")
        st.code(cd)
    if len(clients):
        st.dataframe(clients.drop(columns=["client_id"]), hide_index=True, width="stretch")
        who = st.selectbox("Turn a client on or off", clients.name, key="svy_toggle_client")
        row = clients[clients.name == who].iloc[0]
        if st.button("Turn off" if row.active else "Turn on", key="svy_toggle"):
            db.set_client_active(row.client_id, not row.active)
            st.rerun()


if st.query_params.get("survey"):
    survey_page()
    st.stop()

up = st.sidebar.file_uploader("Load a newer workbook (.xlsx)", type="xlsx",
                              help="Overrides the bundled data for this session only.")
surveys, monthly = load_upload(up.getvalue()) if up else (db.load_surveys(), db.load_monthly())

commodity = st.segmented_control("Commodity", COMMODITIES, default="Corn", key="commodity") or "Corn"
sm = START[commodity]
order = MONTHS[sm - 1:] + MONTHS[:sm - 1]
close = order[0] + " close"
mo = monthly[monthly.commodity == commodity]

tab_sum, tab_month, tab_data, tab_admin = st.tabs(["Summary", "Monthly view", "Data", "Admin"])


def snap_stats(com):
    """Latest current-crop % for one commodity vs last year / prior-year average, plus new-crop forward sales."""
    m = monthly[monthly.commodity == com]
    cur = m[m.kind == "current"]
    if cur.empty:
        return None
    s = START[com]
    ords = MONTHS[s - 1:] + MONTHS[:s - 1]
    ords = ords + [ords[0] + " close"]
    newest = max(cur.crop_year)
    mon = max(cur[cur.crop_year == newest].month, key=ords.index)
    now = cur[(cur.crop_year == newest) & (cur.month == mon)].pct.iloc[0]
    others = cur[(cur.month == mon) & (cur.crop_year != newest)].sort_values("crop_year").pct
    nw = m[m.kind == "new"]
    new_pct = None
    if len(nw):
        ny = max(nw.crop_year)
        rows = nw[nw.crop_year == ny]
        new_pct = (ny, max(rows.month, key=ords.index), rows[rows.month == max(rows.month, key=ords.index)].pct.iloc[0])
    return dict(com=com, crop=newest, month=mon, now=now,
                ly=others.iloc[-1] if len(others) else None, avg=others.mean() if len(others) else None, new=new_pct)


def delta_cell(v):
    if v is None:
        return '<td class="num">&ndash;</td>'
    cls = "up" if v > 0 else "down" if v < 0 else ""
    return f'<td class="num {cls}">{v:+.0f} pts</td>'


@st.fragment
def summary():
    rows = [r for r in (snap_stats(c) for c in COMMODITIES) if r]
    def pct(v):
        return "&ndash;" if v is None else "%.0f%%" % v

    def gap(a, b):
        return None if b is None else a - b

    body = ""
    for r in rows:
        new = r["new"]
        body += ('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td class="num big">%s</td>'
                 '<td class="num">%s</td>%s<td class="num">%s</td>%s<td>%s</td><td class="num">%s</td></tr>'
                 % (r["com"], r["crop"], r["month"], pct(r["now"]),
                    pct(r["ly"]), delta_cell(gap(r["now"], r["ly"])),
                    pct(r["avg"]), delta_cell(gap(r["now"], r["avg"])),
                    "&ndash;" if new is None else new[0], pct(None if new is None else new[2])))
    sec("Current-crop sales, all commodities")
    st.markdown(
        '<div class="sum-wrap"><table class="sum"><thead><tr><th>Commodity</th><th>Crop year</th><th>As of</th>'
        '<th class="num">% sold</th><th class="num">Last year</th><th class="num">vs LY</th>'
        '<th class="num">Avg prior yrs</th><th class="num">vs avg</th><th>New crop</th>'
        f'<th class="num">New-crop % sold</th></tr></thead><tbody>{body}</tbody></table></div>',
        unsafe_allow_html=True)
    st.caption("% sold is the share of the crop reported sold as of the latest survey month for the newest crop year. "
               "Last year and the prior-year average are for the same month.")


def kpi_tiles():
    cur = mo[mo.kind == "current"]
    newest = max(cur.crop_year)
    ord_s = order + [close]
    latest_m = max(cur[cur.crop_year == newest].month, key=ord_s.index)
    now = cur[(cur.crop_year == newest) & (cur.month == latest_m)].pct.iloc[0]
    others = cur[(cur.month == latest_m) & (cur.crop_year != newest)].sort_values("crop_year")
    st.markdown(f'<div class="asof">Current-crop sales, <b>{newest}</b> crop, as of the <b>{latest_m}</b> survey.</div>',
                unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].markdown(tile(f"{newest} sold", f"{now:.0f}%", "current crop"), unsafe_allow_html=True)
    if len(others):
        d, cls = pts(now - others.pct.iloc[-1])
        cols[1].markdown(tile("vs last year", d, f"last year {others.pct.iloc[-1]:.0f}%", cls), unsafe_allow_html=True)
        d, cls = pts(now - others.pct.mean())
        cols[2].markdown(tile(f"vs {len(others)}-yr avg", d, f"average {others.pct.mean():.0f}%", cls),
                         unsafe_allow_html=True)
    nw = mo[mo.kind == "new"]
    if len(nw):
        ny = max(nw.crop_year)
        rows = nw[nw.crop_year == ny]
        ny_m = max(rows.month, key=ord_s.index)
        cols[3].markdown(tile(f"{ny} new crop", f"{rows[rows.month == ny_m].pct.iloc[0]:.0f}%",
                              f"forward sales, {ny_m}"), unsafe_allow_html=True)


@st.fragment
def monthly_view():
    kpi_tiles()
    for kind, lbl in (("current", "Current-crop sales"), ("new", "New-crop forward sales")):
        k = mo[mo.kind == kind]
        if k.empty:
            continue
        sec(lbl)
        ord_k = list(order if kind == "current" else MONTHS[8:] + MONTHS[:8])
        if close in set(k.month):
            ord_k.append(close)
        fig = go.Figure()
        ks = sorted(k.crop_year.unique())
        for cy in ks:
            d = k[k.crop_year == cy].assign(i=lambda t: t.month.map(ord_k.index)).sort_values("i")
            fig.add_scatter(x=d.month, y=d.pct, name=cy, mode="lines+markers", marker=dict(size=5),
                            line=dict(color=year_color(cy, ks), width=3.5 if cy == ks[-1] else 2.2))
        fig.update_xaxes(categoryorder="array", categoryarray=ord_k)
        kind_lbl = "Current crop" if kind == "current" else "New crop"
        style_fig(fig, title=f"Farmer Selling % - {commodity} ({kind_lbl})")
        # side card: every crop year's % sold at the latest month reported for the newest crop year
        latest = k[k.crop_year == ks[-1]].month.map(ord_k.index).max()
        mon = ord_k[latest]
        vals = k[k.month == mon].set_index("crop_year").pct
        card = "".join(f'<div class="cy-row{" cy-new" if cy == ks[-1] else ""}">{cy} {vals[cy]:.0f}%</div>'
                       for cy in reversed(ks) if cy in vals.index)
        c_chart, c_card = st.columns([5, 1])
        c_chart.plotly_chart(fig, width="stretch", theme=None)
        c_card.markdown(f'<div class="cy-card"><div class="tile-label">{mon} % sold</div>{card}</div>',
                        unsafe_allow_html=True)
        piv =k.pivot(index="month", columns="crop_year", values="pct").reindex(ord_k).dropna(how="all")
        show_table(piv.map(lambda v: None if pd.isna(v) else f"{v:.0f}%"), f"m_{kind}")


@st.fragment
def data_view():
    sv = surveys[surveys.commodity == commodity]
    show_table(sv.sort_values(["crop_year", "date"], ascending=[False, False])
               .assign(date=lambda t: t.date.dt.date), "data", hide_index=True)
    st.download_button("Download survey points (CSV)", sv.to_csv(index=False), f"{commodity}_survey.csv")


with tab_sum:
    summary()
with tab_month:
    monthly_view()
with tab_data:
    data_view()

with tab_admin:
    try:
        pw = st.secrets.get("EDIT_PASSWORD", "")
    except Exception:  # no secrets file locally
        pw = ""
    if pw and st.text_input("Admin password", type="password", key="admin_pw") != pw:
        st.info("Enter the admin password to add data.")
    elif up:
        st.warning("An uploaded workbook is loaded for this session; remove it to edit the saved data.")
    else:
        sec("Add monthly survey results")
        st.caption("Leave % blank for anything not reported; an existing month / crop year / crop type row is overwritten.")
        month = st.selectbox("Month", MONTHS, index=(pd.Timestamp.today().month - 1), key="admin_month")
        base = []
        for com in COMMODITIES:
            for kind in ("current", "new"):
                k = monthly[(monthly.commodity == com) & (monthly.kind == kind)]
                if not k.empty:
                    base.append({"commodity": com, "kind": kind, "crop_year": max(k.crop_year), "pct": None})
        edited = st.data_editor(
            pd.DataFrame(base), hide_index=True, width="stretch", key=f"admin_grid_{month}",
            disabled=["commodity", "kind"],
            column_config={"pct": st.column_config.NumberColumn("% sold", min_value=0, max_value=100, step=1),
                           "crop_year": st.column_config.TextColumn("Crop year", help="e.g. 26/27")})
        if st.button("Save to monthly data", type="primary", icon=":material/save:"):
            new = edited.dropna(subset=["pct"])
            if new.empty:
                st.warning("Nothing to save: fill in at least one % sold.")
            else:
                new = new.assign(month=month)[["commodity", "kind", "crop_year", "month", "pct"]]
                db.save_monthly(new)
                st.cache_data.clear()
                st.toast(f"Saved {len(new)} value(s) for {month}.", icon=":material/check:")
                st.rerun()
        st.divider()
        client_survey_admin()
