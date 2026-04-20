import math
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st
from supabase import create_client

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
        .order("inserted_at")
        .execute()
    )

    rows = result.data or []

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
            "Heat Index Band": heat_index_band(r["heat_index_f"]),  # 👈 ADD THIS
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

    is_band = column_name == "Heat Index Band"

    if column_name not in column_map and not is_band:
        return pd.DataFrame()

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

    if is_band:
        result = (
            supabase.table("observations")
            .select("site_name, inserted_at, heat_index_f")
            .eq("site_name", site_name)
            .gte("inserted_at", cutoff)
            .order("inserted_at")
            .execute()
        )

        rows = result.data or []

        return pd.DataFrame([
            {
                "Site": r["site_name"],
                "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
                "Heat Index Band": heat_index_band(r["heat_index_f"]),
            }
            for r in rows
        ])

    db_col = column_map[column_name]

    result = (
        supabase.table("observations")
        .select(f"site_name, inserted_at, {db_col}")
        .eq("site_name", site_name)
        .gte("inserted_at", cutoff)
        .order("inserted_at")
        .execute()
    )

    rows = result.data or []

    return pd.DataFrame([
        {
            "Site": r["site_name"],
            "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
            column_name: r[db_col],
        }
        for r in rows
    ])
# def history_single_variable_df(site_name, location_key, column_name):
#     column_map = {
#         "Temp (F)": "temp_f",
#         "Dew Point (F)": "dewpoint_f",
#         "RH (%)": "rh",
#         "Wind Speed (mph)": "wind_speed_mph",
#         "Wind Gust (mph)": "wind_gust_mph",
#         "Wind Dir": "wind_dir",
#         "Heat Index (F)": "heat_index_f",
#     }

#     is_band = column_name == "Heat Index Band"
    
#     if column_name not in column_map and not is_band:
#         return pd.DataFrame()

#     latest_result = (
#         supabase.table("observations")
#         .select("inserted_at")
#         .eq("site_name", site_name)
#         .order("inserted_at", desc=True)
#         .limit(1)
#         .execute()
#     )

#     latest_rows = latest_result.data or []
#     if not latest_rows:
#         return pd.DataFrame()

#     latest_inserted = datetime.fromisoformat(latest_rows[0]["inserted_at"].replace("Z", "+00:00"))
#     cutoff = (latest_inserted - timedelta(hours=1)).isoformat()
#     db_col = column_map[column_name]

#     result = (
#         supabase.table("observations")
#         .select(f"site_name, inserted_at, {db_col}")
#         .eq("site_name", site_name)
#         .gte("inserted_at", cutoff)
#         .order("inserted_at")
#         .execute()
#     )

#     rows = result.data or []

#     return pd.DataFrame([
#         {
#             "Site": r["site_name"],
#             "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
#             column_name: r[db_col],
#         }
#         for r in rows
#     ])
    
def render_history_panel(selection, group_df):
    if not selection or "selection" not in selection:
        return

    selected_rows = selection["selection"].get("rows", [])
    selected_cells = selection["selection"].get("cells", [])

    table_df = group_df.reset_index(drop=True)

    if selected_rows:
        row_idx = selected_rows[0]
        if row_idx >= len(table_df):
            return

        site_name = table_df.loc[row_idx, "Site"]
        location_key = LOCATION_GROUPS[table_df.loc[row_idx, "Group"]][site_name]

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

    if selected_cells:
        row_idx, col_name = selected_cells[0]

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
                    st.dataframe(hist_df, width="content", hide_index=True)
            return

        if col_name not in display_columns:
            return

        with st.expander(f"Last hour for {site_name} — {col_name}", expanded=True):
            hist_df = history_single_variable_df(site_name, location_key, col_name)
            if hist_df.empty:
                st.info("No historical data returned for the past hour.")
            else:
                st.dataframe(hist_df, width="content", hide_index=True)
                
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
    rows = []
    errors = []

    for group_name, group_locations in LOCATION_GROUPS.items():
        for site_name, key in group_locations.items():
            try:
                c = get_current_conditions(key)
                if c:
                    rows.append(extract_row(group_name, site_name, key, c))
                else:
                    errors.append(f"{site_name}: no data returned")
            except Exception as e:
                errors.append(f"{site_name}: {e}")

    return rows, errors

def style_table(df):
    def apply_row_style(row):
        hi = row["Heat Index (F)"]
        age_min = row["Observation Age (min)"]
        is_stale = age_min is not None and age_min > STALE_MINUTES

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
        # "Wind Dir (deg)": "{:.1f}",
        "Heat Index (F)": "{:.1f}",
    }, na_rep="")

    event = st.dataframe(
        styled_df,
        width="content",
        hide_index=True,
        key=f"table_{group_name}",
        on_select="rerun",
        selection_mode=["single-row", "single-cell"]
    )

    render_history_panel(event, group_df)

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

st.markdown(
    f"""
    <script>
        setTimeout(function() {{
            window.location.reload();
        }}, {REFRESH_SECONDS * 1000});
    </script>
    """,
    unsafe_allow_html=True,
)
