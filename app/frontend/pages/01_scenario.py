import streamlit as st
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from app.api.data_loader import load_city_baseline
from app.api.scenario import apply_intervention, estimate_delta_t
from app.api.costs import get_cost_summary


st.set_page_config(page_title="Scenario Configuration", page_icon="🌳", layout="wide")

# Re-apply some basic styling for consistency (in a real app, this would be a shared module)
st.markdown("""
    <style>
    .main-title {
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<h1 class="main-title">🌳 Urban Intervention Scenario</h1>', unsafe_allow_html=True)

st.write("Modify the land cover fractions below to simulate urban interventions.")
# 
# Load demo data (hardcoded for now, will use data_loader.py later)
# initial_fractions = {
#     "Paved": 0.45,
#     "Buildings": 0.30,
#     "Green Space": 0.20,
#     "Water": 0.05
# }
fractions_baseline = load_city_baseline("basel") # Pydantic model. Access values like baseline_data.paved, etc.
fractions_initical = fractions_baseline.fractions


st.sidebar.header("Intervention")
intervention = st.sidebar.slider("Increase in Green Space (%)", 0, 50, 10)/100

fractions_intervention = apply_intervention(fractions_initical, intervention)
delta_t = estimate_delta_t(fractions_intervention, fractions_initical)

col1, col2 = st.columns(2) # dividing the screen into 2 columns: the left one for the metric and the right one for the cost

with col1:
    st.metric("Estimated (ΔT): Cooling (-) or Heating (+)", f"{delta_t} °C", delta = delta_t, delta_color = "normal" if delta_t < 0 else "inverse")

with col2:
    cost_data = get_cost_summary(100000, intervention) # temporarlly, using fixed area of 100,000 m2 (10 hectares) for the demo
    cost_formatted = f"€ {cost_data['total_cost']:,.0f}"
    st.metric("Estimated Intervention Cost", cost_formatted, delta=f"{cost_data['area_affected_m2']:,.0f} m² modified", delta_color="off")



def get_plot_data(f):
    paved = (f.paved + f.bare_soil)*100
    buildings = f.buildings*100
    green = (f.deciduous_trees + f.evergreen_trees + f.grass)*100
    water = f.water*100
    landcover_list = [paved, buildings, green, water]
    return landcover_list



# Display comparison
st.subheader("Comparison: Baseline vs. Scenario")

data = {
    "Type": ["Paved", "Buildings", "Green Space", "Water"],
    "Baseline (%)": get_plot_data(fractions_initical),
    "Scenario (%)": get_plot_data(fractions_intervention),
}


df = pd.DataFrame(data)

st.table(df)

st.success("✨ Scenario Logic and Cost Estimation fully integrated!")
