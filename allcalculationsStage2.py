
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
        # APPLY POPULATION TABLE EDITS BEFORE RECALCULATING
        # =====================================================

        population_editable_columns = [
            "Population_per_ha",
            "Residential_Area_ha",
            "Industrial_Area_ha"
        ]
        population_editor_state = st.session_state.get("population_data_editor", {})
        population_edited_rows = (
            population_editor_state.get("edited_rows", {})
            if isinstance(population_editor_state, dict) else {}
        )
        for row_index, changes in population_edited_rows.items():
            try:
                row_index = int(row_index)
            except (TypeError, ValueError):
                continue
            if 0 <= row_index < len(df):
                for col in population_editable_columns:
                    if col in changes:
                        df.at[row_index, col] = pd.to_numeric(
                            pd.Series([changes[col]]), errors="coerce"
                        ).fillna(0).iloc[0]

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
        # HYDRAULIC CALCULATION HELPER
        # =====================================================

        def calculate_hydraulics(data, manning_n):
            data = data.copy()

            data["Slope (%)"] = np.where(
                data["Length_m"] > 0,
                ((data["Upstream_Invert_m"] - data["Downstream_Invert_m"])
                 / data["Length_m"]) * 100,
                0.0
            )
            data["Diameter_m"] = data["Pipe_Diameter_mm"] / 1000
            data["Area_m2"] = np.pi * data["Diameter_m"] ** 2 / 4
            data["Hydraulic_Radius_m"] = data["Diameter_m"] / 4
            effective_slope = data["Slope (%)"].clip(lower=0) / 100

            data["Capacity_m3s"] = (
                (1 / manning_n)
                * data["Area_m2"]
                * data["Hydraulic_Radius_m"] ** (2 / 3)
                * np.sqrt(effective_slope)
            )
            data.loc[
                (data["Diameter_m"] <= 0) | (data["Length_m"] <= 0),
                "Capacity_m3s"
            ] = 0.0

            data["Capacity (L/s)"] = data["Capacity_m3s"] * 1000
            data["Full Flow Velocity (m/s)"] = np.where(
                data["Area_m2"] > 0,
                data["Capacity_m3s"] / data["Area_m2"],
                0.0
            )
            data["Q Peak / Q Capacity (%)"] = np.where(
                data["Capacity (L/s)"] > 0,
                data["Peak Design Flow Q(t)"] / data["Capacity (L/s)"] * 100,
                np.nan
            )
            return data

        # Re-apply the latest edits before calculating hydraulics. Streamlit reruns
        # the script after each data_editor change; reading edited_rows here means
        # the calculated columns are refreshed in the editor on that same rerun.
        editable_columns = [
            "Length_m", "Pipe_Diameter_mm", "Upstream_Invert_m", "Downstream_Invert_m"
        ]
        editor_state = st.session_state.get("sewer_data_editor", {})
        edited_rows = editor_state.get("edited_rows", {}) if isinstance(editor_state, dict) else {}
        for row_index, changes in edited_rows.items():
            try:
                row_index = int(row_index)
            except (TypeError, ValueError):
                continue
            if 0 <= row_index < len(df):
                for col in editable_columns:
                    if col in changes:
                        df.at[row_index, col] = pd.to_numeric(
                            pd.Series([changes[col]]), errors="coerce"
                        ).fillna(0).iloc[0]

        # Recalculate using the current editable values before rendering tables.
        df = calculate_hydraulics(df, n)

        id_columns = [
            "Location", "Pipe_ID", "From_MH_ID", "To_MH_ID", "Subcatchment_ID"
        ]

        # =====================================================
        # POPULATION TABLE
        # =====================================================

        st.subheader("Population")
        population_columns = id_columns + [
            "Population_per_ha",
            "Residential_Area_ha",
            "Residential Population",
            "Area Cumulative (ha)",
            "Population Cumulative",
            "Industrial_Area_ha",
            "Industrial Cumulative Area (ha)",
            "Total Area (ha)"
        ]
        population_results = df[population_columns].copy()
        population_formats = {
            col: "{:.2f}"
            for col in population_results.select_dtypes(include=[np.number]).columns
        }
        population_formats["Population_per_ha"] = "{:.2f}"
        population_formats["Residential_Area_ha"] = "{:.2f}"
        population_formats["Industrial_Area_ha"] = "{:.2f}"
        styled_population_results = population_results.style.format(population_formats)
        population_disabled_columns = [
            col for col in population_columns
            if col not in population_editable_columns
        ]
        edited_population_data = st.data_editor(
            styled_population_results,
            column_config={
                "Location": st.column_config.TextColumn("Location"),
                "Pipe_ID": st.column_config.TextColumn("Pipe ID"),
                "From_MH_ID": st.column_config.TextColumn("From MH ID"),
                "To_MH_ID": st.column_config.TextColumn("To MH ID"),
                "Subcatchment_ID": st.column_config.TextColumn("Subcatchment Area ID"),
                "Population_per_ha": st.column_config.NumberColumn(
                    "Population per ha", min_value=0.0, step=10.0, format="%.2f"
                ),
                "Residential_Area_ha": st.column_config.NumberColumn(
                    "Residential Area (ha)", min_value=0.0, step=0.1, format="%.2f"
                ),
                "Residential Population": st.column_config.NumberColumn(
                    "Residential Population", format="%.2f"
                ),
                "Area Cumulative (ha)": st.column_config.NumberColumn(
                    "Area Cumulative (ha)", format="%.2f"
                ),
                "Population Cumulative": st.column_config.NumberColumn(
                    "Population Cumulative", format="%.2f"
                ),
                "Industrial_Area_ha": st.column_config.NumberColumn(
                    "Industrial Area (ha)", min_value=0.0, step=0.1, format="%.2f"
                ),
                "Industrial Cumulative Area (ha)": st.column_config.NumberColumn(
                    "Industrial Cumulative Area (ha)", format="%.2f"
                ),
                "Total Area (ha)": st.column_config.NumberColumn(
                    "Total Area (ha)", format="%.2f"
                )
            },
            disabled=population_disabled_columns,
            use_container_width=True,
            hide_index=True,
            key="population_data_editor"
        )

        # =====================================================
        # FLOWS TABLE
        # =====================================================

        st.subheader("Flows")
        flow_columns = id_columns + [
            "Peaking Factor M",
            "Peak Population Flow Q(p)",
            "Peak ICI Flow Q(p)",
            "Peak Extraneous Flow Q(i)",
            "Peak Design Flow Q(t)"
        ]
        flow_results = df[flow_columns].copy()
        flow_formats = {
            col: "{:.2f}"
            for col in flow_results.select_dtypes(include=[np.number]).columns
        }
        st.dataframe(
            flow_results.style.format(flow_formats),
            use_container_width=True,
            hide_index=True
        )

        # =====================================================
        # FORMATTING / STYLING HELPERS
        # =====================================================

        def velocity_style(value):
            if pd.isna(value):
                return ""
            if value <= 0.60 or value >= 3.00:
                return "color: red; font-weight: bold"
            if 0.60 < value <= 0.75:
                return "color: orange; font-weight: bold"
            return ""

        def capacity_ratio_style(value):
            if pd.notna(value) and value >= 80:
                return "color: red; font-weight: bold"
            return ""

        def style_results(frame):
            formats = {
                col: "{:.2f}"
                for col in frame.select_dtypes(include=[np.number]).columns
            }
            formats.update({
                "Upstream_Invert_m": "{:.3f}",
                "Downstream_Invert_m": "{:.3f}",
                "Q Peak / Q Capacity (%)": "{:.2f}%"
            })
            return (
                frame.style
                .map(velocity_style, subset=["Full Flow Velocity (m/s)"])
                .map(capacity_ratio_style, subset=["Q Peak / Q Capacity (%)"])
                .format(formats)
            )

        # =====================================================
        # SEWER DATA TABLE (EDITABLE INPUTS)
        # =====================================================

        st.subheader("Sewer Data")
        st.caption(
            "Edit Length, Pipe Size, and invert elevations. "
            "Hydraulic results and the Results table recalculate automatically."
        )

        id_columns = [
            "Location", "Pipe_ID", "From_MH_ID", "To_MH_ID", "Subcatchment_ID"
        ]
        sewer_columns = id_columns + [
            "Peak Design Flow Q(t)",
            "Length_m",
            "Pipe_Diameter_mm",
            "Upstream_Invert_m",
            "Downstream_Invert_m",
            "Pipe_Type",
            "Slope (%)",
            "Capacity (L/s)",
            "Full Flow Velocity (m/s)",
            "Q Peak / Q Capacity (%)"
        ]
        sewer_editor_df = df[sewer_columns].copy()
        disabled_columns = [col for col in sewer_columns if col not in editable_columns]

        sewer_editor_formats = {
            col: "{:.2f}"
            for col in sewer_editor_df.select_dtypes(include=[np.number]).columns
        }
        sewer_editor_formats.update({
            "Upstream_Invert_m": "{:.3f}",
            "Downstream_Invert_m": "{:.3f}",
            "Q Peak / Q Capacity (%)": "{:.2f}%"
        })
        styled_sewer_editor_df = (
            sewer_editor_df.style
            .map(velocity_style, subset=["Full Flow Velocity (m/s)"])
            .map(capacity_ratio_style, subset=["Q Peak / Q Capacity (%)"])
            .format(sewer_editor_formats)
        )

        edited_sewer_data = st.data_editor(
            styled_sewer_editor_df,
            column_config={
                "Location": st.column_config.TextColumn("Location"),
                "Pipe_ID": st.column_config.TextColumn("Pipe ID"),
                "From_MH_ID": st.column_config.TextColumn("From MH ID"),
                "To_MH_ID": st.column_config.TextColumn("To MH ID"),
                "Subcatchment_ID": st.column_config.TextColumn("Subcatchment Area ID"),
                "Peak Design Flow Q(t)": st.column_config.NumberColumn("Peak Design Flow Q(t) (L/s)", format="%.2f"),
                "Length_m": st.column_config.NumberColumn("Length (m)", min_value=0.0, step=1.0, format="%.2f"),
                "Pipe_Diameter_mm": st.column_config.NumberColumn("Pipe Size (mm)", min_value=0.0, step=25.0, format="%.2f"),
                "Upstream_Invert_m": st.column_config.NumberColumn("Upstream Invert (m)", step=0.001, format="%.3f"),
                "Downstream_Invert_m": st.column_config.NumberColumn("Downstream Invert (m)", step=0.001, format="%.3f"),
                "Pipe_Type": st.column_config.TextColumn("Type of Pipe"),
                "Slope (%)": st.column_config.NumberColumn("Slope (%)", format="%.2f"),
                "Capacity (L/s)": st.column_config.NumberColumn("Capacity (L/s), n=0.013", format="%.2f"),
                "Full Flow Velocity (m/s)": st.column_config.NumberColumn("Full Flow Velocity (m/s)", format="%.2f"),
                "Q Peak / Q Capacity (%)": st.column_config.NumberColumn("Q Peak / Q Capacity", format="%.2f%%")
            },
            disabled=disabled_columns,
            use_container_width=True,
            hide_index=True,
            key="sewer_data_editor"
        )

        # Bring the edited input fields back into the main data frame and recalculate.
        for col in editable_columns:
            df[col] = pd.to_numeric(edited_sewer_data[col], errors="coerce").fillna(0)
        df = calculate_hydraulics(df, n)

        # Preserve full precision for calculations; apply display formatting in tables.
        # =====================================================
        # RESULTS TABLE (ALL INFORMATION JOINED)
        # =====================================================

        result_columns = id_columns + [
            "Population_per_ha",
            "Residential_Area_ha",
            "Residential Population",
            "Area Cumulative (ha)",
            "Population Cumulative",
            "Industrial_Area_ha",
            "Industrial Cumulative Area (ha)",
            "Total Area (ha)",
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
            "Q Peak / Q Capacity (%)"
        ]
        results = df[result_columns].copy()
        results = results[results["Pipe_ID"].notna()].reset_index(drop=True)

        st.success(
            "Sanitary sewer design completed successfully. "
            f"{len(results)} records processed."
        )
        st.subheader("Results")
        st.dataframe(
            style_results(results),
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

        export_results = results.copy()
        for col in export_results.select_dtypes(include=[np.number]).columns:
            if col in ["Upstream_Invert_m", "Downstream_Invert_m"]:
                export_results[col] = export_results[col].map(
                    lambda value: f"{value:.3f}" if pd.notna(value) else ""
                )
            else:
                export_results[col] = export_results[col].map(
                    lambda value: f"{value:.2f}" if pd.notna(value) else ""
                )
        export_results["Q Peak / Q Capacity (%)"] = results["Q Peak / Q Capacity (%)"].map(
            lambda value: f"{value:.2f}%" if pd.notna(value) else ""
        )
        csv_data = export_results.to_csv(index=False)

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
