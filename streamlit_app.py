import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import base64

# ---------- CONFIG ----------
st.set_page_config(page_title=" FlightOps Dashboard", layout="wide")

# ---------- STYLING ----------
st.markdown(
    """
    <style>
        /* Page background */
        body, .main, .block-container {
            background-color: #f5f7fa !important;
            color: #1a1a1a !important;
        }

        /* Card style */
        .card {
            background-color: #ffffff;
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0px 2px 10px rgba(0, 0, 0, 0.06);
        }

        /* Big numbers font */
        .big-font {
            font-size: 36px !important;
            font-weight: bold;
            color: #0d47a1;  /* Deep blue */
        }

        /* Header text */
        h2, h3, h4 {
            color: #1a1a1a;
        }

        /* Streamlit metrics text center */
        .stMetric {
            text-align: center !important;
        }

        /* Sidebar and other background elements */
        .css-18ni7ap, .css-1d391kg, .css-1v3fvcr {
            background-color: #eaf0f6 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)


# ---------- LOAD DATA ----------
@st.cache_data(ttl=60)  # cache only for 60 seconds
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
    k1.markdown(f"<div class='card'><h3> Total Flights</h3><p class='big-font'>{t_total}</p></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='card'><h3> Total Time</h3><p class='big-font'>{t_total_formatted}</p></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='card'><h3> Failed Flights</h3><p class='big-font'>{t_fail}</p></div>", unsafe_allow_html=True)


   # Prepare summary data
    status_summary = df_t['Flight_Status'].value_counts().reset_index()
    status_summary.columns = ['Flight_Status', 'Flight Count']

    # Create pie chart
    st.subheader("Trishul Flight Status")
    fig_t_pie = px.pie(
        status_summary,
        names='Flight_Status',
        values='Flight Count',
        color='Flight_Status',
        color_discrete_map={
            'Pass': 'green',
            'Fail': 'red',
            'Unknown': 'gray'
        }
    )

    # Custom hover template: "Pass = 12 flights"
    fig_t_pie.update_traces(
        hovertemplate="%{label} = %{value} flights"
    )

    fig_t_pie.update_layout(width=400, height=500)
    st.plotly_chart(fig_t_pie, use_container_width=True)

    # Interactive dropdown
    st.markdown("####  Trishul Flight Summary by Flight Status")

    selected_status = st.selectbox(
        "Select Status",
        options=['Pass', 'Fail', 'Unknown'],
        key="status_filter"
    )

    filtered_drones = df_t[df_t['Flight_Status'] == selected_status]['Vehicle_Name'].dropna().unique().tolist()

    if filtered_drones:
        st.markdown(
            f"<div style='background-color:#d0ebff; color:#003366; padding: 10px; border-radius: 8px;'>"
            f"<strong> Drones with status '{selected_status}':</strong> {', '.join(filtered_drones)}"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='background-color:#fff3cd; color:#8a6d3b; padding: 10px; border-radius: 8px;'>"
            f" No drones found with status '<strong>{selected_status}</strong>'."
            f"</div>",
            unsafe_allow_html=True
        )

    # ------------------- CHART: FLIGHTS PER DRONE (Trishul) ----------
    st.subheader("📊 Flights Per Drone (Trishul)")
    
    # Group data by Vehicle_Name
    t_summary = df_t.groupby('Vehicle_Name').agg({
        'Duration_Min': 'sum',
        'Vehicle_Name': 'count'
    }).rename(columns={'Vehicle_Name': 'Flight Count', 'Duration_Min': 'Total Minutes'}).reset_index()

    # Add human-readable time
    t_summary['Total Time'] = t_summary['Total Minutes'].apply(
        lambda x: f"{int(x // 60)} hr {int(x % 60)} min"
    )
    
    # Plotly bar chart with hover
    fig_trishul = px.bar(
        t_summary,
        x='Vehicle_Name',
        y='Flight Count',
        color='Vehicle_Name',
        hover_data={'Total Time': True, 'Total Minutes': False},
        labels={'Vehicle_Name': 'Drone', 'Flight Count': 'Flight Count'},
    )
    fig_trishul.update_layout(height=500)
    st.plotly_chart(fig_trishul, use_container_width=True)
    
    
    # Filter UI at the bottom
    st.markdown("#### Trishul Operator Overview")
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

        st.subheader(f" Daily Flight Log for {pilot_trishul}")
        st.dataframe(daily_flights_t)

        total_minutes = pilot_daily['Duration_Min'].sum()
        total_hr = int(total_minutes // 60)
        total_min = int(total_minutes % 60)

        st.markdown(
            f"<div style='background-color:#d4edda; color:#155724; padding:10px; border-radius:8px;'>"
            f" <strong>Total Flight Time for {pilot_trishul}:</strong> {total_hr} hr {total_min} min"
            f"</div>",
            unsafe_allow_html=True
        )

        drone_list = pilot_daily['Vehicle_Name'].dropna().unique().tolist()
        if drone_list:
            drone_list_str = ", ".join(drone_list)
            st.markdown(
                f"<div style='background-color:#d0ebff; color:#003366; padding:10px; border-radius:8px;'>"
                f" <strong>Drones Flown by {pilot_trishul}:</strong> {drone_list_str}"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style='background-color:#fff3cd; color:#8a6d3b; padding:10px; border-radius:8px;'>"
                f" <strong>No drone records found for {pilot_trishul}.</strong>"
                f"</div>",
                unsafe_allow_html=True
            )

        
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
    j1.markdown(f"<div class='card'><h3> Total Flights</h3><p class='big-font'>{k_total}</p></div>", unsafe_allow_html=True)
    j2.markdown(f"<div class='card'><h3> Total Time</h3><p class='big-font'>{k_total_formatted}</p></div>", unsafe_allow_html=True)
    j3.markdown(f"<div class='card'><h3> Failed Flights</h3><p class='big-font'>{k_fail}</p></div>", unsafe_allow_html=True)

    # Prepare summary data
    status_summary_k = df_k['Flight_Status'].value_counts().reset_index()
    status_summary_k.columns = ['Flight_Status', 'Flight Count']

    # Create pie chart
    st.subheader("Kamet Flight Status")
    fig_k_pie = px.pie(
        status_summary_k,
        names='Flight_Status',
        values='Flight Count',
        color='Flight_Status',
        color_discrete_map={
            'Pass': 'green',
            'Fail': 'red',
            'Unknown': 'gray'
        }
    )

    # Custom hover template
    fig_k_pie.update_traces(
        hovertemplate="%{label} = %{value} flights"
    )

    fig_k_pie.update_layout(width=400, height=500)
    st.plotly_chart(fig_k_pie, use_container_width=True)
    
    # ---------- Interactive Drone List by Flight Status (Kamet) ----------
    st.markdown("#### Kamet Flight Summary by Flight Status")

    selected_status_kamet = st.selectbox(
        "Select Status",
        options=['Pass', 'Fail', 'Unknown'],
        key="kamet_status_filter"
    )

    filtered_drones_kamet = df_k[df_k['Flight_Status'] == selected_status_kamet]['Vehicle_Name'].dropna().unique().tolist()

    if filtered_drones_kamet:
        st.markdown(
            f"<div style='background-color:#d0ebff; color:#003366; padding: 10px; border-radius: 8px;'>"
            f"<strong> Drones with status '{selected_status_kamet}':</strong> {', '.join(filtered_drones_kamet)}"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='background-color:#fff3cd; color:#8a6d3b; padding: 10px; border-radius: 8px;'>"
            f" No drones found with status '<strong>{selected_status_kamet}</strong>'."
            f"</div>",
            unsafe_allow_html=True
        )
    
    # ------------------- CHART: FLIGHTS PER DRONE (Kamet) ---------- #
    st.subheader("📊 Flights Per Drone (Kamet)")
    
    # Group by Vehicle_Name to get flight count and total duration
    k_summary = df_k.groupby('Vehicle_Name').agg({
        'Duration_Min': 'sum',
        'Vehicle_Name': 'count'
    }).rename(columns={'Vehicle_Name': 'Flight Count', 'Duration_Min': 'Total Minutes'}).reset_index()

    # Format total time as "X hr Y min"
    k_summary['Total Time'] = k_summary['Total Minutes'].apply(
        lambda x: f"{int(x // 60)} hr {int(x % 60)} min"
    )
    
    # Plot bar chart
    fig_kamet = px.bar(
        k_summary,
        x='Vehicle_Name',
        y='Flight Count',
        color='Vehicle_Name',
        hover_data={'Total Time': True, 'Total Minutes': False},
        labels={'Vehicle_Name': 'Drone', 'Flight Count': 'Flight Count'},
    )

    fig_kamet.update_layout(height=500)
    st.plotly_chart(fig_kamet, use_container_width=True)
    
    # Filter UI at the bottom
    st.markdown("#### Kamet Operator Overview")
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

        st.subheader(f" Daily Flight Log for {pilot_kamet}")
        st.dataframe(daily_flights_k)

        total_minutes_k = pilot_daily['Duration_Min'].sum()
        total_hr = int(total_minutes_k // 60)
        total_min = int(total_minutes_k % 60)

        st.markdown(
            f"<div style='background-color:#d4edda; color:#155724; padding:10px; border-radius:8px;'>"
            f" <strong>Total Flight Time for {pilot_kamet}:</strong> {total_hr} hr {total_min} min"
            f"</div>",
            unsafe_allow_html=True
        )

        drone_list = pilot_daily['Vehicle_Name'].dropna().unique().tolist()
        if drone_list:
            drone_list_str = ", ".join(drone_list)
            st.markdown(
                f"<div style='background-color:#d0ebff; color:#003366; padding:10px; border-radius:8px;'>"
                f" <strong>Drones Flown by {pilot_kamet}:</strong> {drone_list_str}"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style='background-color:#fff3cd; color:#8a6d3b; padding:10px; border-radius:8px;'>"
                f" <strong>No drone records found for {pilot_kamet}.</strong>"
                f"</div>",
                unsafe_allow_html=True
            )


# ---------- DOWNLOAD CLEANED DATA ----------
csv_data = df.to_csv(index=False)
b64 = base64.b64encode(csv_data.encode()).decode()

st.markdown(f"""
    <style>
    .download-container {{
        text-align: center;
        margin-top: 30px;
    }}

    .download-btn {{
        background-color: #ffffff;
        color: #0d47a1;
        font-size: 16px;
        padding: 14px 28px;
        border: 2px solid #0d47a1;
        border-radius: 12px;
        cursor: pointer;
        font-weight: bold;
        box-shadow: 0px 0px 10px rgba(0, 71, 171, 0.4);
        transition: all 0.3s ease;
        animation: pulse 2s infinite;
    }}

    .download-btn:hover {{
        background-color: #e3f2fd;
        color: #003c8f;
        box-shadow: 0 0 20px rgba(0, 71, 171, 0.7);
        transform: scale(1.05);
    }}

    @keyframes pulse {{
        0% {{ box-shadow: 0 0 10px rgba(0, 71, 171, 0.4); }}
        50% {{ box-shadow: 0 0 20px rgba(0, 71, 171, 0.8); }}
        100% {{ box-shadow: 0 0 10px rgba(0, 71, 171, 0.4); }}
    }}
    </style>

    <div class="download-container">
        <h3>📁 Download FlightOps Data</h3>
        <a href="data:file/csv;base64,{b64}" download="filtered_flight_data.csv">
            <button class="download-btn">⬇️ Download CSV</button>
        </a>
    </div>
""", unsafe_allow_html=True)
# ---------- FOOTER ----------
st.markdown("---", unsafe_allow_html=True)
st.markdown(
    """
    <div style='text-align: center; font-size: 18px;'>
        DCM Shriram  FlightOps Dashboard<br>
        <span style='font-size: 14px; color: gray;'>&copy; 2025 DCM Shriram Ltd. All rights reserved.</span>
    </div>
    """,
    unsafe_allow_html=True
)
