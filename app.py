import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st
#test comment
TEST_COLOR_MODE = True

if TEST_COLOR_MODE:
    YELLOW_MIN = 72
    ORANGE_MIN = 73
    RED_MIN = 74
    PURPLE_MIN = 75
else:
    YELLOW_MIN = 90
    ORANGE_MIN = 95
    RED_MIN = 100
    PURPLE_MIN = 105
    
st.set_page_config(page_title="Disney Heat Index Dashboard", layout="wide")

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

FIELD_MAP = {
    "Temp (F)": ("Temperature", "Imperial", "Value"),
    "Dew Point (F)": ("DewPoint", "Imperial", "Value"),
    "RH (%)": ("RelativeHumidity",),
    "Wind Speed (mph)": ("Wind", "Speed", "Imperial", "Value"),
    "Wind Gust (mph)": ("WindGust", "Speed", "Imperial", "Value"),
    "Wind Dir (deg)": ("Wind", "Direction", "Degrees"),
    "Wind Dir": ("Wind", "Direction", "Localized"),
    "Heat Index (F)": None,
    "Observation Time (CT)": ("LocalObservationDateTime",),
}

def safe_get(d, *keys):
    cur = d
    for k in keys:
        if cur is None:
            return None
        cur = cur.get(k)
    return cur

@st.cache_data(ttl=120, show_spinner=False)
def get_historical_conditions_24(location_key):
    url = f"{BASE_URL}/currentconditions/v1/{location_key}/historical/24"
    params = {
        "apikey": API_KEY,
        "details": "true"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, list) else []

def parse_obs_dt(obs_time):
    if not obs_time:
        return None
    try:
        return datetime.fromisoformat(obs_time)
    except Exception:
        return None

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

def history_last_hour(location_key):
    records = get_historical_conditions_24(location_key)
    parsed = []
    for rec in records:
        obs_time = rec.get("LocalObservationDateTime")
        dt = parse_obs_dt(obs_time)
        if dt is not None:
            parsed.append((dt, rec))

    if not parsed:
        return []

    parsed.sort(key=lambda x: x[0])
    latest_dt = parsed[-1][0]
    cutoff = latest_dt.timestamp() - 3600

    return [rec for dt, rec in parsed if dt.timestamp() >= cutoff]

def history_all_variables_df(site_name, location_key):
    records = history_last_hour(location_key)

    rows = []
    for rec in records:
        temp_f = round1(safe_get(rec, "Temperature", "Imperial", "Value"))
        rh = round1(rec.get("RelativeHumidity"))
        rows.append({
            "Site": site_name,
            "Observation Time (CT)": format_obs_time_ct_short(rec.get("LocalObservationDateTime")),
            "Temp (F)": temp_f,
            "Dew Point (F)": round1(safe_get(rec, "DewPoint", "Imperial", "Value")),
            "RH (%)": rh,
            "Wind Speed (mph)": round1(safe_get(rec, "Wind", "Speed", "Imperial", "Value")),
            "Wind Gust (mph)": round1(safe_get(rec, "WindGust", "Speed", "Imperial", "Value")),
            "Wind Dir (deg)": round1(safe_get(rec, "Wind", "Direction", "Degrees")),
            "Wind Dir": safe_get(rec, "Wind", "Direction", "Localized"),
            "Heat Index (F)": heat_index_f(temp_f, rh),
        })

    return pd.DataFrame(rows)

def history_single_variable_df(site_name, location_key, column_name):
    records = history_last_hour(location_key)
    rows = []

    for rec in records:
        temp_f = round1(safe_get(rec, "Temperature", "Imperial", "Value"))
        rh = round1(rec.get("RelativeHumidity"))

        if column_name == "Heat Index (F)":
            value = heat_index_f(temp_f, rh)
        elif column_name == "Observation Time (CT)":
            value = format_obs_time_ct_short(rec.get("LocalObservationDateTime"))
        else:
            field_path = FIELD_MAP.get(column_name)
            value = round1(safe_get(rec, *field_path)) if field_path and column_name != "Wind Dir" else (
                safe_get(rec, *field_path) if field_path else None
            )

        rows.append({
            "Site": site_name,
            "Observation Time (CT)": format_obs_time_ct_short(rec.get("LocalObservationDateTime")),
            column_name: value,
        })

    return pd.DataFrame(rows)

def render_history_panel(selection, group_df):
    if not selection or "selection" not in selection:
        return

    selected_rows = selection["selection"].get("rows", [])
    selected_cells = selection["selection"].get("cells", [])

    if not selected_rows and not selected_cells:
        return

    table_df = group_df.reset_index(drop=True)

    if selected_cells:
        cell = selected_cells[0]
        row_idx, col_name = cell

        if row_idx >= len(table_df):
            return

        site_name = table_df.loc[row_idx, "Site"]
        location_key = LOCATION_GROUPS[table_df.loc[row_idx, "Group"]][site_name]

        if col_name not in display_columns:
            return

        with st.expander(f"Last hour for {site_name} — {col_name}", expanded=True):
            hist_df = history_single_variable_df(site_name, location_key, col_name)
            if hist_df.empty:
                st.info("No historical data returned for the past hour.")
            else:
                st.dataframe(
                    hist_df,
                    width="content",
                    hide_index=True
                )
        return

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
                    hist_df,
                    width="content",
                    hide_index=True
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

# def heat_index_band(hi):
#     if hi is None or hi < 90:
#         return "None"
#     if hi < 95:
#         return "Yellow"
#     if hi < 100:
#         return "Orange"
#     if hi < 105:
#         return "Red"
#     return "Purple"

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

# def row_background_css(hi):
#     if hi is None or hi < YELLOW_MIN:
#         return ""
#     if hi < ORANGE_MIN:
#         return "background-color: #fff59d; color: black;"
#     if hi < RED_MIN:
#         return "background-color: #ffcc80; color: black;"
#     if hi < PURPLE_MIN:
#         return "background-color: #d32f2f; color: white;"
#     return "background-color: #7b1fa2; color: white;"

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

# def stale_text_css(is_stale, hi):
#     if not is_stale:
#         return ""
#     if hi is not None and hi >= RED_MIN:
#         return "color: yellow; font-weight: 700;"
#     return "color: red; font-weight: 700;"

def stale_text_css(is_stale, hi):
    if not is_stale:
        return ""
    if hi is not None and hi >= 100:
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
st.caption(f"Auto-refresh every {REFRESH_SECONDS} seconds")

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
