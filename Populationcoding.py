import streamlit as st
import pandas as pd

# ==================================================
# PAGE SETUP
# ==================================================

st.set_page_config(
    page_title="Population Coding",
    layout="wide"
)

st.title("Population Coding Tool")

# ==================================================
# FILE UPLOAD
# ==================================================

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

# ==================================================
# PROCESS FILE
# ==================================================

if uploaded_file is not None:

    try:

        # Read CSV
        df = pd.read_csv(uploaded_file)

        # Show original columns
        st.subheader("Columns Found")
        st.write(df.columns.tolist())

        # Clean column names
        df.columns = (
            df.columns
            .str.strip()
        )

        # ------------------------------------------------
        # AUTOMATIC COLUMN MAPPING
        # ------------------------------------------------

        rename_map = {}

        for col in df.columns:

            c = col.lower().strip()

            if c == "street":
                rename_map[col] = "Location"

            elif c == "pipe id":
                rename_map[col] = "Pipe_ID"

            elif c == "from":
                rename_map[col] = "From_MH_ID"

            elif c == "to":
                rename_map[col] = "To_MH_ID"

            elif "subc" in c:
                rename_map[col] = "Subcatchment_ID"

            elif c == "pop":
                rename_map[col] = "Population_per_ha"

            elif c == "area":
                rename_map[col] = "Residential_Area_ha"

            elif "industrial" in c:
                rename_map[col] = "Industrial_Area_ha"

        df.rename(
            columns=rename_map,
            inplace=True
        )

        # ------------------------------------------------
        # OPTIONAL INDUSTRIAL COLUMN
        # ------------------------------------------------

        if "Industrial_Area_ha" not in df.columns:
            df["Industrial_Area_ha"] = 0

        # ------------------------------------------------
        # REQUIRED COLUMNS
        # ------------------------------------------------

        required = [
            "Location",
            "Pipe_ID",
            "From_MH_ID",
            "To_MH_ID",
            "Subcatchment_ID",
            "Population_per_ha",
            "Residential_Area_ha"
        ]

        missing = [
            c for c in required
            if c not in df.columns
        ]

        if missing:

            st.error(
                f"Missing columns: {missing}"
            )

            st.write(
                "Mapped Columns:"
            )

            st.write(
                df.columns.tolist()
            )

            st.stop()

        # ------------------------------------------------
        # CALCULATIONS
        # ------------------------------------------------

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

        # ------------------------------------------------
        # OUTPUT TABLE
        # ------------------------------------------------

        results = df[
            [
                "Location",
                "Pipe_ID",
                "From_MH_ID",
                "To_MH_ID",
                "
