import streamlit as st
from PIL import Image
import os

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="City Climate for Planners",
    #page_icon="🏙️",
    page_icon=Image.open("app/frontend/assets/urban_flow_pipeline_logo_v2.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CUSTOM CSS FOR PREMIUM LOOK ---
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
    
    /* Sidebar styling & text contrast */
    [data-testid="stSidebar"] {
        background-color: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
        color: #f8fafc;
    }
    [data-testid="stSidebarNav"] span {
        color: #f1f5f9 !important;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {
        color: #cbd5e1 !important;
    }
    
    /* Glassmorphism containers */
    div.stMetric, div[data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.05);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Metric text contrast */
    [data-testid="stMetricLabel"] {
        color: #cbd5e1 !important;
    }
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
    
    /* Titles and Headers */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    .main-title {
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        color: #cbd5e1; /* Increased contrast from #94a3b8 */
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    
    /* Custom button style */
    .stButton>button {
        background: linear-gradient(90deg, #0ea5e9, #6366f1);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
        opacity: 0.9;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.image("app/frontend/assets/logo.png", width=200)
    st.markdown("---")
    st.markdown("### 🛠️ Configuration")
    location = st.selectbox("Select City", ["Basel", "Zurich", "Berlin"], index=0)
    st.markdown("---")
    st.info("This is a prototype for climate-aware urban planning.")

# --- MAIN CONTENT ---
st.markdown('<h1 class="main-title">City Climate for Planners</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Simulate urban interventions and visualize thermal impact in real-time.</p>', unsafe_allow_html=True)

# Layout: 3 Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Baseline Temp (Annual)", value="11.5 °C", delta="Normal")
with col2:
    st.metric(label="Hot Days (>30°C)", value="18 days", delta="High Risk", delta_color="inverse")
with col3:
    st.metric(label="Heat Risk Class", value="High", delta=None)

st.markdown("---")

# Main Area
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("🏙️ City Overview: " + location)
    st.write("""
        This dashboard allows urban planners to explore the impact of land cover changes on the local microclimate. 
        Use the **Scenarios** page to modify land fractions (e.g., increasing vegetation or reducing paved surfaces) 
        and see the estimated temperature changes.
    """)
    
    # Placeholder for a map or a main chart
    st.image("app/frontend/assets/heatmap.png", 
             caption="Urban Heat Map - Basel (Prototype)", use_container_width=True)

with right_col:
    st.subheader("📊 Scenario Summary")
    st.info("Navigate to the **Scenario** page in the sidebar to start modifying the city's land use.")
    
    st.markdown("#### Key Indicators")
    st.progress(45, text="Paved Area: 45%")
    st.progress(30, text="Buildings: 30%")
    st.progress(25, text="Green/Blue Space: 25%")

# Footer
st.markdown("---")
st.caption("© 2026 Carlos Salvador | DHBW Bachelor Thesis Project in partnership with meteoblue AG.")
