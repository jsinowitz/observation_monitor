import math
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st
from supabase import create_client
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

if "selected_site" not in st.session_state:
    st.session_state.selected_site = None

if "selected_column" not in st.session_state:
    st.session_state.selected_column = None

st_autorefresh(interval=120000, key="datarefresh")

YELLOW_MIN = 90
ORANGE_MIN = 95
RED_MIN = 100
PURPLE_MIN = 105

st.set_page_config(page_title="Disney Heat Index Dashboard", layout="wide")
SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
BASE_URL = "http://apidev.accuweather.com"
API_KEY = st.secrets["ACCUWEATHER_API_KEY"]
CENTRAL_TZ = ZoneInfo("America/Chicago")
REFRESH_SECONDS = 120
STALE_MINUTES = 30

LOCATION_GROUPS = {
    "Walt Disney World - Orlando": {
        "Magic Kingdom": "196686_POI",
        "Epcot": "70889_POI",
        "Animal Kingdom": "1-196687_1_POI_AL",
        "Hollywood Studios": "1-196660_1_POI_AL",
        "Blizzard Beach": "1-196655_1_POI_AL",
        "Typhoon Lagoon": "1-196662_1_POI_AL",
        "Disney Springs": "196663_POI",
        "Bay Lake": "2257549",
        "Lake Buena Vista": "2257551",
    },
    "Disneyland Resort - California": {
        "Circle D Ranch": "2154424",
        "DLR Paradise Pier": "327150",
        "DLR Main Street": "327150",
    },
    "Aulani Resort - Hawaii": {
        "Aulani Resort and Spa": "2274485",
    }
}

def safe_get(d, *keys):
    cur = d
    for k in keys:
        if cur is None:
            return None
        cur = cur.get(k)
    return cur

def format_obs_time_ct_short(obs_time):
    if not obs_time:
        return ""
    try:
        dt = datetime.fromisoformat(obs_time).astimezone(CENTRAL_TZ)
        month = dt.month
        day = dt.day
        hour12 = dt.strftime("%I").lstrip("0") or "0"
        minute = dt.strftime("%M")
        ampm = dt.strftime("%p").lower()
        return f"{month}/{day} {hour12}:{minute}{ampm}"
    except Exception:
        return obs_time
        
def history_all_variables_df(site_name, location_key):
    latest_result = (
        supabase.table("observations")
        .select("inserted_at")
        .eq("site_name", site_name)
        .order("inserted_at", desc=True)
        .limit(1)
        .execute()
    )

    latest_rows = latest_result.data or []
    if not latest_rows:
        return pd.DataFrame()

    latest_inserted = datetime.fromisoformat(latest_rows[0]["inserted_at"].replace("Z", "+00:00"))
    cutoff = (latest_inserted - timedelta(hours=1)).isoformat()

    result = (
        supabase.table("observations")
        .select("site_name, inserted_at, temp_f, dewpoint_f, rh, wind_speed_mph, wind_gust_mph, wind_dir, heat_index_f")
        .eq("site_name", site_name)
        .gte("inserted_at", cutoff)
        .order("inserted_at", desc=True)
        .execute()
    )

    rows = result.data or []
    rows = filter_to_6min_intervals(rows)
    return pd.DataFrame([
        {
            "Site": r["site_name"],
            "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
            "Temp (F)": r["temp_f"],
            "Dew Point (F)": r["dewpoint_f"],
            "RH (%)": r["rh"],
            "Wind Speed (mph)": r["wind_speed_mph"],
            "Wind Gust (mph)": r["wind_gust_mph"],
            "Wind Dir": r["wind_dir"],
            "Heat Index (F)": r["heat_index_f"],
            "Heat Index Band": heat_index_band(r["heat_index_f"]) if r["heat_index_f"] is not None else "None",
        }
        for r in rows
    ])

def history_single_variable_df(site_name, location_key, column_name):
    column_map = {
        "Temp (F)": "temp_f",
        "Dew Point (F)": "dewpoint_f",
        "RH (%)": "rh",
        "Wind Speed (mph)": "wind_speed_mph",
        "Wind Gust (mph)": "wind_gust_mph",
        "Wind Dir": "wind_dir",
        "Heat Index (F)": "heat_index_f",
    }

    is_heat_index = column_name in ["Heat Index (F)", "Heat Index Band"]

    if column_name not in column_map and not is_heat_index:
        return pd.DataFrame()

    # get latest timestamp
    latest_result = (
        supabase.table("observations")
        .select("inserted_at")
        .eq("site_name", site_name)
        .order("inserted_at", desc=True)
        .limit(1)
        .execute()
    )

    latest_rows = latest_result.data or []
    if not latest_rows:
        return pd.DataFrame()

    latest_inserted = datetime.fromisoformat(
        latest_rows[0]["inserted_at"].replace("Z", "+00:00")
    )
    cutoff = (latest_inserted - timedelta(hours=1)).isoformat()

    if is_heat_index:
        result = (
            supabase.table("observations")
            .select("site_name, inserted_at, heat_index_f")
            .eq("site_name", site_name)
            .gte("inserted_at", cutoff)
            .order("inserted_at", desc=True)
            .execute()
        )
        
        rows = result.data or []
        rows = filter_to_6min_intervals(rows)
        return pd.DataFrame([
            {
                "Site": r["site_name"],
                "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
                "Heat Index (F)": r["heat_index_f"],
                "Heat Index Band": heat_index_band(r["heat_index_f"]),
            }
            for r in rows
        ])

    # 🔹 NORMAL VARIABLE CASE
    db_col = column_map[column_name]

    result = (
        supabase.table("observations")
        .select(f"site_name, inserted_at, {db_col}")
        .eq("site_name", site_name)
        .gte("inserted_at", cutoff)
        .order("inserted_at", desc=True)
        .execute()
    )

    rows = result.data or []
    rows = rows[::3]
    return pd.DataFrame([
        {
            "Site": r["site_name"],
            "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
            column_name: r[db_col],
        }
        for r in rows
    ])

def history_chart_series(hist_df, column_name):
    if hist_df.empty:
        return pd.DataFrame()

    df = hist_df.copy()
    df["dt"] = pd.to_datetime(df["Observation Time (CT)"], format="%m/%d %I:%M%p", errors="coerce")

    if df["dt"].isna().all():
        df["x_label"] = df["Observation Time (CT)"].astype(str)
    else:
        df["x_label"] = df["dt"].dt.strftime("%I:%M%p").str.lstrip("0").str.lower()

    if column_name in ["Heat Index (F)", "Heat Index Band"]:
        chart_col = "Heat Index (F)"
        y_min = 70
    elif column_name == "Temp (F)":
        chart_col = "Temp (F)"
        y_min = 60
    elif column_name == "Dew Point (F)":
        chart_col = "Dew Point (F)"
        y_min = 50
    elif column_name == "RH (%)":
        chart_col = "RH (%)"
        y_min = 0
    elif column_name in ["Wind Speed (mph)", "Wind Gust (mph)"]:
        chart_col = column_name
        y_min = 0
    else:
        return pd.DataFrame()
    
    out = df[["Observation Time (CT)", "x_label", chart_col]].copy()
    out = out.rename(columns={chart_col: "y"})
    out["y"] = pd.to_numeric(out["y"], errors="coerce")
    out = out.dropna(subset=["y"]).reset_index(drop=True)
    out = out.iloc[::-1].reset_index(drop=True)
    
    out["x"] = range(len(out))
    out["y_min"] = y_min
    return out
    
def is_dark_theme():
    try:
        return st.get_option("theme.base") == "dark"
    except Exception:
        return False
        
def solid_line_color(column_name):
    if column_name == "Temp (F)":
        return "#d32f2f"
    if column_name == "Dew Point (F)":
        return "#2e7d32"
    if column_name == "RH (%)":
        return "#d4ff00"
    if column_name == "Wind Speed (mph)":
        return "#2196f3"
    if column_name == "Wind Gust (mph)":
        return "#8e24aa"
    return "#90caf9"

def hi_segment_color(hi_value):
    dark = is_dark_theme()

    # Below threshold ("None")
    if hi_value is None or pd.isna(hi_value) or hi_value < YELLOW_MIN:
        return "#ffffff" if dark else "#000000"

    if hi_value < ORANGE_MIN:
        return "#fff59d"
    if hi_value < RED_MIN:
        return "#ffcc80"
    if hi_value < PURPLE_MIN:
        return "#d32f2f"
    return "#7b1fa2"

def build_history_chart(hist_df, column_name):
    plot_df = history_chart_series(hist_df, column_name)
    if plot_df.empty:
        return None

    x = plot_df["x_label"].tolist()
    y = plot_df["y"].tolist()

    is_hi = column_name in ["Heat Index (F)", "Heat Index Band"]

    # --- Units + floor ---
    if column_name in ["Temp (F)", "Dew Point (F)", "Heat Index (F)", "Heat Index Band"]:
        unit = "°F"
        y_floor = 70 if is_hi else (60 if column_name == "Temp (F)" else 50)
    elif column_name == "RH (%)":
        unit = "%"
        y_floor = 0
    else:
        unit = "mph"
        y_floor = 0

    y_ceiling = max(max(y) + 5, y_floor + 10)

    fig = go.Figure()

    # --- Heat Index segmented lines ---
    if is_hi:
        for i in range(len(y) - 1):
            fig.add_trace(go.Scatter(
                x=[x[i], x[i+1]],
                y=[y[i], y[i+1]],
                mode="lines",
                line=dict(color=hi_segment_color(y[i+1]), width=3),
                hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>"
            ))

        # markers layer
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="markers",
            marker=dict(color=[hi_segment_color(v) for v in y], size=6),
            hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>"
        ))

    else:
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line=dict(color=solid_line_color(column_name), width=3),
            marker=dict(size=6),
            hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>",
        ))

    # --- Title ---
    if is_hi:
        title = "Heat Index Over the Last Hour"
    elif column_name == "Temp (F)":
        title = "Temperature Over the Last Hour"
    elif column_name == "Dew Point (F)":
        title = "Dew Point Over the Last Hour"
    elif column_name == "RH (%)":
        title = "Relative Humidity Over the Last Hour"
    elif column_name == "Wind Speed (mph)":
        title = "Wind Speed Over the Last Hour"
    elif column_name == "Wind Gust (mph)":
        title = "Wind Gusts Over the Last Hour"
    else:
        title = f"{column_name} Over the Last Hour"
        
    if len(y) > 0:
        latest_x = x[-1]
        latest_y = y[-1]
    
        # --- determine color ---
        if is_hi:
            label_color = hi_segment_color(latest_y)
        else:
            label_color = solid_line_color(column_name)
    
        # --- label text ---
        label_text = f"{latest_y:.1f}{unit}"
    
        # --- add annotation ---
        fig.add_annotation(
            x=latest_x,
            y=latest_y,
            text=label_text,
            showarrow=False,
            xshift=40,
            yshift=-10,
            font=dict(size=12, color=label_color),
            bgcolor="rgba(0,0,0,0)",
            bordercolor=label_color,
            borderwidth=1,
            borderpad=7
        )
    # --- Layout ---
    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor="center",
            font=dict(size=14)
        ),
        height=260,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(
            tickmode="array",
            tickvals=x,
            ticktext=x
        ),
        yaxis=dict(
            range=[y_floor, y_ceiling],
            dtick=10
        ),
        showlegend=False,
        transition=dict(
            duration=600,
            easing="cubic-in-out"
        )
    )

    fig.update_traces(connectgaps=True)

    return fig
    
def filter_to_6min_intervals(rows):
    filtered = []

    seen_minutes = set()

    for r in rows:
        dt = datetime.fromisoformat(r["inserted_at"].replace("Z","+00:00"))

        # round DOWN to nearest 6-minute bucket
        minute_bucket = (dt.minute // 6) * 6

        key = (dt.hour, minute_bucket)

        if key not in seen_minutes:
            seen_minutes.add(key)
            filtered.append(r)

        # stop once we have 10 rows
        if len(filtered) >= 10:
            break

    return filtered
    
def render_history_panel(selection, group_df):
    if not selection or "selection" not in selection:
        return

    selected_cells = selection["selection"].get("cells", [])
    if not selected_cells:
        return

    table_df = group_df.reset_index(drop=True)

    row_idx, col_name = selected_cells[0]
    st.session_state.selected_site = table_df.loc[row_idx, "Site"]
    st.session_state.selected_column = col_name
    if row_idx >= len(table_df):
        return

    site_name = table_df.loc[row_idx, "Site"]
    location_key = LOCATION_GROUPS[table_df.loc[row_idx, "Group"]][site_name]

    if col_name == "Site":
        with st.expander(f"Last hour for {site_name}", expanded=True):
            hist_df = history_all_variables_df(site_name, location_key)
            if hist_df.empty:
                st.info("No historical data returned for the past hour.")
            else:
                st.dataframe(
                    style_table(hist_df).format({
                        "Temp (F)": "{:.1f}",
                        "Dew Point (F)": "{:.1f}",
                        "RH (%)": "{:.1f}",
                        "Wind Speed (mph)": "{:.1f}",
                        "Wind Gust (mph)": "{:.1f}",
                        "Heat Index (F)": "{:.1f}",
                    }, na_rep=""),
                    width=950,
                    hide_index=True
                )
        return

    if col_name not in display_columns or col_name in ["Observation Time (CT)", "Observation Age (min)"]:
        return

    with st.expander(f"Last hour for {site_name} — {col_name}", expanded=True):
        hist_df = history_single_variable_df(site_name, location_key, col_name)

        if hist_df.empty:
            st.info("No historical data returned for the past hour.")
        else:
            left_col, right_col = st.columns([1.8, 1.2], vertical_alignment="top")

            with left_col:
                st.dataframe(
                    style_table(hist_df).format({
                        "Temp (F)": "{:.1f}",
                        "Dew Point (F)": "{:.1f}",
                        "RH (%)": "{:.1f}",
                        "Wind Speed (mph)": "{:.1f}",
                        "Wind Gust (mph)": "{:.1f}",
                        "Heat Index (F)": "{:.1f}",
                    }, na_rep=""),
                    width=950,
                    hide_index=True
                )

            with right_col:
                fig = build_history_chart(hist_df, col_name)
                if fig is not None:
                    st.plotly_chart(
                        fig,
                        width="stretch",
                        key=f"chart_{site_name}_{col_name}"
                    )
                    
def get_current_conditions(location_key):
    url = f"{BASE_URL}/currentconditions/v1/{location_key}"
    params = {
        "apikey": API_KEY,
        "details": "true"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    return payload[0] if payload else None

def round1(value):
    if value is None or pd.isna(value):
        return None
    return round(float(value), 1)

def heat_index_f(temp_f, rh):
    if temp_f is None or rh is None:
        return None

    if temp_f < 80 or rh < 40:
        return round1(temp_f)

    hi = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * rh
        - 0.22475541 * temp_f * rh
        - 0.00683783 * temp_f * temp_f
        - 0.05481717 * rh * rh
        + 0.00122874 * temp_f * temp_f * rh
        + 0.00085282 * temp_f * rh * rh
        - 0.00000199 * temp_f * temp_f * rh * rh
    )

    if rh < 13 and 80 <= temp_f <= 112:
        adjustment = ((13 - rh) / 4) * math.sqrt((17 - abs(temp_f - 95)) / 17)
        hi -= adjustment
    elif rh > 85 and 80 <= temp_f <= 87:
        adjustment = ((rh - 85) / 10) * ((87 - temp_f) / 5)
        hi += adjustment

    return round1(hi)

def heat_index_band(hi):
    if hi is None or hi < YELLOW_MIN:
        return "None"
    if hi < ORANGE_MIN:
        return "Yellow"
    if hi < RED_MIN:
        return "Orange"
    if hi < PURPLE_MIN:
        return "Red"
    return "Purple"

def row_background_css(hi):
    if hi is None or hi < YELLOW_MIN:
        return ""
    if hi < ORANGE_MIN:
        return "background-color: #fff59d; color: black;"
    if hi < RED_MIN:
        return "background-color: #ffcc80; color: black;"
    if hi < PURPLE_MIN:
        return "background-color: #d32f2f; color: white;"
    return "background-color: #7b1fa2; color: white;"
    
def parse_obs_time_ct(obs_time):
    if not obs_time:
        return ""
    try:
        dt = datetime.fromisoformat(obs_time)
        dt_ct = dt.astimezone(CENTRAL_TZ)
        month = dt_ct.month
        day = dt_ct.day
        hour12 = dt_ct.strftime("%I").lstrip("0") or "0"
        minute = dt_ct.strftime("%M")
        ampm = dt_ct.strftime("%p").lower()
        return f"{month}/{day} {hour12}:{minute}{ampm}"
    except Exception:
        return obs_time

def obs_age_minutes(obs_time):
    if not obs_time:
        return None
    try:
        dt = datetime.fromisoformat(obs_time)
        now_utc = datetime.now(timezone.utc)
        return int(round((now_utc - dt.astimezone(timezone.utc)).total_seconds() / 60.0))
    except Exception:
        return None
        
def stale_text_css(is_stale, hi):
    if not is_stale:
        return ""
    if hi is not None and hi >= RED_MIN:
        return "color: yellow; font-weight: 700;"
    return "color: red; font-weight: 700;"
    
def extract_row(group_name, site_name, key, c):
    wind = c.get("Wind", {})
    temp_f = round1(c.get("Temperature", {}).get("Imperial", {}).get("Value"))
    dewpoint_f = round1(c.get("DewPoint", {}).get("Imperial", {}).get("Value"))
    rh = round1(c.get("RelativeHumidity"))
    wind_speed = round1(wind.get("Speed", {}).get("Imperial", {}).get("Value"))
    wind_gust = round1(c.get("WindGust", {}).get("Speed", {}).get("Imperial", {}).get("Value"))
    # wind_dir_deg = round1(wind.get("Direction", {}).get("Degrees"))
    wind_dir = wind.get("Direction", {}).get("Localized")
    obs_time_raw = c.get("LocalObservationDateTime")
    age_min = obs_age_minutes(obs_time_raw)
    hi = heat_index_f(temp_f, rh)

    return {
        "Group": group_name,
        "Site": site_name,
        "Observation Time (CT)": parse_obs_time_ct(obs_time_raw),
        "Observation Age (min)": age_min,
        "Temp (F)": temp_f,
        "Dew Point (F)": dewpoint_f,
        "RH (%)": rh,
        "Wind Speed (mph)": wind_speed,
        "Wind Gust (mph)": wind_gust,
        "Wind Dir": wind_dir,
        "Heat Index (F)": hi,
        "Heat Index Band": heat_index_band(hi),
        "_obs_time_raw": obs_time_raw,
    }
@st.cache_data(ttl=60, show_spinner=False)
def fetch_all_data():
    result = (
        supabase.table("observations")
        .select("*")
        .order("inserted_at", desc=True)
        .execute()
    )

    rows = result.data or []

    if not rows:
        return [], ["No Supabase data"]

    df = pd.DataFrame(rows)

    # keep only latest per site
    df = df.sort_values("inserted_at", ascending=False)
    df = df.drop_duplicates(subset=["site_name"], keep="first")

    output = []

    for _, r in df.iterrows():
        output.append({
            "Group": r["group_name"],
            "Site": r["site_name"],
            "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
            "Observation Age (min)": int((datetime.now(timezone.utc) - datetime.fromisoformat(r["inserted_at"].replace("Z","+00:00"))).total_seconds()/60),
            "Temp (F)": round1(r["temp_f"]),
            "Dew Point (F)": round1(r["dewpoint_f"]),
            "RH (%)": round1(r["rh"]),
            "Wind Speed (mph)": round1(r["wind_speed_mph"]),
            "Wind Gust (mph)": round1(r["wind_gust_mph"]),
            "Wind Dir": r["wind_dir"],
            "Heat Index (F)": round1(r["heat_index_f"]),
            "Heat Index Band": heat_index_band(r["heat_index_f"]),
        })

    return output, []

def style_table(df):
    def apply_row_style(row):
        hi = row.get("Heat Index (F)", None)
        age_min = row.get("Observation Age (min)", None)
        is_stale = age_min is not None and pd.notna(age_min) and age_min > STALE_MINUTES

        bg = row_background_css(hi)
        stale_css = stale_text_css(is_stale, hi)

        styles = []
        for col in row.index:
            cell_style = bg
            if col in ["Observation Time (CT)", "Observation Age (min)"] and stale_css:
                cell_style = f"{cell_style} {stale_css}".strip()
            styles.append(cell_style)

        return styles

    return df.style.apply(apply_row_style, axis=1)


def build_status_cards(df):
    total_sites = len(df)
    stale_count = int((df["Observation Age (min)"] > STALE_MINUTES).fillna(False).sum())
    max_hi = df["Heat Index (F)"].max() if not df.empty else None
    hottest_site = None
    if not df.empty and df["Heat Index (F)"].notna().any():
        hottest_site = df.loc[df["Heat Index (F)"].idxmax(), "Site"]

    yellow_count = int(((df["Heat Index (F)"] >= 90) & (df["Heat Index (F)"] < 95)).sum())
    orange_count = int(((df["Heat Index (F)"] >= 95) & (df["Heat Index (F)"] < 100)).sum())
    red_count = int(((df["Heat Index (F)"] >= 100) & (df["Heat Index (F)"] < 105)).sum())
    purple_count = int((df["Heat Index (F)"] >= 105).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stations", total_sites)
    c2.metric("Stale Obs (>30 min)", stale_count)
    c3.metric("Max Heat Index", f"{max_hi:.1f}°F" if pd.notna(max_hi) else "N/A")
    c4.metric("Highest Site", hottest_site if hottest_site else "N/A")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Yellow Rows", yellow_count)
    c6.metric("Orange Rows", orange_count)
    c7.metric("Red Rows", red_count)
    c8.metric("Purple Rows", purple_count)

st.title("Disney Heat Index Dashboard")
st.markdown(
    """
    <div style="font-size:18px; font-weight:600;">
        Time until next update: <span id="countdown">--:--</span>
    </div>

    <script>
        function waitForElement(id, callback) {
            const interval = setInterval(() => {
                const el = document.getElementById(id);
                if (el) {
                    clearInterval(interval);
                    callback(el);
                }
            }, 100);
        }

        function startCountdown(el) {
            function updateCountdown() {
                const now = new Date();

                const next = new Date(now);
                next.setSeconds(0);
                next.setMilliseconds(0);

                const minutes = next.getMinutes();
                const remainder = minutes % 2;

                if (remainder === 0 && now.getSeconds() === 0) {
                    next.setMinutes(minutes + 2);
                } else {
                    next.setMinutes(minutes + (2 - remainder));
                }

                const diff = next - now;

                const totalSeconds = Math.floor(diff / 1000);
                const m = Math.floor(totalSeconds / 60);
                const s = totalSeconds % 60;

                const formatted =
                    String(m).padStart(2, '0') + ":" +
                    String(s).padStart(2, '0');

                el.innerText = formatted;
            }

            setInterval(updateCountdown, 950);
            updateCountdown();
        }

        waitForElement("countdown", startCountdown);
    </script>
    """,
    unsafe_allow_html=True
)
st.caption("Auto-refresh every 2 minutes")

rows, errors = fetch_all_data()

if errors:
    with st.expander("Errors", expanded=False):
        for err in errors:
            st.write(err)

if not rows:
    st.warning("No data returned.")
    st.stop()

df = pd.DataFrame(rows)

display_columns = [
    "Site",
    "Observation Time (CT)",
    "Observation Age (min)",
    "Temp (F)",
    "Dew Point (F)",
    "RH (%)",
    "Wind Speed (mph)",
    "Wind Gust (mph)",
    "Wind Dir",
    "Heat Index (F)",
    "Heat Index Band",
]

build_status_cards(df)

for group_name in LOCATION_GROUPS.keys():
    st.subheader(group_name)

    group_df = df[df["Group"] == group_name].copy()
    group_df = group_df.reset_index(drop=True)
    group_df = group_df.dropna(subset=["Site"])
    
    table_df = group_df[display_columns].copy()

    styled_df = style_table(table_df).format({
        "Observation Age (min)": "{:.0f}",
        "Temp (F)": "{:.1f}",
        "Dew Point (F)": "{:.1f}",
        "RH (%)": "{:.1f}",
        "Wind Speed (mph)": "{:.1f}",
        "Wind Gust (mph)": "{:.1f}",
        "Heat Index (F)": "{:.1f}",
    }, na_rep="")

    event = st.dataframe(
        styled_df,
        width="content",
        hide_index=True,
        key=f"table_{group_name}",
        on_select="rerun",
        selection_mode="single-cell"
    )

    render_history_panel(event, group_df)

# 🔥 MOVE THIS OUTSIDE LOOP
if st.session_state.selected_site is not None:
    for group_name in LOCATION_GROUPS.keys():
        group_df = df[df["Group"] == group_name].copy().reset_index(drop=True)

        matches = group_df[group_df["Site"] == st.session_state.selected_site]
        if not matches.empty:
            row_idx = matches.index[0]
            site_name = st.session_state.selected_site
            col_name = st.session_state.selected_column

            fake_event = {
                "selection": {
                    "rows": [],
                    "cells": [(row_idx, col_name)]
                }
            }

            render_history_panel(fake_event, group_df)
            break
st.markdown(
    """
    **Heat Index Color Scale**
    - 90 to 94.9: yellow
    - 95 to 99.9: orange
    - 100 to 104.9: red
    - 105+: purple

    **Stale Observation Rule**
    - If observation age is greater than 30 minutes, the observation time and age text turn red
    - On red/purple heat index rows, stale text turns yellow instead

    **Time Zone Note**
    - Observation times are displayed in Central Time

    ---
    Click on any site name to pull up the last hour's data for all variables.  
    Click on any single variable data cell to display the last hour's data for that variable.

    Click on any one column header to sort it by ascending or descending.
    """
)

now_ct = datetime.now(CENTRAL_TZ)
st.caption(f"Last page render: {now_ct.month}/{now_ct.day} {now_ct.strftime('%I:%M%p').lstrip('0').lower()} CT")

