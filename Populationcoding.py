import streamlit as st
import pandas as pd

# =====================================================
# PAGE SETUP
# =====================================================

st.set_page_config(
    page_title="Population Coding",
    layout="wide"
)

st.title("Population Coding Tool")

# =====================================================
# FILE UPLOAD
# =====================================================

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

# =====================================================
# PROCESS FILE
# =====================================================

if uploaded_file is not None:

    try:

        # Read CSV
        df = pd.read_csv(uploaded_file)

        # Clean column names
        df.columns = (
            df.columns
            .str.strip()
        )

        # -------------------------------------------------
        # AUTO MAP COLUMNS
        # -------------------------------------------------

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

        df.rename(
            columns=rename_map,
            inplace=True
        )

        # -------------------------------------------------
        # CREATE INDUSTRIAL COLUMN IF MISSING
        # -------------------------------------------------

        if "Industrial_Area_ha" not in df.columns:
            df["Industrial_Area_ha"] = 0.0

        # -------------------------------------------------
        # CHECK REQUIRED COLUMNS
        # -------------------------------------------------

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
            col
            for col in required_columns
            if col not in df.columns
        ]

        if missing:

            st.error(
                f"Missing columns: {missing}"
            )

            st.write("Columns found:")
            st.write(df.columns.tolist())

            st.stop()

        # -------------------------------------------------
        # CONVERT TO NUMERIC
        # -------------------------------------------------

        df["Population_per_ha"] = pd.to_numeric(
            df["Population_per_ha"],
            errors="coerce"
        ).fillna(0)

        df["Residential_Area_ha"] = pd.to_numeric(
            df["Residential_Area_ha"],
            errors="coerce"
        ).fillna(0)

        df["Industrial_Area_ha"] = pd.to_numeric(
            df["Industrial_Area_ha"],
            errors="coerce"
        ).fillna(0)

        # -------------------------------------------------
        # CALCULATIONS
        # -------------------------------------------------

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

        # -------------------------------------------------
        # RESULTS TABLE
        # -------------------------------------------------

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
                "Industrial Cumulative Area (ha)"
            ]
        ]

        st.success(
            "Population coding completed successfully."
        )

        st.dataframe(
            results,
            use_container_width=True
        )

        # -------------------------------------------------
        # TOTALS
        # -------------------------------------------------

        total_area = round(
            df["Residential_Area_ha"].sum(),
            2
        )

        total_population = round(
            df["Residential Population"].sum(),
            0
        )

        col1, col2 = st.columns(2)

        col1.metric(
            "Total Residential Area (ha)",
            total_area
        )

        col2.metric(
            "Total Residential Population",
            int(total_population)
        )

        # -------------------------------------------------
        # DOWNLOAD
        # -------------------------------------------------

        csv_data = results.to_csv(
            index=False
        )

        st.download_button(
            label="Download Results CSV",
            data=csv_data,
            file_name="population_results.csv",
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
