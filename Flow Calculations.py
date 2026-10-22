import streamlit as st
import pandas as pd
import numpy as np

# =====================================================
# PAGE SETUP
# =====================================================

st.set_page_config(
    page_title="Sanitary Sewer Design",
    layout="wide"
)

st.title("Sanitary Sewer Design Tool")

# =====================================================
# DESIGN PARAMETERS
# =====================================================

st.sidebar.header("Design Parameters")

q = st.sidebar.number_input(
    "Average Daily Per Capita Flow (L/cap/day)",
    value=350.0
)

i = st.sidebar.number_input(
    "Extraneous Flow Rate (L/ha/s)",
    value=0.28
)

ici_rate = st.sidebar.number_input(
    "Industrial Sewage (m³/ha/day)",
    value=35.0
)

commercial_rate = st.sidebar.number_input(
    "Commercial Domestic Sewage (L/d-m²)",
    value=5.0
)

ici_peak = st.sidebar.number_input(
    "ICI Peaking Factor",
    value=2.0
)

# =====================================================
# FILE UPLOAD
# =====================================================

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

# =====================================================
# HARMON PEAKING FACTOR
# =====================================================

def harmon_factor(population):

    P = population / 1000

    M = 1 + (14 / (4 + np.sqrt(P)))

    M = np.minimum(M, 4)
    M = np.maximum(M, 2)

    return M

# =====================================================
# PROCESS FILE
# =====================================================

if uploaded_file is not None:

    try:

        df = pd.read_csv(uploaded_file)

        df.columns = df.columns.str.strip()

        rename_map = {}

        for col in df.columns:

            c = col.lower().strip()

            if c in ["street", "location"]:
                rename_map[col] = "Location"

            elif c in ["pipe id", "pipe_id"]:
                rename_map[col] = "Pipe_ID"

            elif c == "from":
                rename_map[col] = "From_MH_ID"

            elif c == "to":
                rename_map[col] = "To_MH_ID"

            elif "subc" in c:
                rename_map[col] = "Subcatchment_ID"

            elif c in ["pop", "population per ha"]:
                rename_map[col] = "Population_per_ha"

            elif c in ["area", "area (ha)"]:
                rename_map[col] = "Residential_Area_ha"

            elif "industrial" in c:
                rename_map[col] = "Industrial_Area_ha"

        df.rename(columns=rename_map, inplace=True)

        if "Industrial_Area_ha" not in df.columns:
            df["Industrial_Area_ha"] = 0.0

        numeric_cols = [
            "Population_per_ha",
            "Residential_Area_ha",
            "Industrial_Area_ha"
        ]

        for col in numeric_cols:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).fillna(0)

        # =====================================================
        # POPULATION CALCULATIONS
        # =====================================================

        df["Residential Population"] = (
            df["Population_per_ha"]
            * df["Residential_Area_ha"]
        )

        df["Area Cumulative (ha)"] = (
            df["Residential_Area_ha"]
            .cumsum()
        )

        df["Population Cumulative"] = (
            df["Residential Population"]
            .cumsum()
        )

        df["Industrial Cumulative Area (ha)"] = (
            df["Industrial_Area_ha"]
            .cumsum()
        )

        # =====================================================
        # FLOW CALCULATIONS
        # =====================================================

        df["Peaking Factor M"] = harmon_factor(
            df["Population Cumulative"]
        )

        df["Peak Population Flow Q(p)"] = (
            df["Population Cumulative"]
            * q
            * df["Peaking Factor M"]
            / 86400
        )

        df["Peak ICI Flow Q(p)"] = (
            df["Industrial Cumulative Area (ha)"]
            * ici_rate
            * 1000
            / 86400
            * ici_peak
        )

        df["Total Area (ha)"] = (
            df["Area Cumulative (ha)"]
            +
            df["Industrial Cumulative Area (ha)"]
        )

        df["Peak Extraneous Flow Q(i)"] = (
            df["Total Area (ha)"]
            * i
        )

        df["Peak Design Flow Q(t)"] = (
            df["Peak Population Flow Q(p)"]
            +
            df["Peak ICI Flow Q(p)"]
            +
            df["Peak Extraneous Flow Q(i)"]
        )

        # =====================================================
        # ROUND RESULTS
        # =====================================================

        flow_cols = [
            "Peaking Factor M",
            "Peak Population Flow Q(p)",
            "Peak ICI Flow Q(p)",
            "Peak Extraneous Flow Q(i)",
            "Peak Design Flow Q(t)"
        ]

        df[flow_cols] = df[flow_cols].round(2)

        # =====================================================
        # RESULTS TABLE
        # =====================================================

        results = df[
            [
                "Location",
                "Pipe_ID",
                "From_MH_ID",
                "To_MH_ID",
                "Subcatchment_ID",
                "Population_per_ha",
                "Residential_Area_ha",
                "Residential Population",
                "Area Cumulative (ha)",
                "Population Cumulative",
                "Industrial_Area_ha",
                "Industrial Cumulative Area (ha)",
                "Peaking Factor M",
                "Peak Population Flow Q(p)",
                "Peak ICI Flow Q(p)",
                "Peak Extraneous Flow Q(i)",
                "Peak Design Flow Q(t)"
            ]
        ]

        st.success(
            "Sanitary sewer design completed successfully."
        )

        st.dataframe(
            results,
            use_container_width=True
        )

        st.subheader("Project Totals")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Population",
            int(df["Residential Population"].sum())
        )

        col2.metric(
            "Residential Area (ha)",
            round(
                df["Residential_Area_ha"].sum(),
                2
            )
        )

        col3.metric(
            "Industrial Area (ha)",
            round(
                df["Industrial_Area_ha"].sum(),
                2
            )
        )

        csv_data = results.to_csv(
            index=False
        )

        st.download_button(
            label="Download Sewer Design CSV",
            data=csv_data,
            file_name="sanitary_sewer_design.csv",
            mime="text/csv"
        )

    except Exception as e:

        st.error(
            f"Error: {str(e)}"
        )

else:

    st.info(
        "Upload a CSV file to begin."
    )
