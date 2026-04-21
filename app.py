# import math
# from datetime import datetime, timezone, timedelta
# from zoneinfo import ZoneInfo
# import pandas as pd
# import requests
# import streamlit as st
# from supabase import create_client
# import matplotlib.pyplot as plt
# from matplotlib.collections import LineCollection
# import plotly.graph_objects as go
# from streamlit_autorefresh import st_autorefresh
# import streamlit.components.v1 as components
# import hashlib

# if "selected_site" not in st.session_state:
#     st.session_state.selected_site = None

# if "selected_column" not in st.session_state:
#     st.session_state.selected_column = None

# st_autorefresh(interval=30000, key="datarefresh") # polls supabase every 30 seconds
# rows, errors = fetch_all_data()
# df = pd.DataFrame(rows)

# # Compute a hash of the actual data content
# data_fingerprint = hashlib.md5(pd.util.hash_pandas_object(df).values.tobytes()).hexdigest() if not df.empty else ""

# if "last_data_fingerprint" not in st.session_state:
#     st.session_state.last_data_fingerprint = None
#     st.session_state.last_data_changed_at = datetime.now(timezone.utc).isoformat()

# if data_fingerprint != st.session_state.last_data_fingerprint:
#     st.session_state.last_data_fingerprint = data_fingerprint
#     st.session_state.last_data_changed_at = datetime.now(timezone.utc).isoformat()

# latest_inserted = st.session_state.last_data_changed_at
# YELLOW_MIN = 90
# ORANGE_MIN = 95
# RED_MIN = 100
# PURPLE_MIN = 105

# st.set_page_config(page_title="Disney Heat Index Dashboard", layout="wide")
# SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
# SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# BASE_URL = "http://apidev.accuweather.com"
# API_KEY = st.secrets["ACCUWEATHER_API_KEY"]
# CENTRAL_TZ = ZoneInfo("America/Chicago")
# REFRESH_SECONDS = 120
# STALE_MINUTES = 30

# LOCATION_GROUPS = {
#     "Walt Disney World - Orlando": {
#         "Magic Kingdom": "196686_POI",
#         "Epcot": "70889_POI",
#         "Animal Kingdom": "1-196687_1_POI_AL",
#         "Hollywood Studios": "1-196660_1_POI_AL",
#         "Blizzard Beach": "1-196655_1_POI_AL",
#         "Typhoon Lagoon": "1-196662_1_POI_AL",
#         "Disney Springs": "196663_POI",
#         "Bay Lake": "2257549",
#         "Lake Buena Vista": "2257551",
#     },
#     "Disneyland Resort - California": {
#         "Circle D Ranch": "2154424",
#         "DLR Paradise Pier": "327150",
#         "DLR Main Street": "327150",
#     },
#     "Aulani Resort - Hawaii": {
#         "Aulani Resort and Spa": "2274485",
#     }
# }

# def safe_get(d, *keys):
#     cur = d
#     for k in keys:
#         if cur is None:
#             return None
#         cur = cur.get(k)
#     return cur

# def format_obs_time_ct_short(obs_time):
#     if not obs_time:
#         return ""
#     try:
#         dt = datetime.fromisoformat(obs_time).astimezone(CENTRAL_TZ)
#         month = dt.month
#         day = dt.day
#         hour12 = dt.strftime("%I").lstrip("0") or "0"
#         minute = dt.strftime("%M")
#         ampm = dt.strftime("%p").lower()
#         return f"{month}/{day} {hour12}:{minute}{ampm}"
#     except Exception:
#         return obs_time
        
# def history_all_variables_df(site_name, location_key):
#     cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

#     result = (
#         supabase.table("observations")
#         .select("site_name, inserted_at, obs_time_utc, temp_f, dewpoint_f, rh, wind_speed_mph, wind_gust_mph, wind_dir, heat_index_f")
#         .eq("site_name", site_name)
#         .gte("inserted_at", cutoff)
#         .order("inserted_at", desc=True)
#         .limit(15)
#         .execute()
#     )

#     rows = result.data or []

#     return pd.DataFrame([
#         {
#             "Site": r["site_name"],
#             "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
#             "Temp (F)": r["temp_f"],
#             "Dew Point (F)": r["dewpoint_f"],
#             "RH (%)": r["rh"],
#             "Wind Speed (mph)": r["wind_speed_mph"],
#             "Wind Gust (mph)": r["wind_gust_mph"],
#             "Wind Dir": r["wind_dir"],
#             "Heat Index (F)": r["heat_index_f"],
#             "Heat Index Band": heat_index_band(r["heat_index_f"]),
#         }
#         for r in rows
#     ])
    
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

#     is_heat_index = column_name in ["Heat Index (F)", "Heat Index Band"]

#     cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

#     if is_heat_index:
#         result = (
#             supabase.table("observations")
#             .select("site_name, inserted_at, obs_time_utc, heat_index_f")
#             .eq("site_name", site_name)
#             .gte("inserted_at", cutoff)
#             .order("inserted_at", desc=True)
#             .limit(15)
#             .execute()
#         )

#         rows = result.data or []

#         return pd.DataFrame([
#             {
#                 "Site": r["site_name"],
#                 "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
#                 "Heat Index (F)": r["heat_index_f"],
#                 "Heat Index Band": heat_index_band(r["heat_index_f"]),
#             }
#             for r in rows
#         ])

#     db_col = column_map[column_name]

#     result = (
#         supabase.table("observations")
#         .select(f"site_name, inserted_at, obs_time_utc, {db_col}")
#         .eq("site_name", site_name)
#         .gte("inserted_at", cutoff)
#         .order("inserted_at", desc=True)
#         .limit(15)
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
    
# def history_chart_series(hist_df, column_name):
#     if hist_df.empty:
#         return pd.DataFrame()

#     df = hist_df.copy()
#     df["dt"] = pd.to_datetime(df["Observation Time (CT)"], format="%m/%d %I:%M%p", errors="coerce")

#     if df["dt"].isna().all():
#         df["x_label"] = df["Observation Time (CT)"].astype(str)
#     else:
#         df["x_label"] = df["dt"].dt.strftime("%I:%M%p").str.lstrip("0").str.lower()

#     if column_name in ["Heat Index (F)", "Heat Index Band"]:
#         chart_col = "Heat Index (F)"
#         y_min = 70
#     elif column_name == "Temp (F)":
#         chart_col = "Temp (F)"
#         y_min = 60
#     elif column_name == "Dew Point (F)":
#         chart_col = "Dew Point (F)"
#         y_min = 50
#     elif column_name == "RH (%)":
#         chart_col = "RH (%)"
#         y_min = 0
#     elif column_name in ["Wind Speed (mph)", "Wind Gust (mph)"]:
#         chart_col = column_name
#         y_min = 0
#     else:
#         return pd.DataFrame()
    
#     out = df[["Observation Time (CT)", "x_label", chart_col]].copy()
#     out = out.rename(columns={chart_col: "y"})
#     out["y"] = pd.to_numeric(out["y"], errors="coerce")
#     out = out.dropna(subset=["y"]).reset_index(drop=True)
#     out = out.iloc[::-1].reset_index(drop=True)
    
#     out["x"] = range(len(out))
#     out["y_min"] = y_min
#     return out
    
# def is_dark_theme():
#     try:
#         return st.get_option("theme.base") == "dark"
#     except Exception:
#         return False
        
# def solid_line_color(column_name):
#     if column_name == "Temp (F)":
#         return "#d32f2f"
#     if column_name == "Dew Point (F)":
#         return "#2e7d32"
#     if column_name == "RH (%)":
#         return "#d4ff00"
#     if column_name == "Wind Speed (mph)":
#         return "#2196f3"
#     if column_name == "Wind Gust (mph)":
#         return "#8e24aa"
#     return "#90caf9"

# def hi_segment_color(hi_value):
#     dark = is_dark_theme()

#     # Below threshold ("None")
#     if hi_value is None or pd.isna(hi_value) or hi_value < YELLOW_MIN:
#         return "#ffffff" if dark else "#000000"

#     if hi_value < ORANGE_MIN:
#         return "#fff59d"
#     if hi_value < RED_MIN:
#         return "#ffcc80"
#     if hi_value < PURPLE_MIN:
#         return "#d32f2f"
#     return "#7b1fa2"

# def build_history_chart(hist_df, column_name):
#     plot_df = history_chart_series(hist_df, column_name)
#     if plot_df.empty:
#         return None

#     x = plot_df["x_label"].tolist()
#     y = plot_df["y"].tolist()

#     is_hi = column_name in ["Heat Index (F)", "Heat Index Band"]

#     # --- Units + floor ---
#     if column_name in ["Temp (F)", "Dew Point (F)", "Heat Index (F)", "Heat Index Band"]:
#         unit = "°F"
#         y_floor = 70 if is_hi else (60 if column_name == "Temp (F)" else 50)
#     elif column_name == "RH (%)":
#         unit = "%"
#         y_floor = 0
#     else:
#         unit = "mph"
#         y_floor = 0

#     y_ceiling = max(max(y) + 5, y_floor + 10)

#     fig = go.Figure()

#     # --- Heat Index segmented lines ---
#     if is_hi:
#         for i in range(len(y) - 1):
#             fig.add_trace(go.Scatter(
#                 x=[x[i], x[i+1]],
#                 y=[y[i], y[i+1]],
#                 mode="lines",
#                 line=dict(color=hi_segment_color(y[i+1]), width=3),
#                 hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>"
#             ))

#         # markers layer
#         fig.add_trace(go.Scatter(
#             x=x,
#             y=y,
#             mode="markers",
#             marker=dict(color=[hi_segment_color(v) for v in y], size=6),
#             hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>"
#         ))

#     else:
#         fig.add_trace(go.Scatter(
#             x=x,
#             y=y,
#             mode="lines+markers",
#             line=dict(color=solid_line_color(column_name), width=3),
#             marker=dict(size=6),
#             hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>",
#         ))

#     # --- Title ---
#     if is_hi:
#         title = "Heat Index Over the Last Hour"
#     elif column_name == "Temp (F)":
#         title = "Temperature Over the Last Hour"
#     elif column_name == "Dew Point (F)":
#         title = "Dew Point Over the Last Hour"
#     elif column_name == "RH (%)":
#         title = "Relative Humidity Over the Last Hour"
#     elif column_name == "Wind Speed (mph)":
#         title = "Wind Speed Over the Last Hour"
#     elif column_name == "Wind Gust (mph)":
#         title = "Wind Gusts Over the Last Hour"
#     else:
#         title = f"{column_name} Over the Last Hour"
        
#     if len(y) > 0:
#         latest_x = x[-1]
#         latest_y = y[-1]
    
#         # --- determine color ---
#         if is_hi:
#             label_color = hi_segment_color(latest_y)
#         else:
#             label_color = solid_line_color(column_name)
    
#         # --- label text ---
#         label_text = f"{latest_y:.1f}{unit}"
    
#         # --- add annotation ---
#         fig.add_annotation(
#             x=latest_x,
#             y=latest_y,
#             text=label_text,
#             showarrow=False,
#             xshift=40,
#             yshift=-10,
#             font=dict(size=12, color=label_color),
#             bgcolor="rgba(0,0,0,0)",
#             bordercolor=label_color,
#             borderwidth=1,
#             borderpad=7
#         )
#     # --- Layout ---
#     fig.update_layout(
#         title=dict(
#             text=title,
#             x=0.5,
#             xanchor="center",
#             font=dict(size=14)
#         ),
#         height=260,
#         margin=dict(l=20, r=20, t=30, b=20),
#         xaxis=dict(
#             tickmode="array",
#             tickvals=x,
#             ticktext=x
#         ),
#         yaxis=dict(
#             range=[y_floor, y_ceiling],
#             dtick=10
#         ),
#         showlegend=False,
#         transition=dict(
#             duration=600,
#             easing="cubic-in-out"
#         )
#     )

#     fig.update_traces(connectgaps=True)

#     return fig

# def get_text_color(bg_color):
#     if not bg_color:
#         return "color: inherit;"  # let Streamlit handle default text color

#     # light backgrounds → black text
#     if bg_color in ["#fff59d", "#ffcc80"]:
#         return "black"

#     # dark backgrounds → white text
#     return "white"

# def render_history_panel(selection, group_df):
#     if not selection or "selection" not in selection:
#         return

#     selected_cells = selection["selection"].get("cells", [])
#     if not selected_cells:
#         return

#     table_df = group_df.reset_index(drop=True)

#     row_idx, col_name = selected_cells[0]
#     st.session_state.selected_site = table_df.loc[row_idx, "Site"]
#     st.session_state.selected_column = col_name
#     if row_idx >= len(table_df):
#         return

#     site_name = table_df.loc[row_idx, "Site"]
#     location_key = LOCATION_GROUPS[table_df.loc[row_idx, "Group"]][site_name]

#     if col_name == "Site":
#         with st.expander(f"Last hour for {site_name}", expanded=True):
#             hist_df = history_all_variables_df(site_name, location_key)
#             if hist_df.empty:
#                 st.info("No historical data returned for the past hour.")
#             else:
#                 styled_hist = hist_df.copy()
                
#                 def color_rows(row):
#                     if "Heat Index (F)" in row.index:
#                         color = get_row_color(row["Heat Index (F)"])
#                     else:
#                         color = ""
#                     return [
#                         f"background-color: {color}; color: black;" if color else ""
#                         for _ in row
#                     ]
                    
#                 styled_hist = styled_hist.style.apply(color_rows, axis=1).format({
#                     "Temp (F)": "{:.1f}",
#                     "Dew Point (F)": "{:.1f}",
#                     "RH (%)": "{:.1f}",
#                     "Wind Speed (mph)": "{:.1f}",
#                     "Wind Gust (mph)": "{:.1f}",
#                     "Heat Index (F)": "{:.1f}",
#                 }, na_rep="")
                
#                 st.dataframe(
#                     styled_hist,
#                     width=950,
#                     hide_index=True
#                 )
#         return

#     if col_name not in display_columns or col_name in ["Observation Time (CT)", "Observation Age (min)"]:
#         return

#     with st.expander(f"Last hour for {site_name} — {col_name}", expanded=True):
#         hist_df = history_single_variable_df(site_name, location_key, col_name)

#         if hist_df.empty:
#             st.info("No historical data returned for the past hour.")
#         else:
#             left_col, right_col = st.columns([1.8, 1.2], vertical_alignment="top")

#             with left_col:
#                 styled_hist = hist_df.copy()
                
#                 def color_rows(row):
#                   if "Heat Index (F)" in row.index:
#                     color = get_row_color(row["Heat Index (F)"])
#                   else:
#                     color = ""
#                   return [
#                     f"background-color: {color}; color: black;" if color else ""
#                     for _ in row
#                   ]
                
#                 styled_hist = styled_hist.style.apply(color_rows, axis=1).format({
#                     "Temp (F)": "{:.1f}",
#                     "Dew Point (F)": "{:.1f}",
#                     "RH (%)": "{:.1f}",
#                     "Wind Speed (mph)": "{:.1f}",
#                     "Wind Gust (mph)": "{:.1f}",
#                     "Heat Index (F)": "{:.1f}",
#                 }, na_rep="")
                
#                 st.dataframe(
#                     styled_hist,
#                     width=950,
#                     hide_index=True
#                 )

#             with right_col:
#                 fig = build_history_chart(hist_df, col_name)
#                 if fig is not None:
#                     st.plotly_chart(
#                         fig,
#                         width="stretch",
#                         key=f"chart_{site_name}_{col_name}"
#                     )
                    
# def get_current_conditions(location_key):
#     url = f"{BASE_URL}/currentconditions/v1/{location_key}"
#     params = {
#         "apikey": API_KEY,
#         "details": "true"
#     }
#     r = requests.get(url, params=params, timeout=30)
#     r.raise_for_status()
#     payload = r.json()
#     return payload[0] if payload else None

# def round1(value):
#     if value is None or pd.isna(value):
#         return None
#     return round(float(value), 1)

# def heat_index_f(temp_f, rh):
#     if temp_f is None or rh is None:
#         return None

#     if temp_f < 80 or rh < 40:
#         return round1(temp_f)

#     hi = (
#         -42.379
#         + 2.04901523 * temp_f
#         + 10.14333127 * rh
#         - 0.22475541 * temp_f * rh
#         - 0.00683783 * temp_f * temp_f
#         - 0.05481717 * rh * rh
#         + 0.00122874 * temp_f * temp_f * rh
#         + 0.00085282 * temp_f * rh * rh
#         - 0.00000199 * temp_f * temp_f * rh * rh
#     )

#     if rh < 13 and 80 <= temp_f <= 112:
#         adjustment = ((13 - rh) / 4) * math.sqrt((17 - abs(temp_f - 95)) / 17)
#         hi -= adjustment
#     elif rh > 85 and 80 <= temp_f <= 87:
#         adjustment = ((rh - 85) / 10) * ((87 - temp_f) / 5)
#         hi += adjustment

#     return round1(hi)

# def heat_index_band(hi):
#     if hi is None or hi < YELLOW_MIN:
#         return "None"
#     if hi < ORANGE_MIN:
#         return "Yellow"
#     if hi < RED_MIN:
#         return "Orange"
#     if hi < PURPLE_MIN:
#         return "Red"
#     return "Purple"

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
    
# def parse_obs_time_ct(obs_time):
#     if not obs_time:
#         return ""
#     try:
#         dt = datetime.fromisoformat(obs_time)
#         dt_ct = dt.astimezone(CENTRAL_TZ)
#         month = dt_ct.month
#         day = dt_ct.day
#         hour12 = dt_ct.strftime("%I").lstrip("0") or "0"
#         minute = dt_ct.strftime("%M")
#         ampm = dt_ct.strftime("%p").lower()
#         return f"{month}/{day} {hour12}:{minute}{ampm}"
#     except Exception:
#         return obs_time

# def obs_age_minutes(obs_time):
#     if not obs_time:
#         return None
#     try:
#         dt = datetime.fromisoformat(obs_time)
#         now_utc = datetime.now(timezone.utc)
#         return int(round((now_utc - dt.astimezone(timezone.utc)).total_seconds() / 60.0))
#     except Exception:
#         return None
        
# def stale_text_css(is_stale, hi):
#     if not is_stale:
#         return ""
#     if hi is not None and hi >= RED_MIN:
#         return "color: yellow; font-weight: 700;"
#     return "color: red; font-weight: 700;"
    
# def extract_row(group_name, site_name, key, c):
#     wind = c.get("Wind", {})
#     temp_f = round1(c.get("Temperature", {}).get("Imperial", {}).get("Value"))
#     dewpoint_f = round1(c.get("DewPoint", {}).get("Imperial", {}).get("Value"))
#     rh = round1(c.get("RelativeHumidity"))
#     wind_speed = round1(wind.get("Speed", {}).get("Imperial", {}).get("Value"))
#     wind_gust = round1(c.get("WindGust", {}).get("Speed", {}).get("Imperial", {}).get("Value"))
#     # wind_dir_deg = round1(wind.get("Direction", {}).get("Degrees"))
#     wind_dir = wind.get("Direction", {}).get("Localized")
#     obs_time_raw = c.get("LocalObservationDateTime")
#     age_min = obs_age_minutes(obs_time_raw)
#     hi = heat_index_f(temp_f, rh)

#     return {
#         "Group": group_name,
#         "Site": site_name,
#         "Observation Time (CT)": parse_obs_time_ct(obs_time_raw),
#         "Observation Age (min)": age_min,
#         "Temp (F)": temp_f,
#         "Dew Point (F)": dewpoint_f,
#         "RH (%)": rh,
#         "Wind Speed (mph)": wind_speed,
#         "Wind Gust (mph)": wind_gust,
#         "Wind Dir": wind_dir,
#         "Heat Index (F)": hi,
#         "Heat Index Band": heat_index_band(hi),
#         "_obs_time_raw": obs_time_raw,
#     }

# @st.cache_data(ttl=60, show_spinner=False)
# def fetch_all_data():
#     result = (
#         supabase.table("observations")
#         .select("*")
#         .order("inserted_at", desc=True)
#         .execute()
#     )

#     rows = result.data or []

#     if not rows:
#         return [], ["No Supabase data"]

#     df = pd.DataFrame(rows)

#     # keep only latest per site
#     df = df.sort_values("inserted_at", ascending=False)
#     df = df.drop_duplicates(subset=["site_name"], keep="first")

#     output = []

#     for _, r in df.iterrows():
#         insert_time = datetime.fromisoformat(r["inserted_at"].replace("Z","+00:00"))

#         output.append({
#             "Group": r["group_name"],
#             "Site": r["site_name"],
#             "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
#             "Observation Age (min)": int((datetime.now(timezone.utc) - insert_time).total_seconds()/60),
#             "Temp (F)": round1(r["temp_f"]),
#             "Dew Point (F)": round1(r["dewpoint_f"]),
#             "RH (%)": round1(r["rh"]),
#             "Wind Speed (mph)": round1(r["wind_speed_mph"]),
#             "Wind Gust (mph)": round1(r["wind_gust_mph"]),
#             "Wind Dir": r["wind_dir"],
#             "Heat Index (F)": round1(r["heat_index_f"]),
#             "Heat Index Band": heat_index_band(r["heat_index_f"]),
#         })

#     return output, []

# def get_latest_inserted_time():
#     result = (
#         supabase.table("observations")
#         .select("inserted_at")
#         .order("inserted_at", desc=True)
#         .limit(1)
#         .execute()
#     )

#     rows = result.data or []
#     if not rows:
#         return None

#     return rows[0]["inserted_at"]
    
# def get_row_color(hi):
#     if hi is None or pd.isna(hi) or hi < YELLOW_MIN:
#         return ""
#     if hi < ORANGE_MIN:
#         return "#fff59d"
#     if hi < RED_MIN:
#         return "#ffcc80"
#     if hi < PURPLE_MIN:
#         return "#d32f2f"
#     return "#7b1fa2"
# # def build_status_cards(df):
# #     total_sites = len(df)
# #     stale_count = int((df["Observation Age (min)"] > STALE_MINUTES).fillna(False).sum())
# #     max_hi = df["Heat Index (F)"].max() if not df.empty else None
# #     hottest_site = None
# #     orlando_df = df[df["Group"] == "Walt Disney World - Orlando"]
    
# #     hottest_site = None
    
# #     if not orlando_df.empty and orlando_df["Heat Index (F)"].notna().any():
# #         max_hi = orlando_df["Heat Index (F)"].max()
        
# #         # pick first match (stable)
# #         hottest_site = orlando_df[
# #             orlando_df["Heat Index (F)"] == max_hi
# #         ].iloc[0]["Site"]

# #     yellow_count = int(((df["Heat Index (F)"] >= 90) & (df["Heat Index (F)"] < 95)).sum())
# #     orange_count = int(((df["Heat Index (F)"] >= 95) & (df["Heat Index (F)"] < 100)).sum())
# #     red_count = int(((df["Heat Index (F)"] >= 100) & (df["Heat Index (F)"] < 105)).sum())
# #     purple_count = int((df["Heat Index (F)"] >= 105).sum())

# #     c1, c2, c3, c4 = st.columns(4)
# #     c1.metric("Stations", total_sites)
# #     c2.metric("Stale Obs (>30 min)", stale_count)
# #     c3.metric("Max Heat Index", f"{max_hi:.1f}°F" if pd.notna(max_hi) else "N/A")
# #     c4.metric("Orlando's Highest Heat Index Site", hottest_site if hottest_site else "N/A")

# #     c5, c6, c7, c8 = st.columns(4)
# #     c5.metric("Yellow Rows", yellow_count)
# #     c6.metric("Orange Rows", orange_count)
# #     c7.metric("Red Rows", red_count)
# #     c8.metric("Purple Rows", purple_count)

# def build_status_cards(df):
#     max_hi = df["Heat Index (F)"].max() if not df.empty else None

#     orlando_df = df[df["Group"] == "Walt Disney World - Orlando"]

#     hottest_site = None
#     if not orlando_df.empty and orlando_df["Heat Index (F)"].notna().any():
#         max_orlando_hi = orlando_df["Heat Index (F)"].max()
#         hottest_site = orlando_df[
#             orlando_df["Heat Index (F)"] == max_orlando_hi
#         ].iloc[0]["Site"]

#     c1, c2 = st.columns(2)

#     c1.metric("Max Heat Index", f"{max_hi:.1f}°F" if pd.notna(max_hi) else "N/A")
#     c2.metric("Orlando Highest Site", hottest_site if hottest_site else "N/A")
# st.title("Disney Heat Index Dashboard")

# latest_inserted = get_latest_inserted_time()

# is_dark = st.get_option("theme.base") == "dark"
# text_color = "#ffffff" if is_dark else "#000000"

# components.html(
#     f"""
#     <div style="
#         font-size:16px;
#         font-weight:600;
#         color:{text_color};
#         margin:0;
#         padding:0;
#     ">
#         Last updated: <span id="since">--</span> ago
#     </div>

#     <script>
#         const lastUpdate = new Date("{latest_inserted}");

#         function formatElapsed(seconds) {{
#             const m = Math.floor(seconds / 60);
#             const s = seconds % 60;

#             if (m > 0) {{
#                 return m + "m " + String(s).padStart(2,'0') + "s";
#             }} else {{
#                 return s + "s";
#             }}
#         }}

#         function updateSince() {{
#             const now = new Date();
#             const diff = Math.floor((now - lastUpdate) / 1000);

#             const el = document.getElementById("since");
#             if (el) {{
#                 el.innerText = formatElapsed(diff);
#             }}
#         }}

#         setInterval(updateSince, 1000);
#         updateSince();
#     </script>
#     """,
#     height=28
# )
# st.caption("Auto-refresh every 4 minutes")

# rows, errors = fetch_all_data()
# df = pd.DataFrame(rows)

# if not rows:
#     st.warning("No data returned.")
#     st.stop()


# display_columns = [
#     "Site",
#     "Observation Time (CT)",
#     "Observation Age (min)",
#     "Temp (F)",
#     "Dew Point (F)",
#     "RH (%)",
#     "Wind Speed (mph)",
#     "Wind Gust (mph)",
#     "Wind Dir",
#     "Heat Index (F)",
#     "Heat Index Band",
# ]

# build_status_cards(df)

# for group_name in LOCATION_GROUPS.keys():
#     st.subheader(group_name)

#     group_df = df[df["Group"] == group_name].copy()
#     group_df = group_df.reset_index(drop=True)
#     group_df = group_df.dropna(subset=["Site"])
    
#     table_df = group_df[display_columns].copy()

#     styled_df = table_df.copy()
    
#     def color_rows(row):
#         if "Heat Index (F)" in row.index:
#             color = get_row_color(row["Heat Index (F)"])
#         else:
#             color = ""
#         return [
#             f"background-color: {color}; color: black;" if color else ""
#             for _ in row
#         ]
#     styled_df = styled_df.style.apply(color_rows, axis=1)
    
#     event = st.dataframe(
#         styled_df,
#         width="content",
#         hide_index=True,
#         key=f"table_{group_name}",
#         on_select="rerun",
#         selection_mode="single-cell"
#     )

#     render_history_panel(event, group_df)

# # 🔥 MOVE THIS OUTSIDE LOOP
# if st.session_state.selected_site is not None:
#     for group_name in LOCATION_GROUPS.keys():
#         group_df = df[df["Group"] == group_name].copy().reset_index(drop=True)

#         matches = group_df[group_df["Site"] == st.session_state.selected_site]
#         if not matches.empty:
#             row_idx = matches.index[0]
#             site_name = st.session_state.selected_site
#             col_name = st.session_state.selected_column

#             fake_event = {
#                 "selection": {
#                     "rows": [],
#                     "cells": [(row_idx, col_name)]
#                 }
#             }

#             render_history_panel(fake_event, group_df)
#             break
# st.markdown(
#     """
#     **Heat Index Color Scale**
#     - 90 to 94.9: yellow
#     - 95 to 99.9: orange
#     - 100 to 104.9: red
#     - 105+: purple

#     **Stale Observation Rule**
#     - If observation age is greater than 30 minutes, the observation time and age text turn red
#     - On red/purple heat index rows, stale text turns yellow instead

#     **Time Zone Note**
#     - Observation times are displayed in Central Time

#     ---
#     Click on any site name to pull up the last hour's data for all variables.  
#     Click on any single variable data cell to display the last hour's data for that variable.

#     Click on any one column header to sort it by ascending or descending.
#     """
# )

# now_ct = datetime.now(CENTRAL_TZ)
# st.caption(f"Last page render: {now_ct.month}/{now_ct.day} {now_ct.strftime('%I:%M%p').lstrip('0').lower()} CT")

import math
import hashlib
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st
from supabase import create_client
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

if "selected_site" not in st.session_state:
    st.session_state.selected_site = None

if "selected_column" not in st.session_state:
    st.session_state.selected_column = None

st_autorefresh(interval=30000, key="datarefresh")  # polls supabase every 30 seconds

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
    },
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def safe_get(d, *keys):
    cur = d
    for k in keys:
        if cur is None:
            return None
        cur = cur.get(k)
    return cur


def round1(value):
    if value is None:
        return None
    try:
        v = float(value)
        if pd.isna(v):
            return None
        return round(v, 1)
    except (TypeError, ValueError):
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


# ---------------------------------------------------------------------------
# Heat index calculation & banding
# ---------------------------------------------------------------------------

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
    if hi is None:
        return "None"
    try:
        hi = float(hi)
    except (TypeError, ValueError):
        return "None"
    if pd.isna(hi) or hi < YELLOW_MIN:
        return "None"
    if hi < ORANGE_MIN:
        return "Yellow"
    if hi < RED_MIN:
        return "Orange"
    if hi < PURPLE_MIN:
        return "Red"
    return "Purple"


def _safe_hi_value(hi):
    """Return a float heat index or None — handles every null/NaN variant."""
    if hi is None:
        return None
    try:
        v = float(hi)
        if pd.isna(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def get_row_color(hi):
    v = _safe_hi_value(hi)
    if v is None or v < YELLOW_MIN:
        return ""
    if v < ORANGE_MIN:
        return "#fff59d"
    if v < RED_MIN:
        return "#ffcc80"
    if v < PURPLE_MIN:
        return "#d32f2f"
    return "#7b1fa2"


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


def stale_text_css(is_stale, hi):
    if not is_stale:
        return ""
    if hi is not None and hi >= RED_MIN:
        return "color: yellow; font-weight: 700;"
    return "color: red; font-weight: 700;"


def get_text_color(bg_color):
    if not bg_color:
        return "color: inherit;"
    if bg_color in ["#fff59d", "#ffcc80"]:
        return "black"
    return "white"


# ---------------------------------------------------------------------------
# Shared styling helpers — used everywhere dataframes are styled
# ---------------------------------------------------------------------------

def color_rows(row):
    """Apply background color based on Heat Index (F) if the column exists."""
    if "Heat Index (F)" in row.index:
        color = get_row_color(row["Heat Index (F)"])
    else:
        color = ""
    if color:
        return [f"background-color: {color}; color: black;" for _ in row]
    else:
        return ["" for _ in row]


def build_format_dict(columns):
    """Build .format() dict only for numeric columns present in the dataframe."""
    fmt = {}
    for col in ["Temp (F)", "Dew Point (F)", "RH (%)", "Wind Speed (mph)",
                 "Wind Gust (mph)", "Heat Index (F)"]:
        if col in columns:
            fmt[col] = "{:.1f}"
    return fmt


# ---------------------------------------------------------------------------
# History helpers — single site drill-down
# ---------------------------------------------------------------------------

def history_all_variables_df(site_name, location_key):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    result = (
        supabase.table("observations")
        .select("site_name, inserted_at, obs_time_utc, temp_f, dewpoint_f, rh, "
                "wind_speed_mph, wind_gust_mph, wind_dir, heat_index_f")
        .eq("site_name", site_name)
        .gte("inserted_at", cutoff)
        .order("inserted_at", desc=True)
        .limit(15)
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
            "Heat Index Band": heat_index_band(r["heat_index_f"]),
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
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    if is_heat_index:
        result = (
            supabase.table("observations")
            .select("site_name, inserted_at, obs_time_utc, heat_index_f")
            .eq("site_name", site_name)
            .gte("inserted_at", cutoff)
            .order("inserted_at", desc=True)
            .limit(15)
            .execute()
        )
        rows = result.data or []
        return pd.DataFrame([
            {
                "Site": r["site_name"],
                "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
                "Heat Index (F)": r["heat_index_f"],
                "Heat Index Band": heat_index_band(r["heat_index_f"]),
            }
            for r in rows
        ])

    db_col = column_map.get(column_name)
    if db_col is None:
        return pd.DataFrame()

    result = (
        supabase.table("observations")
        .select(f"site_name, inserted_at, obs_time_utc, {db_col}")
        .eq("site_name", site_name)
        .gte("inserted_at", cutoff)
        .order("inserted_at", desc=True)
        .limit(15)
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


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def history_chart_series(hist_df, column_name):
    if hist_df.empty:
        return pd.DataFrame()

    df = hist_df.copy()
    df["dt"] = pd.to_datetime(df["Observation Time (CT)"],
                               format="%m/%d %I:%M%p", errors="coerce")

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

    if is_hi:
        for i in range(len(y) - 1):
            fig.add_trace(go.Scatter(
                x=[x[i], x[i + 1]],
                y=[y[i], y[i + 1]],
                mode="lines",
                line=dict(color=hi_segment_color(y[i + 1]), width=3),
                hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>",
            ))
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode="markers",
            marker=dict(color=[hi_segment_color(v) for v in y], size=6),
            hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>",
        ))
    else:
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode="lines+markers",
            line=dict(color=solid_line_color(column_name), width=3),
            marker=dict(size=6),
            hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>",
        ))

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
        if is_hi:
            label_color = hi_segment_color(latest_y)
        else:
            label_color = solid_line_color(column_name)
        label_text = f"{latest_y:.1f}{unit}"
        fig.add_annotation(
            x=latest_x, y=latest_y,
            text=label_text,
            showarrow=False,
            xshift=40, yshift=-10,
            font=dict(size=12, color=label_color),
            bgcolor="rgba(0,0,0,0)",
            bordercolor=label_color,
            borderwidth=1, borderpad=7,
        )

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center", font=dict(size=14)),
        height=260,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(tickmode="array", tickvals=x, ticktext=x),
        yaxis=dict(range=[y_floor, y_ceiling], dtick=10),
        showlegend=False,
        transition=dict(duration=600, easing="cubic-in-out"),
    )
    fig.update_traces(connectgaps=True)
    return fig


# ---------------------------------------------------------------------------
# History panel renderer
# ---------------------------------------------------------------------------

def render_history_panel(selection, group_df):
    if not selection or "selection" not in selection:
        return

    selected_cells = selection["selection"].get("cells", [])
    if not selected_cells:
        return

    table_df = group_df.reset_index(drop=True)

    row_idx, col_name = selected_cells[0]
    if row_idx >= len(table_df):
        return

    st.session_state.selected_site = table_df.loc[row_idx, "Site"]
    st.session_state.selected_column = col_name

    site_name = table_df.loc[row_idx, "Site"]
    location_key = LOCATION_GROUPS[table_df.loc[row_idx, "Group"]][site_name]

    # --- Clicked the Site name → show all variables ---
    if col_name == "Site":
        with st.expander(f"Last hour for {site_name}", expanded=True):
            hist_df = history_all_variables_df(site_name, location_key)
            if hist_df.empty:
                st.info("No historical data returned for the past hour.")
            else:
                styled_hist = (
                    hist_df.style
                    .apply(color_rows, axis=1)
                    .format(build_format_dict(hist_df.columns), na_rep="")
                )
                st.dataframe(styled_hist, width=950, hide_index=True)
        return

    # --- Clicked a non-data column → ignore ---
    if col_name not in display_columns or col_name in [
        "Observation Time (CT)", "Observation Age (min)"
    ]:
        return

    # --- Clicked a specific variable → show that variable + chart ---
    with st.expander(f"Last hour for {site_name} — {col_name}", expanded=True):
        hist_df = history_single_variable_df(site_name, location_key, col_name)

        if hist_df.empty:
            st.info("No historical data returned for the past hour.")
        else:
            left_col, right_col = st.columns([1.8, 1.2], vertical_alignment="top")

            with left_col:
                styled_hist = (
                    hist_df.style
                    .apply(color_rows, axis=1)
                    .format(build_format_dict(hist_df.columns), na_rep="")
                )
                st.dataframe(styled_hist, width=950, hide_index=True)

            with right_col:
                fig = build_history_chart(hist_df, col_name)
                if fig is not None:
                    st.plotly_chart(
                        fig, width="stretch",
                        key=f"chart_{site_name}_{col_name}",
                    )


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def extract_row(group_name, site_name, key, c):
    wind = c.get("Wind", {})
    temp_f = round1(c.get("Temperature", {}).get("Imperial", {}).get("Value"))
    dewpoint_f = round1(c.get("DewPoint", {}).get("Imperial", {}).get("Value"))
    rh = round1(c.get("RelativeHumidity"))
    wind_speed = round1(wind.get("Speed", {}).get("Imperial", {}).get("Value"))
    wind_gust = round1(c.get("WindGust", {}).get("Speed", {}).get("Imperial", {}).get("Value"))
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
    """Fetch latest observation per site from Supabase.

    Returns (rows, errors) where rows include all display columns.
    Observation Age is computed fresh each rerun but is NOT part of the
    fingerprint used for the "last updated" timer.
    """
    result = (
        supabase.table("observations")
        .select("*")
        .order("inserted_at", desc=True)
        .execute()
    )

    raw_rows = result.data or []

    if not raw_rows:
        return [], []

    df = pd.DataFrame(raw_rows)
    df = df.sort_values("inserted_at", ascending=False)
    df = df.drop_duplicates(subset=["site_name"], keep="first")

    output = []

    for _, r in df.iterrows():
        insert_time = datetime.fromisoformat(r["inserted_at"].replace("Z", "+00:00"))

        output.append({
            "Group": r["group_name"],
            "Site": r["site_name"],
            "Observation Time (CT)": format_obs_time_ct_short(r["inserted_at"]),
            "Observation Age (min)": int(
                (datetime.now(timezone.utc) - insert_time).total_seconds() / 60
            ),
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


def get_current_conditions(location_key):
    url = f"{BASE_URL}/currentconditions/v1/{location_key}"
    params = {"apikey": API_KEY, "details": "true"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    return payload[0] if payload else None


def build_status_cards(df):
    max_hi = df["Heat Index (F)"].max() if not df.empty else None

    orlando_df = df[df["Group"] == "Walt Disney World - Orlando"]
    hottest_site = None
    if not orlando_df.empty and orlando_df["Heat Index (F)"].notna().any():
        max_orlando_hi = orlando_df["Heat Index (F)"].max()
        hottest_site = orlando_df[
            orlando_df["Heat Index (F)"] == max_orlando_hi
        ].iloc[0]["Site"]

    c1, c2 = st.columns(2)
    c1.metric("Max Heat Index", f"{max_hi:.1f}°F" if pd.notna(max_hi) else "N/A")
    c2.metric("Orlando Highest Site", hottest_site if hottest_site else "N/A")


def compute_stable_fingerprint(rows):
    """Hash the data WITHOUT 'Observation Age (min)' so the fingerprint only
    changes when Supabase actually returns different observation data."""
    if not rows:
        return ""
    # Strip out Observation Age before hashing
    stable = []
    for r in rows:
        s = {k: v for k, v in r.items() if k != "Observation Age (min)"}
        stable.append(s)
    stable_df = pd.DataFrame(stable)
    return hashlib.md5(
        stable_df.to_csv(index=False).encode("utf-8")
    ).hexdigest()


# ===================================================================
# MAIN PAGE
# ===================================================================

st.title("Disney Heat Index Dashboard")

# --- Fetch data ---
rows, errors = fetch_all_data()
df = pd.DataFrame(rows)

# --- Fingerprint: only changes when the actual observation data changes,
#     NOT when Observation Age recalculates on each rerun ---
if "last_data_fingerprint" not in st.session_state:
    st.session_state.last_data_fingerprint = None
    st.session_state.last_data_changed_at = datetime.now(timezone.utc).isoformat()

current_fingerprint = compute_stable_fingerprint(rows)

if current_fingerprint != st.session_state.last_data_fingerprint:
    st.session_state.last_data_fingerprint = current_fingerprint
    st.session_state.last_data_changed_at = datetime.now(timezone.utc).isoformat()

latest_changed = st.session_state.last_data_changed_at

# --- "Last updated" live timer ---
# The JS gets re-rendered every Streamlit rerun (every 30s poll), but
# `latest_changed` only updates when the fingerprint changes, so the
# timer jumps to the correct elapsed time immediately on re-render
# rather than resetting to 0.
is_dark = is_dark_theme()
text_color = "#ffffff" if is_dark else "#000000"

components.html(
    f"""
    <div style="
        font-size:16px;
        font-weight:600;
        color:{text_color};
        margin:0;
        padding:0;
    ">
        Last updated: <span id="since">--</span> ago
    </div>

    <script>
        const lastUpdate = new Date("{latest_changed}");

        function formatElapsed(seconds) {{
            const m = Math.floor(seconds / 60);
            const s = seconds % 60;
            if (m > 0) {{
                return m + "m " + String(s).padStart(2,'0') + "s";
            }}
            return s + "s";
        }}

        function updateSince() {{
            const now = new Date();
            const diff = Math.max(0, Math.floor((now - lastUpdate) / 1000));
            const el = document.getElementById("since");
            if (el) {{
                el.innerText = formatElapsed(diff);
            }}
        }}

        setInterval(updateSince, 1000);
        updateSince();
    </script>
    """,
    height=28,
)
st.caption("Auto-refresh every 4 minutes")

if not rows:
    st.warning("No data returned.")
    st.stop()

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

    styled_df = (
        table_df.style
        .apply(color_rows, axis=1)
        .format(build_format_dict(table_df.columns), na_rep="")
    )

    event = st.dataframe(
        styled_df,
        width="content",
        hide_index=True,
        key=f"table_{group_name}",
        on_select="rerun",
        selection_mode="single-cell",
    )

    render_history_panel(event, group_df)

# Persist selected panel across refreshes
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
                    "cells": [(row_idx, col_name)],
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
st.caption(
    f"Last page render: {now_ct.month}/{now_ct.day} "
    f"{now_ct.strftime('%I:%M%p').lstrip('0').lower()} CT"
)
