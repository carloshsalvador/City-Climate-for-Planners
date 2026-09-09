import streamlit as st

from app.frontend.basel_controls import (
    default_financial_assumptions,
    format_celsius,
    format_chf,
    format_m2,
    format_m3,
    grass_percent_to_irrfrac,
    paved_albedo_for_cm3,
)
from app.runtime import (
    BaselRc5CompatibilityError,
    BaselRc5InputError,
    BaselRc5Runtime,
    BaselRc5RuntimeError,
)


st.set_page_config(page_title="Basel rc5 Scenario", page_icon="app/frontend/assets/logo.png", layout="wide")

st.markdown(
    """
    <style>
    .main-title {
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_basel_runtime() -> BaselRc5Runtime:
    return BaselRc5Runtime()


st.markdown('<h1 class="main-title">Basel rc5 Demonstrator</h1>', unsafe_allow_html=True)
st.info(
    "Cooling estimates use surrogate models calibrated for the fixed Basel rc5 scientific "
    "context. Site-specific predictions for other geometries or cities require local "
    "simulation and validation."
)

try:
    runtime = get_basel_runtime()
except BaselRc5CompatibilityError as exc:
    st.error(f"Basel rc5 runtime compatibility error: {exc}")
    st.stop()
except BaselRc5RuntimeError as exc:
    st.error(f"Basel rc5 runtime could not initialize: {exc}")
    st.stop()

defaults = default_financial_assumptions(runtime)

st.sidebar.header("Intervention")
grass_percent = st.sidebar.slider(
    "Irrigated grass fraction [%]",
    min_value=0,
    max_value=100,
    value=0,
    step=1,
    format="%d %%",
)
cm3_enabled = st.sidebar.toggle("Street whitening / CM3", value=False)

if cm3_enabled:
    selected_paved_albedo = st.sidebar.slider(
        "Target paved albedo",
        min_value=0.10,
        max_value=0.87,
        value=0.87,
        step=0.01,
    )
else:
    selected_paved_albedo = 0.10
    st.sidebar.caption("CM3 off: target paved albedo fixed at the Basel baseline value 0.10.")

st.sidebar.markdown("---")
st.sidebar.caption("Financial assumptions, not validated universal market prices.")
water_unit_cost = st.sidebar.number_input(
    "Water unit cost [CHF/m³]",
    min_value=0.0,
    value=defaults["water_unit_cost_chf_m3"],
    step=0.01,
)
whitening_unit_cost = st.sidebar.number_input(
    "Street whitening unit cost [CHF/m²]",
    min_value=0.0,
    value=defaults["whitening_unit_cost_chf_m2"],
    step=0.10,
)

grass_irrfrac = grass_percent_to_irrfrac(grass_percent)
paved_albedo = paved_albedo_for_cm3(
    cm3_enabled=cm3_enabled,
    selected_paved_albedo=selected_paved_albedo,
)

try:
    result = runtime.evaluate(
        grass_irrfrac=grass_irrfrac,
        paved_albedo=paved_albedo,
        cm3_enabled=cm3_enabled,
        water_unit_cost_chf_m3=water_unit_cost,
        whitening_unit_cost_chf_m2=whitening_unit_cost,
    )
except BaselRc5InputError as exc:
    st.error(f"Scenario input is outside the validated Basel rc5 domain: {exc}")
    st.stop()
except BaselRc5RuntimeError as exc:
    st.error(f"Basel rc5 inference failed: {exc}")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Annual cooling [°C]", format_celsius(result.planner.annual_cooling))
with col2:
    st.metric(
        "Warm-season daytime cooling [°C]",
        format_celsius(result.planner.warm_day_cooling),
    )
with col3:
    st.metric(
        "Warm-season nighttime cooling [°C]",
        format_celsius(result.planner.warm_night_cooling),
    )
with col4:
    st.metric("Total variable cost", format_chf(result.financial.total_variable_cost_chf))

st.markdown("---")

left_col, right_col = st.columns(2)
with left_col:
    st.subheader("Scenario Inputs")
    st.write(
        {
            "Irrigated grass fraction": f"{grass_percent} %",
            "Street whitening / CM3": "On" if cm3_enabled else "Off",
            "Effective target paved albedo": f"{paved_albedo:.2f}",
            "Water unit cost": f"{format_chf(water_unit_cost)}/m³",
            "Street whitening unit cost": f"{format_chf(whitening_unit_cost)}/m²",
        }
    )

with right_col:
    st.subheader("Basel rc5 Runtime")
    st.write(
        {
            "City": result.metadata.city,
            "Bundle version": result.metadata.bundle_version,
            "Training context": result.metadata.training_context_id,
            "Source run": result.metadata.source_run,
        }
    )

with st.expander("Fixed rc5 context", expanded=False):
    st.write(
        {
            "Validated demonstrator": result.metadata.city,
            "Model version": result.metadata.model_version,
            "Irrigated grass fraction range": "0-100 %",
            "Target paved albedo range": "0.10-0.87",
            "Fixed rc5 training-context site area": format_m2(runtime.site_area_m2),
            "Fixed rc5 training-context paved fraction": f"{runtime.paved_fraction:.3f}",
        }
    )
    st.caption(
        "Site area and paved fraction are fixed training-context properties, not dynamic "
        "site measurements."
    )

with st.expander("Operational details", expanded=False):
    irr_col, cm3_col = st.columns(2)
    with irr_col:
        st.markdown("#### Irrigation")
        st.metric("Irrigation demand", f"{result.operational.irrigation_mm:.3f} mm")
        st.metric("Water volume", format_m3(result.operational.water_volume_m3))
        st.metric("Irrigation cost", format_chf(result.financial.irrigation_cost_chf))
    with cm3_col:
        st.markdown("#### Street whitening")
        st.metric("Whitened paved area", format_m2(result.operational.whitening_area_m2))
        st.metric("Whitening cost", format_chf(result.financial.whitening_cost_chf))

with st.expander("Scientific outputs", expanded=False):
    st.write(
        {
            "Annual Delta T2 [°C]": result.scientific.annual_delta_t2,
            "Warm-season daytime Delta T2 [°C]": result.scientific.warm_day_delta_t2,
            "Warm-season nighttime Delta T2 [°C]": result.scientific.warm_night_delta_t2,
            "Raw irrigation [mm]": result.scientific.irrigation_raw_mm,
        }
    )

st.caption(result.metadata.applicability_statement)
