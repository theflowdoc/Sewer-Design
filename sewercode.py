import streamlit as st
import pandas as pd
import math

# ==========================================================
# PAGE SETUP
# ==========================================================

st.set_page_config(
    page_title="Sanitary Sewer Design",
    layout="wide"
)

st.title("Sanitary Sewer Design Tool")

# ==========================================================
# FUNCTIONS
# ==========================================================

def harmon_factor(population):

    p = max(population / 1000, 0.001)

    m = 1 + (14 / (4 + math.sqrt(p)))

    return max(2, min(4, m))


def sewer_slope(upstream, downstream, length):

    if length <= 0:
        return 0.00001

    slope = (upstream - downstream) / length

    return max(slope, 0.00001)


def manning_capacity(diameter_mm, slope, n):

    diameter_m = diameter_mm / 1000

    area = math.pi * diameter_m**2 / 4

    radius = diameter_m / 4

    q = (
        (1 / n)
        * area
        * (radius ** (2 / 3))
        * math.sqrt(slope)
    )

    return q * 1000


def velocity(capacity_ls, diameter_mm):

    diameter_m = diameter_mm / 1000

    area = math.pi * diameter_m**2 / 4

    if area == 0:
        return 0

    return (capacity_ls / 1000) / area


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.header("Design Parameters")

per_capita_flow = st.sidebar.number_input(
    "Per Capita Flow (L/cap/day)",
    value=350.0
)

extraneous_rate = st.sidebar.number_input(
    "Extraneous Flow (L/s/ha)",
    value=0.28
)

population_density = st.sidebar.number_input(
    "Population Density (people/ha)",
    value=124.0
)

manning_n = st.sidebar.number_input(
    "Manning n",
    value=0.013,
    format="%.3f"
)

# ==========================================================
# FILE UPLOAD
# ==========================================================

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

# ==========================================================
# PROCESS FILE
# ==========================================================

if uploaded_file is not None:

    try:

        df = pd.read_csv(uploaded_file)

        # ------------------------------------------
        # CLEAN COLUMN NAMES
        # ------------------------------------------

        df.columns = (
            df.columns
            .str.strip()
            .str.replace(" ", "_", regex=False)
            .str.replace(".", "_", regex=False)
        )

        # ------------------------------------------
        # GIS EXPORT COLUMN MAPPING
        # ------------------------------------------

        rename_map = {

            "FROMMH": "FromMH",
            "TOMH": "ToMH",

            "DIAMETER": "Diameter_mm",

            "UPELEV": "UpstreamInvert",
            "DOWNELEV": "DownstreamInvert",

            "SHAPE_LEN": "Length_m",

            "AREA_HA": "Area_ha",
            "AREA_ha": "Area_ha"
        }

        df.rename(
            columns=rename_map,
            inplace=True
        )

        # ------------------------------------------
        # OPTIONAL FIELDS
        # ------------------------------------------

        if "Street" not in df.columns:
            df["Street"] = "Unknown"

        if "PopDensity" not in df.columns:
            df["PopDensity"] = population_density

        # ------------------------------------------
        # REQUIRED FIELDS
        # ------------------------------------------

        required_columns = [

            "FromMH",
            "ToMH",
            "Area_ha",
            "Length_m",
            "Diameter_mm",
            "UpstreamInvert",
            "DownstreamInvert"
        ]

        missing = []

        for column in required_columns:

            if column not in df.columns:
                missing.append(column)

        if len(missing) > 0:

            st.error(
                f"Missing columns: {missing}"
            )

            st.write("Columns found:")

            st.write(
                list(df.columns)
            )

            st.stop()

        # ------------------------------------------
        # CALCULATIONS
        # ------------------------------------------

        cumulative_population = 0

        cumulative_area = 0

        results = []

        for _, row in df.iterrows():

            area = float(row["Area_ha"])

            density = float(
                row["PopDensity"]
            )

            population = (
                area * density
            )

            cumulative_population += population

            cumulative_area += area

            peaking = harmon_factor(
                cumulative_population
            )

            q_peak = (
                cumulative_population
                * per_capita_flow
                * peaking
                / 86400
            )

            q_infiltration = (
                cumulative_area
                * extraneous_rate
            )

            q_design = (
                q_peak +
                q_infiltration
            )

            slope = sewer_slope(
                float(row["UpstreamInvert"]),
                float(row["DownstreamInvert"]),
                float(row["Length_m"])
            )

            capacity = manning_capacity(
                float(row["Diameter_mm"]),
                slope,
                manning_n
            )

            vel = velocity(
                capacity,
                float(row["Diameter_mm"])
            )

            utilization = 0

            if capacity > 0:

                utilization = (
                    q_design / capacity
                )

            results.append({

                "Street":
                    row["Street"],

                "FromMH":
                    row["FromMH"],

                "ToMH":
                    row["ToMH"],

                "Population":
                    round(
                        cumulative_population,
                        0
                    ),

                "Peaking":
                    round(
                        peaking,
                        2
                    ),

                "Q Peak (L/s)":
                    round(
                        q_peak,
                        2
                    ),

                "Q Infiltration":
                    round(
                        q_infiltration,
                        2
                    ),

                "Q Design":
                    round(
                        q_design,
                        2
                    ),

                "Slope %":
                    round(
                        slope * 100,
                        3
                    ),

                "Diameter":
                    row["Diameter_mm"],

                "Capacity":
                    round(
                        capacity,
                        2
                    ),

                "Velocity":
                    round(
                        vel,
                        2
                    ),

                "Utilization":
                    round(
                        utilization,
                        2
                    )
            })

        results_df = pd.DataFrame(
            results
        )

        # ------------------------------------------
        # RESULTS
        # ------------------------------------------

        st.success(
            "Design completed successfully"
        )

        st.dataframe(
            results_df,
            use_container_width=True
        )

        # ------------------------------------------
        # SUMMARY
        # ------------------------------------------

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Population",
            int(
                results_df["Population"].max()
            )
        )

        col2.metric(
            "Max Design Flow",
            round(
                results_df["Q Design"].max(),
                2
            )
        )

        col3.metric(
            "Max Capacity",
            round(
                results_df["Capacity"].max(),
                2
            )
        )

        # ------------------------------------------
        # CHART
        # ------------------------------------------

        chart_data = results_df.set_index(
            "FromMH"
        )[
            [
                "Capacity",
                "Q Design"
            ]
        ]

        st.bar_chart(
            chart_data
        )

        # ------------------------------------------
        # EXPORT
        # ------------------------------------------

        csv = results_df.to_csv(
            index=False
        )

        st.download_button(
            label="Download Results CSV",
            data=csv,
            file_name="sewer_results.csv",
            mime="text/csv"
        )

    except Exception as e:

        st.error(
            f"Error: {e}"
        )

        st.exception(e)
