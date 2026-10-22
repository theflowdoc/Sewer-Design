import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Sanitary Sewer Design",
    layout="wide"
)

st.title("Sanitary Sewer Design Sheet")

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

if uploaded_file:

    df = pd.read_csv(uploaded_file)

    # ----------------------------------
    # REQUIRED INPUT COLUMNS
    # ----------------------------------
    required = [
        "Location",
        "Pipe_ID",
        "From_MH_ID",
        "To_MH_ID",
        "Subcatchment_ID",
        "Residential_Pop_per_ha",
        "Residential_Area_ha",
        "Industrial_Commercial_Area_ha"
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        st.error(
            f"Missing columns: {missing}"
        )
        st.stop()

    # ----------------------------------
    # RESIDENTIAL CALCULATIONS
    # ----------------------------------

    df["Residential Population"] = (
        df["Residential_Pop_per_ha"]
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

    # ----------------------------------
    # INDUSTRIAL / COMMERCIAL
    # ----------------------------------

    df["Cumulative IC Area (ha)"] = (
        df["Industrial_Commercial_Area_ha"]
        .cumsum()
    )

    # ----------------------------------
    # TOTALS
    # ----------------------------------

    total_res_area = (
        df["Residential_Area_ha"]
        .sum()
    )

    total_res_population = (
        df["Residential Population"]
        .sum()
    )

    # ----------------------------------
    # OUTPUT TABLE
    # ----------------------------------

    output = df[
        [
            "Location",
            "Pipe_ID",
            "From_MH_ID",
            "To_MH_ID",
            "Subcatchment_ID",
            "Residential_Pop_per_ha",
            "Residential_Area_ha",
            "Residential Population",
            "Area Cumulative (ha)",
            "Population Cumulative",
            "Industrial_Commercial_Area_ha",
            "Cumulative IC Area (ha)"
        ]
    ]

    st.subheader("Residential / Industrial Summary")

    st.dataframe(
        output,
        use_container_width=True
    )

    # ----------------------------------
    # TOTALS
    # ----------------------------------

    col1, col2 = st.columns(2)

    col1.metric(
        "Total Residential Area (ha)",
        round(total_res_area, 2)
    )

    col2.metric(
        "Total Residential Population",
        round(total_res_population, 0)
    )

    # ----------------------------------
    # EXPORT
    # ----------------------------------

    csv = output.to_csv(
        index=False
    )

    st.download_button(
        "Download Results",
        csv,
        "Residential_Design_Sheet.csv",
        "text/csv"
    )
