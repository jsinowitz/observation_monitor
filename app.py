import math
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Disney Heat Index Dashboard", layout="wide")

API_KEY = st.secrets["ACCUWEATHER_API_KEY"]

BASE_URL = "http://dataservice.accuweather.com"

LOCATIONS = {
    "Magic Kingdom": "196686_POI",
    "Epcot": "70889_POI",
    "Animal Kingdom": "1-196687_1_POI_AL",
    "Hollywood Studios": "1-196660_1_POI_AL",
    "Blizzard Beach": "1-196655_1_POI_AL",
    "Typhoon Lagoon": "1-196662_1_POI_AL",
    "Disney Springs": "196663_POI",
    "Bay Lake": "2257549",
    "Lake Buena Vista": "2257551",
}

REFRESH_SECONDS = 120

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

def heat_index_f(temp_f, rh):
    if temp_f is None or rh is None:
        return None

    if temp_f < 80 or rh < 40:
        return round(temp_f, 1)

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

    return round(hi, 1)

def color_for_heat_index(hi):
    if hi is None or hi < 90:
        return ""
    if hi < 95:
        return "background-color: yellow;"
    if hi < 100:
        return "background-color: orange;"
    if hi < 105:
        return "background-color: red; color: white;"
    return "background-color: purple; color: white;"

def parse_obs_time(obs_time):
    if not obs_time:
        return ""
    try:
        dt = datetime.fromisoformat(obs_time)
        return dt.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception:
        return obs_time

def extract_row(name, key, c):
    wind = c.get("Wind", {})
    temp_f = c.get("Temperature", {}).get("Imperial", {}).get("Value")
    dewpoint_f = c.get("DewPoint", {}).get("Imperial", {}).get("Value")
    rh = c.get("RelativeHumidity")
    wind_speed = wind.get("Speed", {}).get("Imperial", {}).get("Value")
    wind_gust = c.get("WindGust", {}).get("Speed", {}).get("Imperial", {}).get("Value")
    wind_dir_deg = wind.get("Direction", {}).get("Degrees")
    wind_dir = wind.get("Direction", {}).get("Localized")
    obs_time = c.get("LocalObservationDateTime")

    return {
        "Site": name,
        "Location Key": key,
        "Observation Time": parse_obs_time(obs_time),
        "Temp (F)": temp_f,
        "Dew Point (F)": dewpoint_f,
        "RH (%)": rh,
        "Wind Speed (mph)": wind_speed,
        "Wind Gust (mph)": wind_gust,
        "Wind Dir (deg)": wind_dir_deg,
        "Wind Dir": wind_dir,
        "Heat Index (F)": heat_index_f(temp_f, rh),
    }

@st.cache_data(ttl=60, show_spinner=False)
def fetch_all_data():
    rows = []
    errors = []

    for name, key in LOCATIONS.items():
        try:
            c = get_current_conditions(key)
            if c:
                rows.append(extract_row(name, key, c))
            else:
                errors.append(f"{name}: no data returned")
        except Exception as e:
            errors.append(f"{name}: {e}")

    return rows, errors

def style_rows(row):
    color = color_for_heat_index(row["Heat Index (F)"])
    return [color] * len(row)

st.title("Disney Heat Index Dashboard")

col1, col2 = st.columns([1, 1])
with col1:
    st.metric("Refresh Interval", f"{REFRESH_SECONDS} sec")
with col2:
    st.metric("Last Page Load", datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"))

rows, errors = fetch_all_data()

if errors:
    with st.expander("Errors", expanded=False):
        for err in errors:
            st.write(err)

if rows:
    df = pd.DataFrame(rows)
    df = df.sort_values(["Heat Index (F)", "Site"], ascending=[False, True]).reset_index(drop=True)

    styled = df.style.apply(style_rows, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown(
        """
        **Heat Index Color Scale**
        - 90 to 94.9: yellow
        - 95 to 99.9: orange
        - 100 to 104.9: red
        - 105+: purple
        """
    )
else:
    st.warning("No data returned.")

st.caption("This page refreshes automatically.")
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
