import streamlit as st

from app.frontend.site_context_controls import (
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_RADIUS_METER,
    GEOMETRY_MODE_OPTIONS,
    build_site_context_request,
    capability_display,
    evaluated_result_state,
    format_area_km2,
    format_area_m2,
    site_context_request_identity,
)
from app.site_context import SiteContextRuntime


st.set_page_config(
    page_title="Technical Site",
    page_icon="app/frontend/assets/logo.png",
    layout="wide",
)

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
def get_site_context_runtime() -> SiteContextRuntime:
    return SiteContextRuntime()


st.markdown('<h1 class="main-title">Technical Site</h1>', unsafe_allow_html=True)
st.info(
    "Define dynamic spatial context for future city-specific SUEWS workflows. The Basel rc5 "
    "decision-support model remains fixed and is not recalibrated by these site inputs."
)

with st.form("technical_site_form"):
    left_col, right_col = st.columns(2)
    with left_col:
        latitude = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=DEFAULT_LATITUDE,
            step=0.0001,
            format="%.6f",
        )
        longitude = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=DEFAULT_LONGITUDE,
            step=0.0001,
            format="%.6f",
        )
    with right_col:
        radius_meter = st.number_input(
            "Radius [m]",
            min_value=1.0,
            value=DEFAULT_RADIUS_METER,
            step=100.0,
            format="%.0f",
        )
        mode = st.radio(
            "Geometry mode",
            options=GEOMETRY_MODE_OPTIONS,
            horizontal=True,
        )

    include_lcz_status = st.checkbox(
        "Show LCZ unavailable status",
        value=False,
        help="No public LCZ provider is configured in this milestone.",
    )
    submitted = st.form_submit_button("Evaluate site", type="primary")

if submitted:
    request = build_site_context_request(
        latitude=latitude,
        longitude=longitude,
        radius_meter=radius_meter,
        mode=mode,
        include_lcz=include_lcz_status,
    )
    st.session_state.site_context_result = get_site_context_runtime().evaluate(request)
    st.session_state.site_context_evaluated_request = site_context_request_identity(request)

state = evaluated_result_state(
    result=st.session_state.get("site_context_result"),
    evaluated_request=st.session_state.get("site_context_evaluated_request"),
)

if not state["has_evaluation"]:
    st.info(
        'Define the technical site above and select "Evaluate site" to generate its spatial '
        "context."
    )
    st.stop()

serialized = state["serialized"]
summary = state["summary"]
evaluated_request = state["evaluated_request"]

if serialized["errors"]:
    st.subheader("Last Evaluated Request")
    st.write(evaluated_request)
    for error in serialized["errors"]:
        st.error(error["message"])
else:
    st.subheader("Last Evaluated Request")
    st.write(evaluated_request)
    site_col, geometry_col, area_col = st.columns(3)
    with site_col:
        st.subheader("Site Identity")
        st.write(
            {
                "Latitude": summary["latitude"],
                "Longitude": summary["longitude"],
                "Radius": f'{summary["radius_meter"]:,.0f} m',
                "Requested mode": summary["requested_mode"],
                "Effective mode": summary["effective_mode"],
            }
        )
    with geometry_col:
        st.subheader("Geometry Status")
        geometry_capability = capability_display(serialized["capabilities"]["geometry"])
        st.metric("Geometry", geometry_capability["label"])
        st.write(
            {
                "Output CRS": summary["output_crs"],
                "Requested matches effective": summary["requested_matches_effective"],
                "Fallback used": summary["fallback_used"],
            }
        )
    with area_col:
        st.subheader("Area")
        surfacearea_m2 = float(summary["surfacearea_m2"])
        st.metric("Effective area", format_area_km2(surfacearea_m2))
        st.caption(format_area_m2(surfacearea_m2))
        st.write({"Metric CRS": summary["metric_crs"], "Unit": summary["area_unit"]})

    st.markdown("---")

    prop_col, cap_col = st.columns(2)
    with prop_col:
        st.subheader("Site Properties")
        st.write(
            {
                "lat": summary["site_properties"].get("lat"),
                "lng": summary["site_properties"].get("lng"),
                "surfacearea": format_area_m2(
                    float(summary["site_properties"].get("surfacearea", 0.0))
                ),
            }
        )
        st.caption("Only request and geometry-derived public properties are currently available.")

    with cap_col:
        st.subheader("Capabilities")
        for name, capability in serialized["capabilities"].items():
            display = capability_display(capability)
            st.write(
                {
                    "Capability": name,
                    "Status": display["label"],
                    "Message": display["message"],
                }
            )

if serialized["warnings"]:
    st.warning("\n".join(serialized["warnings"]))

st.caption(
    "Administrative boundaries, LCZ, SUEWS fractions, maps, and YAML generation are future "
    "technical workflow milestones."
)

with st.expander("Technical details", expanded=False):
    st.write(
        {
            "contract_version": serialized["metadata"]["contract_version"],
            "runtime_adapter": serialized["metadata"]["adapter"],
            "requested_mode": summary["requested_mode"],
            "effective_mode": summary["effective_mode"],
            "fallback_used": summary["fallback_used"],
            "crs": summary["output_crs"],
            "metric_crs_for_area": summary["metric_crs"],
            "capabilities": serialized["capabilities"],
            "provenance": serialized["provenance"],
            "warnings": serialized["warnings"],
        }
    )
    st.json(serialized)
