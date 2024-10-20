import streamlit as st
import fastf1
import fastf1.plotting
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
import time

# Page configuration
st.set_page_config(
    page_title="F1 Data Analysis Hub",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
        .stButton>button {
            width: 100%;
        }
        .streamlit-expanderHeader {
            font-size: 18px;
        }
        .stProgress .st-bo {
            background-color: red;
        }
    </style>
""", unsafe_allow_html=True)

# Initialize FastF1
@st.cache_resource
def initialize_fastf1():
    fastf1.Cache.enable_cache('f1_cache')
    fastf1.plotting.setup_mpl()

initialize_fastf1()

# Session loading with caching
@st.cache_data(ttl=3600)
def load_session_data(year, grand_prix, session_type):
    """Load and cache session data"""
    try:
        session = fastf1.get_session(year, grand_prix, session_type)
        session.load()
        return session
    except Exception as e:
        st.error(f"Error loading session data: {str(e)}")
        return None

@st.cache_data
def get_schedule(year):
    """Get and cache F1 schedule"""
    return fastf1.get_event_schedule(year)

def create_lap_time_chart(session, selected_drivers):
    """Create interactive lap time comparison chart"""
    lap_times_data = []
    
    for driver in selected_drivers:
        driver_laps = session.laps.pick_driver(driver)
        driver_info = session.get_driver(driver)
        
        for _, lap in driver_laps.iterrows():
            if pd.notnull(lap['LapTime']):
                compound = lap['Compound'] if 'Compound' in lap else 'Unknown'
                lap_times_data.append({
                    'Driver': driver_info['Abbreviation'],
                    'Lap Number': lap['LapNumber'],
                    'Lap Time': lap['LapTime'].total_seconds(),
                    'Compound': compound,
                    'Sector 1': lap['Sector1Time'].total_seconds() if pd.notnull(lap['Sector1Time']) else None,
                    'Sector 2': lap['Sector2Time'].total_seconds() if pd.notnull(lap['Sector2Time']) else None,
                    'Sector 3': lap['Sector3Time'].total_seconds() if pd.notnull(lap['Sector3Time']) else None,
                })
    
    return pd.DataFrame(lap_times_data) if lap_times_data else None

def create_telemetry_plot(session, driver, lap_number=None):
    """Create detailed telemetry visualization"""
    if lap_number:
        lap = session.laps.pick_driver(driver).pick_lap(lap_number)
    else:
        lap = session.laps.pick_driver(driver).pick_fastest()
    
    if lap is not None:
        telemetry = lap.get_telemetry()
        
        fig = go.Figure()
        
        # Speed trace
        fig.add_trace(go.Scatter(
            x=telemetry['Distance'],
            y=telemetry['Speed'],
            name='Speed',
            line=dict(color='blue')
        ))
        
        # Throttle
        if 'Throttle' in telemetry.columns:
            fig.add_trace(go.Scatter(
                x=telemetry['Distance'],
                y=telemetry['Throttle'],
                name='Throttle',
                line=dict(color='green')
            ))
        
        # Brake
        if 'Brake' in telemetry.columns:
            fig.add_trace(go.Scatter(
                x=telemetry['Distance'],
                y=telemetry['Brake'] * 100,  # Convert to percentage
                name='Brake',
                line=dict(color='red')
            ))
        
        fig.update_layout(
            title=f'Telemetry - {driver} (Lap {lap["LapNumber"]})',
            xaxis_title='Distance (m)',
            yaxis_title='Value',
            hovermode='x unified'
        )
        
        return fig
    return None

def main():
    # Title and introduction
    st.title("🏎️ Formula 1 Data Analysis Hub")
    st.markdown("""
    Analyze real-time Formula 1 data including lap times, telemetry, and race statistics.
    Select a season, race, and session to begin your analysis.
    """)
    
    # Sidebar controls
    with st.sidebar:
        st.header("Session Selection")
        
        current_year = datetime.now().year
        year = st.selectbox("Select Year", range(current_year, 2018, -1))
        
        # Get available races for selected year
        schedule = get_schedule(year)
        races = schedule['EventName'].tolist()
        grand_prix = st.selectbox("Select Grand Prix", races)
        
        session_types = ['R', 'Q', 'FP1', 'FP2', 'FP3', 'S']
        session_type = st.selectbox(
            "Select Session",
            session_types,
            format_func=lambda x: {
                'R': 'Race',
                'Q': 'Qualifying',
                'S': 'Sprint',
                'FP1': 'Practice 1',
                'FP2': 'Practice 2',
                'FP3': 'Practice 3'
            }[x]
        )
        
        if st.button("Load Session Data", key="load_data"):
            with st.spinner("Loading session data..."):
                session = load_session_data(year, grand_prix, session_type)
                if session:
                    st.session_state['session'] = session
                    st.session_state['drivers'] = sorted(session.drivers)
                    st.success("✅ Session data loaded successfully!")
    
    # Main dashboard
    if 'session' in st.session_state:
        session = st.session_state['session']
        
        # Driver selection
        selected_drivers = st.multiselect(
            "Select Drivers to Compare",
            st.session_state['drivers'],
            default=st.session_state['drivers'][:3]
        )
        
        if selected_drivers:
            # Create tabs for different analyses
            tab1, tab2, tab3 = st.tabs(["📊 Lap Analysis", "📈 Telemetry", "📋 Statistics"])
            
            with tab1:
                st.header("Lap Times Analysis")
                lap_data = create_lap_time_chart(session, selected_drivers)
                
                if lap_data is not None:
                    # Lap times plot
                    fig_lap_times = px.line(
                        lap_data,
                        x='Lap Number',
                        y='Lap Time',
                        color='Driver',
                        symbol='Compound',
                        title='Lap Times Comparison'
                    )
                    st.plotly_chart(fig_lap_times, use_container_width=True)
                    
                    # Sector times
                    st.subheader("Sector Times Analysis")
                    sector_cols = ['Sector 1', 'Sector 2', 'Sector 3']
                    sector_data = lap_data[['Driver'] + sector_cols].groupby('Driver').mean()
                    
                    fig_sectors = go.Figure()
                    for driver in sector_data.index:
                        fig_sectors.add_trace(go.Bar(
                            name=driver,
                            x=sector_cols,
                            y=sector_data.loc[driver],
                            text=sector_data.loc[driver].round(3),
                            textposition='auto',
                        ))
                    
                    fig_sectors.update_layout(
                        title='Average Sector Times',
                        barmode='group',
                        yaxis_title='Time (seconds)'
                    )
                    st.plotly_chart(fig_sectors, use_container_width=True)
            
            with tab2:
                st.header("Telemetry Analysis")
                
                col1, col2 = st.columns(2)
                with col1:
                    driver = st.selectbox("Select Driver", selected_drivers)
                
                if driver:
                    with col2:
                        driver_laps = session.laps.pick_driver(driver)
                        lap_numbers = driver_laps['LapNumber'].tolist()
                        selected_lap = st.selectbox("Select Lap Number", lap_numbers)
                    
                    if selected_lap:
                        fig_telemetry = create_telemetry_plot(session, driver, selected_lap)
                        if fig_telemetry:
                            st.plotly_chart(fig_telemetry, use_container_width=True)
            
            with tab3:
                st.header("Session Statistics")
                
                # Fastest laps
                with st.expander("Fastest Laps", expanded=True):
                    fastest_laps = []
                    for driver in selected_drivers:
                        driver_fastest = session.laps.pick_driver(driver).pick_fastest()
                        if driver_fastest is not None:
                            fastest_laps.append({
                                'Driver': driver,
                                'Time': driver_fastest['LapTime'],
                                'Lap': driver_fastest['LapNumber'],
                                'Speed (km/h)': driver_fastest['SpeedI2'] if 'SpeedI2' in driver_fastest else None
                            })
                    
                    if fastest_laps:
                        fastest_df = pd.DataFrame(fastest_laps)
                        fastest_df = fastest_df.sort_values('Time')
                        st.dataframe(fastest_df, use_container_width=True)
                
                # Average lap times
                with st.expander("Average Lap Times", expanded=True):
                    avg_times = []
                    for driver in selected_drivers:
                        driver_laps = session.laps.pick_driver(driver)
                        if not driver_laps.empty:
                            avg_times.append({
                                'Driver': driver,
                                'Average Time': driver_laps['LapTime'].mean(),
                                'Std Dev': driver_laps['LapTime'].std(),
                                'Laps Completed': len(driver_laps)
                            })
                    
                    if avg_times:
                        avg_df = pd.DataFrame(avg_times)
                        avg_df = avg_df.sort_values('Average Time')
                        st.dataframe(avg_df, use_container_width=True)

if __name__ == "__main__":
    main()
