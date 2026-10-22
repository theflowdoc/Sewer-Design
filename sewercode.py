import streamlit as st
import pandas as pd
import math

st.set_page_config(
    page_title="Sanitary Sewer Design",
    layout="wide"
)

##############################################################################
# FUNCTIONS
##############################################################################

def harmon_factor(pop):

    P = max(pop / 1000, 0.001)

    M = 1 + 14 / (4 + math.sqrt(P))

    M = max(2, min(4, M))

    return M


def calculate_slope(
        us_invert,
        ds_invert,
        length):

    if length <= 0:
        return 0.00001

    slope = (
        us_invert -
        ds_invert
    ) / length

    return max(slope, 0.00001)


def manning_capacity(
        diameter_mm,
        slope,
        n):

    D = diameter_mm / 1000

    area = math.pi * D**2 / 4

    hydraulic_radius = D / 4

    q = (
        (1 / n)
        * area
        * (hydraulic_radius ** (2/3))
        * math.sqrt(slope)
    )

    return q * 1000


def velocity(
        diameter_mm,
        capacity_ls):

    D = diameter_mm / 1000

    area = math.pi * D**2 / 4

    return (capacity_ls / 1000) / area


def recommend_pipe(
        design_flow,
        slope,
        n):

    pipe_sizes = [
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

    for pipe in pipe_sizes:

        cap = manning_capacity(
            pipe,
            slope,
            n
        )

        if cap >= design_flow:

            return pipe

    return "Oversized"


##############################################################################
# TITLE
##############################################################################

st.title(
    "Sanitary Sewer Design Tool"
)

##############################################################################
# SIDEBAR
##############################################################################

st.sidebar.header(
    "Design Parameters"
)

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

##############################################################################
# UPLOAD
##############################################################################

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

##############################################################################
# SAMPLE FORMAT
##############################################################################

with st.expander("CSV Format Example"):

    sample = pd.DataFrame({

        "Street":["Example Road"],

        "FromMH":["MH-1"],

        "ToMH":["MH-2"],

        "Area_ha":[0.66],

        "Length_m":[70],

        "Diameter_mm":[200],

        "UpstreamInvert":[103.556],

        "DownstreamInvert":[103.297],

        "PopDensity":[124]

    })

    st.dataframe(sample)

##############################################################################
# PROCESS FILE
##############################################################################

if uploaded_file:

    df = pd.read_csv(uploaded_file)

    cumulative_pop = 0
    cumulative_area = 0

    results = []

    for index, row in df.iterrows():

        density = row.get(
            "PopDensity",
            default_density
        )

        area = row["Area_ha"]

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

        q_infiltration = (
            cumulative_area
            * extraneous_rate
        )

        q_design = (
            q_peak
            + q_infiltration
        )

        slope = calculate_slope(
            row["UpstreamInvert"],
            row["DownstreamInvert"],
            row["Length_m"]
        )

        capacity = manning_capacity(
            row["Diameter_mm"],
            slope,
            manning_n
        )

        vel = velocity(
            row["Diameter_mm"],
            capacity
        )

        utilization = 0

        if capacity > 0:

            utilization = (
                q_design
                / capacity
            )

        recommended = recommend_pipe(
            q_design,
            slope,
            manning_n
        )

        if utilization < 0.50:

            status = "GOOD"

        elif utilization < 0.80:

            status = "CHECK"

        else:

            status = "UPSIZE"

        results.append({

            "Street":
                row["Street"],

            "From":
                row["FromMH"],

            "To":
                row["ToMH"],

            "Area (ha)":
                round(area,2),

            "Population":
                round(cumulative_pop),

            "Peaking":
                round(peaking,2),

            "Q Peak (L/s)":
                round(q_peak,2),

            "Q Extraneous":
                round(q_infiltration,2),

            "Q Design":
                round(q_design,2),

            "Slope %":
                round(slope*100,3),

            "Diameter":
                row["Diameter_mm"],

            "Capacity":
                round(capacity,2),

            "Velocity":
                round(vel,2),

            "Utilization":
                round(utilization,2),

            "Recommended Pipe":
                recommended,

            "Status":
                status
        })

    results_df = pd.DataFrame(results)

    ##########################################################################

    st.subheader("Results")

    st.dataframe(
        results_df,
        use_container_width=True
    )

    ##########################################################################

    st.subheader("Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Population",
        int(results_df["Population"].max())
    )

    col2.metric(
        "Max Design Flow",
        round(
            results_df["Q Design"].max(),
            2
        )
    )

    col3.metric(
        "Average Utilization",
        round(
            results_df["Utilization"].mean(),
            2
        )
    )

    col4.metric(
        "Max Capacity",
        round(
            results_df["Capacity"].max(),
            2
        )
    )

    ##########################################################################

    st.subheader("Capacity Chart")

    chart = results_df.set_index(
        "From"
    )[["Capacity","Q Design"]]

    st.bar_chart(chart)

    ##########################################################################

    csv = results_df.to_csv(
        index=False
    )

    st.download_button(
        "Download Results CSV",
        csv,
        "Sewer_Design_Results.csv",
        "text/csv"
    )
