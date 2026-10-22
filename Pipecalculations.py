
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

commercial_domestic_sewage = st.sidebar.number_input(
    "Commercial Domestic Sewage (L/d-m²)",
    value=5.0
)

ici_peak = st.sidebar.number_input(
    "Commercial / ICI Peaking Factor",
    value=2.0
)

n = st.sidebar.number_input(
    "Manning n",
    value=0.013,
    min_value=0.001,
    format="%.3f"
)

# =====================================================
# FILE UPLOAD
# =====================================================

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

# =====================================================
# HARMON FACTOR
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

        # =====================================================
        # CLEAN COLUMN NAMES
        # =====================================================

        df.columns = df.columns.str.strip()

        # =====================================================
        # AUTO COLUMN MAPPING
        # =====================================================

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

            elif "length" in c:
                rename_map[col] = "Length_m"

            elif "diameter" in c:
                rename_map[col] = "Pipe_Diameter_mm"

            elif "upstream invert" in c:
                rename_map[col] = "Upstream_Invert_m"

            elif "downstream invert" in c:
                rename_map[col] = "Downstream_Invert_m"

            elif "type of pipe" in c:
                rename_map[col] = "Pipe_Type"

        df.rename(columns=rename_map, inplace=True)

        # =====================================================
        # CLEAN EMPTY RECORDS
        # =====================================================

        df = df.replace(r"^\s*$", np.nan, regex=True)

        df = df.replace(
            ["None", "none", "NULL", "null", "nan"],
            np.nan
        )

        text_cols = [
            "Location",
            "Pipe_ID",
            "From_MH_ID",
            "To_MH_ID",
            "Subcatchment_ID"
        ]

        for col in text_cols:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype("string")
                    .str.strip()
                )

                df[col] = df[col].replace(
                    ["", "None", "none", "nan", "NULL", "null"],
                    np.nan
                )

        existing_cols = [
            col for col in text_cols
            if col in df.columns
        ]

        if existing_cols:
            df = df.dropna(
                subset=existing_cols,
                how="all"
            )

        if "Pipe_ID" in df.columns:
            df = df[df["Pipe_ID"].notna()]

        df = df.reset_index(drop=True)

        # =====================================================
        # OPTIONAL COLUMNS
        # =====================================================

        optional_defaults = {
            "Industrial_Area_ha": 0.0,
            "Length_m": 0.0,
            "Pipe_Diameter_mm": 0.0,
            "Upstream_Invert_m": 0.0,
            "Downstream_Invert_m": 0.0,
            "Pipe_Type": ""
        }

        for col, default in optional_defaults.items():
            if col not in df.columns:
                df[col] = default

        # =====================================================
        # REQUIRED COLUMNS
        # =====================================================

        required_columns = [
            "Location",
            "Pipe_ID",
            "From_MH_ID",
            "To_MH_ID",
            "Subcatchment_ID",
            "Population_per_ha",
            "Residential_Area_ha"
        ]

        missing = [
            col for col in required_columns
            if col not in df.columns
        ]

        if missing:
            st.error(f"Missing columns: {missing}")
            st.write("Columns found:")
            st.write(df.columns.tolist())
            st.stop()

        # =====================================================
        # NUMERIC CONVERSION
        # =====================================================

        numeric_cols = [
            "Population_per_ha",
            "Residential_Area_ha",
            "Industrial_Area_ha",
            "Length_m",
            "Pipe_Diameter_mm",
            "Upstream_Invert_m",
            "Downstream_Invert_m"
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
            df["Residential_Area_ha"].cumsum()
        )

        df["Population Cumulative"] = (
            df["Residential Population"].cumsum()
        )

        df["Industrial Cumulative Area (ha)"] = (
            df["Industrial_Area_ha"].cumsum()
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
            ici_peak
            * commercial_domestic_sewage
            * df["Industrial Cumulative Area (ha)"]
            * 10000
            / 86400
        )

        df["Total Area (ha)"] = (
            df["Area Cumulative (ha)"]
            + df["Industrial Cumulative Area (ha)"]
        )

        df["Peak Extraneous Flow Q(i)"] = (
            df["Total Area (ha)"] * i
        )

        df["Peak Design Flow Q(t)"] = (
            df["Peak Population Flow Q(p)"]
            + df["Peak ICI Flow Q(p)"]
            + df["Peak Extraneous Flow Q(i)"]
        )

        # =====================================================
        # EDIT SEWER DATA
        # =====================================================

        st.subheader("Edit Sewer Data")

        st.caption(
            "Edit pipe length, diameter, and invert elevations. "
            "Hydraulic results will update automatically."
        )

        editable_columns = [
            "Length_m",
            "Pipe_Diameter_mm",
            "Upstream_Invert_m",
            "Downstream_Invert_m"
        ]

        disabled_columns = [
            col for col in df.columns
            if col not in editable_columns
        ]

        df = st.data_editor(
            df,
            column_config={
                "Length_m": st.column_config.NumberColumn(
                    "Length (m)",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f"
                ),
                "Pipe_Diameter_mm": st.column_config.NumberColumn(
                    "Pipe Diameter (mm)",
                    min_value=0.0,
                    step=25.0,
                    format="%.0f"
                ),
                "Upstream_Invert_m": st.column_config.NumberColumn(
                    "Upstream Invert (m)",
                    step=0.01,
                    format="%.3f"
                ),
                "Downstream_Invert_m": st.column_config.NumberColumn(
                    "Downstream Invert (m)",
                    step=0.01,
                    format="%.3f"
                )
            },
            disabled=disabled_columns,
            use_container_width=True,
            hide_index=True,
            key="sewer_data_editor"
        )

        # =====================================================
        # SEWER HYDRAULICS
        # Recalculated using the edited pipe data
        # =====================================================

        # Pipe slope (%)
        df["Slope (%)"] = np.where(
            df["Length_m"] > 0,
            (
                (
                    df["Upstream_Invert_m"]
                    - df["Downstream_Invert_m"]
                )
                / df["Length_m"]
            ) * 100,
            0.0
        )

        # Pipe diameter (m)
        df["Diameter_m"] = (
            df["Pipe_Diameter_mm"] / 1000
        )

        # Full pipe cross-sectional area (m²)
        df["Area_m2"] = (
            np.pi
            * df["Diameter_m"] ** 2
            / 4
        )

        # Hydraulic radius for a full circular pipe (m)
        df["Hydraulic_Radius_m"] = (
            df["Diameter_m"] / 4
        )

        # Use zero effective slope for zero or negative slopes
        effective_slope = (
            df["Slope (%)"].clip(lower=0) / 100
        )

        # Manning full-flow capacity (m³/s)
        df["Capacity_m3s"] = (
            (1 / n)
            * df["Area_m2"]
            * df["Hydraulic_Radius_m"] ** (2 / 3)
            * np.sqrt(effective_slope)
        )

        # Prevent capacity for invalid pipe diameters
        df.loc[
            (df["Diameter_m"] <= 0)
            | (df["Length_m"] <= 0),
            "Capacity_m3s"
        ] = 0.0

        # Capacity (L/s)
        df["Capacity (L/s)"] = (
            df["Capacity_m3s"] * 1000
        )

        # Full-flow velocity (m/s)
        df["Full Flow Velocity (m/s)"] = np.where(
            df["Area_m2"] > 0,
            df["Capacity_m3s"] / df["Area_m2"],
            0.0
        )

        # Peak design flow / pipe capacity
        df["Q Peak / Q Capacity"] = np.where(
            df["Capacity (L/s)"] > 0,
            (
                df["Peak Design Flow Q(t)"]
                / df["Capacity (L/s)"]
            ),
            np.nan
        )

        # =====================================================
        # ROUND RESULTS FOR DISPLAY
        # =====================================================

        flow_cols = [
            "Peaking Factor M",
            "Peak Population Flow Q(p)",
            "Peak ICI Flow Q(p)",
            "Peak Extraneous Flow Q(i)",
            "Peak Design Flow Q(t)",
            "Length_m",
            "Pipe_Diameter_mm",
            "Upstream_Invert_m",
            "Downstream_Invert_m",
            "Slope (%)",
            "Capacity (L/s)",
            "Full Flow Velocity (m/s)",
            "Q Peak / Q Capacity"
        ]

        df[flow_cols] = df[flow_cols].round(2)

        # =====================================================
        # HYDRAULIC RESULTS
        # =====================================================

        st.subheader("Sewer Hydraulic Results")

        hydraulic_columns = [
            "Location",
            "Pipe_ID",
            "From_MH_ID",
            "To_MH_ID",
            "Length_m",
            "Pipe_Diameter_mm",
            "Upstream_Invert_m",
            "Downstream_Invert_m",
            "Slope (%)",
            "Peak Design Flow Q(t)",
            "Capacity (L/s)",
            "Full Flow Velocity (m/s)",
            "Q Peak / Q Capacity"
        ]

        st.dataframe(
            df[hydraulic_columns],
            use_container_width=True,
            hide_index=True
        )

        # =====================================================
        # COMPLETE RESULTS
        # =====================================================

        result_columns = [
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
            "Peak Design Flow Q(t)",
            "Length_m",
            "Pipe_Diameter_mm",
            "Upstream_Invert_m",
            "Downstream_Invert_m",
            "Pipe_Type",
            "Slope (%)",
            "Capacity (L/s)",
            "Full Flow Velocity (m/s)",
            "Q Peak / Q Capacity"
        ]

        results = df[result_columns].copy()

        results = results[
            results["Pipe_ID"].notna()
        ].reset_index(drop=True)

        st.success(
            "Sanitary sewer design completed successfully. "
            f"{len(results)} records processed."
        )

        st.subheader("Complete Design Results")

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )

        # =====================================================
        # PROJECT TOTALS
        # =====================================================

        st.subheader("Project Totals")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Population",
            int(df["Residential Population"].sum())
        )

        col2.metric(
            "Residential Area (ha)",
            round(df["Residential_Area_ha"].sum(), 2)
        )

        col3.metric(
            "Industrial Area (ha)",
            round(df["Industrial_Area_ha"].sum(), 2)
        )

        # =====================================================
        # DOWNLOAD RESULTS
        # =====================================================

        csv_data = results.to_csv(index=False)

        st.download_button(
            label="Download Sewer Design CSV",
            data=csv_data,
            file_name="sanitary_sewer_design.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.exception(e)

else:
    st.info("Upload a CSV file to begin.")
