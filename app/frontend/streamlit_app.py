import streamlit as st
from PIL import Image


st.set_page_config(
    page_title="Basel rc5 Demonstrator",
    page_icon=Image.open("app/frontend/assets/urban_flow_pipeline_logo_v2.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }

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

    div.stMetric, div[data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.05);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    [data-testid="stMetricLabel"] {
        color: #cbd5e1 !important;
    }
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }

    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
    }

    .main-title {
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }

    .subtitle {
        color: #cbd5e1;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.image("app/frontend/assets/logo.png", width=200)
    st.markdown("---")
    st.markdown("### Demonstrator Context")
    st.text_input("Validated demonstrator", value="Basel rc5", disabled=True)
    st.markdown("---")
    st.info("Additional cities and dynamic site geometries are not yet validated.")

st.markdown('<h1 class="main-title">Basel rc5 Demonstrator</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Explore validated intervention consequences for the fixed Basel rc5 '
    'scientific context.</p>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Validated city", value="Basel")
with col2:
    st.metric(label="Bundle", value="basel_rc5_app_v1")
with col3:
    st.metric(label="Context", value="Fixed rc5")

st.markdown("---")

left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Basel rc5 Overview")
    st.write(
        """
        This emergency App v2 demonstrator uses the promoted Basel rc5 runtime bundle
        for intervention consequences relative to the fixed Basel rc5 baseline. The
        Scenario page is the validated surrogate workflow.
        """
    )
    st.image(
        "app/frontend/assets/heatmap.png",
        caption="Basel context image; not a dynamic site-selection map",
        use_container_width=True,
    )

with right_col:
    st.subheader("Planner Workflow")
    st.info("Open the Scenario page to evaluate Basel rc5 interventions.")
    st.markdown("Intervention")
    st.markdown("Climate consequence")
    st.markdown("Operational consequence")
    st.markdown("Financial consequence")
    st.caption(
        "The current surrogate is not Switzerland-wide, multi-city, or dynamically "
        "generated from selected coordinates."
    )

st.markdown("---")
st.caption("© 2026 Carlos Salvador | DHBW Bachelor Thesis Project in partnership with meteoblue AG.")
