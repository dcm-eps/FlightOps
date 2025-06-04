import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ---------- CONFIG ----------
st.set_page_config(page_title=" FlightOps Dashboard", layout="wide")

# ---------- STYLING ----------
st.markdown(
    """
    <style>
        .big-font {
            font-size: 40px !important;
            color: #FF4B4B;
        }
        .card {
            background-color: #1e1e1e;
            padding: 1rem;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0px 0px 10px #ff4b4b50;
        }
        .stMetric {
            text-align: center !important;
        }
    </style>
    """, unsafe_allow_html=True
)

# ---------- LOAD DATA ----------
@st.cache_data
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Pre-Post Flight Data").sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    df['Takeoff_Time'] = pd.to_datetime(df['Takeoff_Time'], errors='coerce')
    df['Landing_time'] = pd.to_datetime(df['Landing_time'], errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date

    df['Duration_Min'] = (df['Landing_time'] - df['Takeoff_Time']).dt.total_seconds() / 60
    df['Duration_Human'] = df['Duration_Min'].apply(
        lambda x: f"{int(x // 60)} hr {int(x % 60)} min" if pd.notnull(x) else "N/A"
    )

    def classify_status(x):
        x = str(x).strip().lower()
        if x == 'yes':
            return 'Fail'
        elif x == 'no':
            return 'Pass'
        else:
            return 'Unknown'

    df['Flight_Status'] = df['Incident_Occurred'].apply(classify_status)
    df['Group'] = df['Vehicle_Name'].apply(lambda x: 'Trishul' if 'trishul' in str(x).lower() else 'Kamet')

    return df

df = load_data()

# ---------- SPLIT DATA ----------
df_trishul = df[df['Group'] == 'Trishul']
df_kamet = df[df['Group'] == 'Kamet']

# ---------- PILOT FILTERS (apply early, display later) ----------
pilot_trishul = st.session_state.get("pilot_trishul", "All")
pilot_kamet = st.session_state.get("pilot_kamet", "All")

df_t = df_trishul.copy()
if pilot_trishul != "All":
    df_t = df_t[df_t['Pilot_Name'] == pilot_trishul]

df_k = df_kamet.copy()
if pilot_kamet != "All":
    df_k = df_k[df_k['Pilot_Name'] == pilot_kamet]

# ---------- DASHBOARD LAYOUT ----------
col1, col2 = st.columns(2)

# ---------- TRISHUL COLUMN ----------
with col1:
    st.markdown("<h2 style='text-align: center;'>Trishul Drone</h2>", unsafe_allow_html=True)
    
    t_total = len(df_t)
    total_minutes = df_t['Duration_Min'].sum()
    t_total_h = int(total_minutes // 60)
    t_total_m = int(total_minutes % 60)
    t_total_formatted = f"{t_total_h} hr {t_total_m} min"
    t_fail = len(df_t[df_t['Flight_Status'] == 'Fail'])

    k1, k2, k3 = st.columns(3)
    k1.markdown(f"<div class='card'><h3>✈️ Total Flights</h3><p class='big-font'>{t_total}</p></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='card'><h3>⏱ Total Time</h3><p class='big-font'>{t_total_formatted}</p></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='card'><h3>⚠️ Failed Flights</h3><p class='big-font'>{t_fail}</p></div>", unsafe_allow_html=True)

    st.subheader("🕵️ Pass vs Fail (Trishul)")
    # Display static pie chart
    fig_t_pie = px.pie(
        df_t,
        names='Flight_Status',
        title="Trishul Flight Status",
        color='Flight_Status',
        color_discrete_map={
            'Pass': 'green',
            'Fail': 'red',
            'Unknown': 'gray'
        }
    )
    fig_t_pie.update_layout(width=400, height=500)
    st.plotly_chart(fig_t_pie, use_container_width=True)

    # Interactive dropdown
    st.markdown("#### 🔍 View Drones by Flight Status (Trishul)")
    selected_status = st.selectbox("Select Status", options=['Pass', 'Fail', 'Unknown'], key="status_filter")

    # Filter and display drone list
    filtered_drones = df_t[df_t['Flight_Status'] == selected_status]['Vehicle_Name'].dropna().unique().tolist()

    if filtered_drones:
        st.info(f"🛩️ **Drones with status '{selected_status}':** " + ", ".join(filtered_drones))
    else:
        st.warning(f"No drones found with status '{selected_status}'.")

    # ------------------- CHART: FLIGHTS PER DRONE (Trishul) ----------
    st.subheader("📊 Flights Per Drone (Trishul)")
    t_counts = df_t['Vehicle_Name'].value_counts().reset_index(name='count').rename(columns={'index': 'Vehicle_Name'})
    fig_trishul = px.bar(
        t_counts,
        x='Vehicle_Name',
        y='count',
        color='Vehicle_Name',
        labels={'Vehicle_Name': 'Drone', 'count': 'Flight Count'},
        title="Flights Per Trishul Drone"
    )
    st.plotly_chart(fig_trishul, use_container_width=True)
    
    
    # Filter UI at the bottom
    st.markdown("#### 🔍 Trishul Pilots")
    pilot_trishul = st.selectbox(
        "Pilots (Trishul)",
        ["All"] + sorted(df_trishul['Pilot_Name'].dropna().unique()),
        key="trishul"
    )

    # ---------- CHART: FLIGHTS PER PILOT PER DAY (Trishul) ----------
    if pilot_trishul != "All":
        pilot_daily = df_trishul[df_trishul['Pilot_Name'] == pilot_trishul].copy()
        daily_flights_t = pilot_daily.groupby(['Pilot_Name', 'Date']).size().reset_index(name='Flights')
        daily_flights_t.reset_index(drop=True, inplace=True)
        daily_flights_t.insert(0, 'S.No', range(1, len(daily_flights_t) + 1))

        st.subheader(f" Daily Flight Log for {pilot_trishul}")
        st.dataframe(daily_flights_t)

        total_minutes = pilot_daily['Duration_Min'].sum()
        total_hr = int(total_minutes // 60)
        total_min = int(total_minutes % 60)
        st.success(f"🕐 Total Flight Time for {pilot_trishul}: {total_hr} hr {total_min} min")

        drone_list = pilot_daily['Vehicle_Name'].dropna().unique().tolist()
        if drone_list:
            drone_list_str = ", ".join(drone_list)
            st.info(f"✈️ Drones Flown by {pilot_trishul}: {drone_list_str}")
        else:
            st.warning(f"No drone records found for {pilot_trishul}.")
        
# ---------- KAMET COLUMN ----------
with col2:
    st.markdown("<h2 style='text-align: center;'>Kamet Drone</h2>", unsafe_allow_html=True)

    k_total = len(df_k)
    total_minutes_k = df_k['Duration_Min'].sum()
    k_total_h = int(total_minutes_k // 60)
    k_total_m = int(total_minutes_k % 60)
    k_total_formatted = f"{k_total_h} hr {k_total_m} min"
    k_fail = len(df_k[df_k['Flight_Status'] == 'Fail'])

    j1, j2, j3 = st.columns(3)
    j1.markdown(f"<div class='card'><h3>✈️ Total Flights</h3><p class='big-font'>{k_total}</p></div>", unsafe_allow_html=True)
    j2.markdown(f"<div class='card'><h3>⏱ Total Time</h3><p class='big-font'>{k_total_formatted}</p></div>", unsafe_allow_html=True)
    j3.markdown(f"<div class='card'><h3>⚠️ Failed Flights</h3><p class='big-font'>{k_fail}</p></div>", unsafe_allow_html=True)

    st.subheader("🕵️ Pass vs Fail (Kamet)")
    fig_k_pie = px.pie(
        df_k,
        names='Flight_Status',
        title="Kamet Flight Status",
        color='Flight_Status',
        color_discrete_map={
            'Pass': 'green',
            'Fail': 'red',
            'Unknown': 'gray'
        }
    )
    fig_k_pie.update_layout(width=400, height=500)
    st.plotly_chart(fig_k_pie, use_container_width=True)
    
    # ---------- Interactive Drone List by Flight Status (Kamet) ----------
    st.markdown("#### 🔍 View Drones by Flight Status (Kamet)")

    selected_status_kamet = st.selectbox(
        "Select Status",
        options=['Pass', 'Fail', 'Unknown'],
        key="kamet_status_filter"
    )

    filtered_drones_kamet = df_k[df_k['Flight_Status'] == selected_status_kamet]['Vehicle_Name'].dropna().unique().tolist()

    if filtered_drones_kamet:
        st.info(f"🛩️ **Drones with status '{selected_status_kamet}':** " + ", ".join(filtered_drones_kamet))
    else:
        st.warning(f"No drones found with status '{selected_status_kamet}'.")
    
    # ------------------- CHART: FLIGHTS PER DRONE (Kamet) ---------- #
    st.subheader("📊 Flights Per Drone (Kamet)")
    k_counts = df_k['Vehicle_Name'].value_counts().reset_index(name='count').rename(columns={'index': 'Vehicle_Name'})
    fig_kamet = px.bar(
        k_counts,
        x='Vehicle_Name',
        y='count',
        color='Vehicle_Name',
        labels={'Vehicle_Name': 'Drone', 'count': 'Flight Count'},
        title="Flights Per Kamet Drone"
    )
    st.plotly_chart(fig_kamet, use_container_width=True)
    
    
    # Filter UI at the bottom
    st.markdown("#### 🔍 Kamet Pilots")
    pilot_kamet = st.selectbox(
        "Pilots (Kamet)",
        ["All"] + sorted(df_kamet['Pilot_Name'].dropna().unique()),
        key="kamet"
    )
    
    # ---------- CHART: FLIGHTS PER PILOT PER DAY (Kamet) ----------
    if pilot_kamet != "All":
        pilot_daily = df_kamet[df_kamet['Pilot_Name'] == pilot_kamet].copy()
        daily_flights_k = pilot_daily.groupby(['Pilot_Name', 'Date']).size().reset_index(name='Flights')
        daily_flights_k.reset_index(drop=True, inplace=True)
        daily_flights_k.insert(0, 'S.No', range(1, len(daily_flights_k) + 1))

        st.subheader(f" Daily Flight Log for {pilot_kamet}")
        st.dataframe(daily_flights_k)

        total_minutes_k = pilot_daily['Duration_Min'].sum()
        total_hr = int(total_minutes_k // 60)
        total_min = int(total_minutes_k % 60)
        st.success(f"🕐 Total Flight Time for {pilot_kamet}: {total_hr} hr {total_min} min")

        drone_list = pilot_daily['Vehicle_Name'].dropna().unique().tolist()
        if drone_list:
            drone_list_str = ", ".join(drone_list)
            st.info(f"✈️ Drones Flown by {pilot_kamet}: {drone_list_str}")
        else:
            st.warning(f"No drone records found for {pilot_kamet}.")

# ---------- DOWNLOAD CLEANED DATA ----------
st.markdown("### 📁 Download Processed Data")
st.download_button("Download CSV", data=df.to_csv(index=False), file_name="filtered_flight_data.csv")

# ---------- FOOTER ----------
st.markdown("---", unsafe_allow_html=True)
st.markdown(
    """
    <div style='text-align: center; font-size: 18px;'>
        DCM Shriram ✈️ FlightOps Dashboard<br>
        <span style='font-size: 14px; color: gray;'>&copy; 2025 DCM Shriram Ltd. All rights reserved.</span>
    </div>
    """,
    unsafe_allow_html=True
)
