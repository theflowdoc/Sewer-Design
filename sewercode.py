import streamlit as st
import pandas as pd
import math

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Sanitary Sewer Design Tool",
    layout="wide"
)

# ============================================================================
# FUNCTIONS
# ============================================================================

def harmon_factor(population):

    P = max(population / 1000, 0.001)

    M = 1 + (14 / (4 + math.sqrt(P)))

    M = max(2, min(4, M))

    return M


def calculate_slope(us, ds, length):

    if length <= 0:
        return 0.00001

    slope = (us - ds) / length

    return max(slope, 0.00001)


def manning_capacity(diameter_mm, slope, n):

    if slope <= 0:
        return 0

    D = diameter_mm / 1000

    area = math.pi * D**2 / 4

    hydraulic_radius = D / 4

    Q = (
        (1 / n)
        * area
        * (hydraulic_radius ** (2 / 3))
        * math.sqrt(slope)
    )

    return Q * 1000


def velocity(diameter_mm, capacity_ls):

    D = diameter_mm / 1000

    area = math.pi * D**2 / 4

    if area == 0:
        return 0

    return (capacity_ls / 1000) / area


def recommend_pipe(flow, slope, n):

    sizes = [
        200,
        250,
        300,
        375,
        450,
        525,
        600,
        750,
        900
    ]

    for size in sizes:

        cap = manning_capacity(
            size,
            slope,
            n
        )

        if cap >= flow:
            return size

    return "Larger Required"


# ============================================================================
# TITLE
# ============================================================================

st.title("Sanitary Sewer Design Tool")

st.markdown("""
Upload either:

• GIS Export CSV

or

• Sewer Design CSV
""")

# ============================================================================
# PARAMETERS
# ============================================================================

st.sidebar.header("Design Parameters")

per_capita_flow = st.sidebar.number_input(
    "Per Capita Flow (L/cap/day)",
    value=350.0
)

extraneous_rate = st.sidebar.number_input(
    "Extraneous Flow (L/s/ha)",
    value=0.28
)

default_density = st.sidebar.number_input(
    "Population Density (people/ha)",
    value=124.0
)

manning_n = st.sidebar.number_input(
    "Manning n",
    value=0.013,
    format="%.3f"
)

# ============================================================================
# FILE UPLOAD
# ============================================================================

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

# ============================================================================
# PROCESS FILE
# ============================================================================

if uploaded_file:

    try:

        df = pd.read_csv(uploaded_file)

        st.subheader("Raw Columns Found")

        st.write(df.columns.tolist())

        # ---------------------------------------------------
        # CLEAN COLUMN NAMES
        # ---------------------------------------------------

        df.columns = (
            df.columns
            .str.strip()
            .str.replace(" ", "_", regex=False)
            .str.replace(".", "_", regex=False)
        )

        # ---------------------------------------------------
        # GIS COLUMN CONVERSION
        # ---------------------------------------------------

        rename_map = {

            "FROMMH": "FromMH",
            "TOMH": "ToMH",

            "DIAMETER": "Diameter_mm",

            "UPELEV": "UpstreamInvert",
            "DOWNELEV": "DownstreamInvert",

            "SHAPE_LEN": "Length_m",

            "AREA_ha": "Area_ha",
            "AREA_HA": "Area_ha",
            "Area_ha": "Area_ha"
        }

        df.rename(
            columns=rename_map,
            inplace=True
        )

        # ---------------------------------------------------
        # CREATE OPTIONAL FIELDS
        # ---------------------------------------------------

        if "Street" not in df.columns:
            df["Street"] = "Unknown"

        if "PopDensity" not in df.columns:
            df["PopDensity"] = default_density

        # ---------------------------------------------------
        # REQUIRED FIELDS
        # ---------------------------------------------------

        required = [
            "FromMH",
            "ToMH",
            "Area_ha",
            "Length_m",
            "Diameter_mm",
            "UpstreamInvert",
            "DownstreamInvert"
        ]

        missing = []

        for col in required:

            if col not in df.columns:
                missing.append(col)

        if len(missing) > 0:

            st.error(
                f"Missing Columns: {missing}"
            )

            st.write("Columns Available:")

            st.write(df.columns.tolist())

            st.stop()

        st.success("CSV Loaded Successfully")

        cumulative_pop = 0
        cumulative_area = 0

        results = []

        # ---------------------------------------------------
        # CALCULATIONS
        # ---------------------------------------------------

        for _, row in df.iterrows():

            area = float(row.get("Area_ha", 0))

            density = float(
                row.get(
                    "PopDensity",
                    default_density
                )
            )

            population = area * density

            cumulative_pop += population

            cumulative_area += area

            peaking = harmon_factor(
                cumulative_pop
            )

            q_peak = (
                cumulative_pop
                * per_capita_flow
                * peaking
                / 86400
            )

            q_extraneous = (
                cumulative_area
                * extraneous_rate
            )

            q_design = (
                q_peak
                + q_extraneous
            )

            slope = calculate_slope(

                float(
                    row["UpstreamInvert"]
                ),

                float(
                    row["
