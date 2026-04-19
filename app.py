import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

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
        "Ko Olina": "2274485",
        "Kapolei": "343019",
    }
}
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
    if hi is None or hi < 90:
        return "None"
    if hi < 95:
        return "Yellow"
    if hi < 100:
        return "Orange"
    if hi < 105:
        return "Red"
    return "Purple"

def row_background_css(hi):
    if hi is None or hi < 90:
        return ""
    if hi < 95:
        return "background-color: #fff59d;"
    if hi < 100:
        return "background-color: #ffcc80;"
    if hi < 105:
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
    wind_dir_deg = round1(wind.get("Direction", {}).get("Degrees"))
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
        "Wind Dir (deg)": wind_dir_deg,
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
    "Wind Dir (deg)",
    "Wind Dir",
    "Heat Index (F)",
    "Heat Index Band",
]

build_status_cards(df)

for group_name in LOCATION_GROUPS.keys():
    st.subheader(group_name)

    group_df = df[df["Group"] == group_name].copy()

    sort_options = {
        "Site": ["Site", "Heat Index (F)"],
        "Heat Index (high to low)": ["Heat Index (F)", "Site"],
        "Temperature (high to low)": ["Temp (F)", "Site"],
        "Newest obs first": ["Observation Age (min)", "Site"],
        "Oldest obs first": ["Observation Age (min)", "Site"],
    }

    col1, col2 = st.columns([1, 3])
    with col1:
        selected_sort = st.selectbox(
            f"Sort order for {group_name}",
            list(sort_options.keys()),
            key=f"sort_{group_name}"
        )

    ascending = [True, True]
    if selected_sort == "Heat Index (high to low)":
        ascending = [False, True]
    elif selected_sort == "Temperature (high to low)":
        ascending = [False, True]
    elif selected_sort == "Newest obs first":
        ascending = [True, True]
    elif selected_sort == "Oldest obs first":
        ascending = [False, True]

    group_df = group_df.sort_values(sort_options[selected_sort], ascending=ascending).reset_index(drop=True)

    styled_df = style_table(group_df[display_columns]).format({
        "Observation Age (min)": "{:.0f}",
        "Temp (F)": "{:.1f}",
        "Dew Point (F)": "{:.1f}",
        "RH (%)": "{:.1f}",
        "Wind Speed (mph)": "{:.1f}",
        "Wind Gust (mph)": "{:.1f}",
        "Wind Dir (deg)": "{:.1f}",
        "Heat Index (F)": "{:.1f}",
    }, na_rep="")

    st.dataframe(
        styled_df,
        width="stretch",
        hide_index=True,
        height=min(600, 45 + len(group_df) * 38)
    )

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
