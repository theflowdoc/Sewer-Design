import streamlit as st
import pandas as pd
import numpy as np
import hashlib


# =====================================================
# PAGE SETUP
# =====================================================

st.set_page_config(
    page_title="Sanitary Sewer Design",
    layout="wide"
)

st.title("Sanitary Sewer Design Tool")


# =====================================================
# APPLICATION OVERVIEW AND DESIGN REFERENCE
# =====================================================

st.markdown("""
### About this application

This tool supports **preliminary sanitary sewer network calculations**.
It reads pipe, manhole, population, area, and pipe geometry data from a
CSV file, then calculates cumulative upstream contributions, estimated
sewage flows, and hydraulic performance for each pipe.

**Main capabilities**

- Download a standardized CSV input template.
- Display a directed network diagram of manholes and pipes.
- Automatically arrange all tables in upstream-to-downstream network order.
- Accumulate population, residential area, and industrial/commercial area
  through connected upstream branches.
- Calculate peak population, ICI, extraneous, and total design flows.
- Calculate pipe slope, Manning-based full-flow capacity, velocity,
  and peak-flow-to-capacity ratio.
- Edit population, area, pipe length, diameter, and invert elevations.
- Display Population, Flows, Sewer Data, Results, and Project Totals.
- Download the calculated results as a CSV file.

**Design reference:** The app's workflow and selected calculation methods
are informed by the Ontario Ministry of the Environment's
[Design Guidelines for Sewage Works](https://www.ontario.ca/document/design-guidelines-sewage-works-0).

**Important:** This application is a calculation aid. It does not implement
every requirement in the guidelines or independently certify design
compliance. Confirm applicable current provincial and municipal criteria,
project-specific conditions, assumptions, and results through appropriate
engineering review.
""")


# =====================================================
# CSV INPUT TEMPLATE
# =====================================================

st.info(
    "**Start here:** Download the CSV template, enter your initial sewer "
    "and population information, save it as a CSV file, and upload it below. "
    "Keep the column headers exactly as provided."
)

template_columns = [
    "Location",
    "Pipe ID",
    "From",
    "To",
    "Subcatchment Area ID",
    "Population per ha",
    "Residential Area (ha)",
    "Industrial Area (ha)",
    "Length (m)",
    "Pipe Diameter (mm)",
    "Upstream Invert (m)",
    "Downstream Invert (m)",
    "Type of Pipe",
]

template_df = pd.DataFrame(
    [{column: "" for column in template_columns} for _ in range(5)],
    columns=template_columns,
)

st.download_button(
    label="Download CSV Input Template",
    data=template_df.to_csv(index=False),
    file_name="sanitary_sewer_input_template.csv",
    mime="text/csv",
)

st.caption(
    "Required fields: Location, Pipe ID, From, To, Subcatchment Area ID, "
    "Population per ha, and Residential Area (ha). Missing optional "
    "numeric values default to zero."
)


# =====================================================
# DESIGN PARAMETERS
# =====================================================

st.sidebar.header("Design Parameters")

q = st.sidebar.number_input(
    "Average Daily Per Capita Flow (L/cap/day)",
    value=350.0,
    min_value=0.0,
)

i = st.sidebar.number_input(
    "Extraneous Flow Rate (L/ha/s)",
    value=0.28,
    min_value=0.0,
)

commercial_domestic_sewage = st.sidebar.number_input(
    "Commercial Domestic Sewage (L/d-m²)",
    value=5.0,
    min_value=0.0,
)

ici_peak = st.sidebar.number_input(
    "Commercial / ICI Peaking Factor",
    value=2.0,
    min_value=0.0,
)

n = st.sidebar.number_input(
    "Manning n",
    value=0.013,
    min_value=0.001,
    format="%.3f",
)


# =====================================================
# FILE UPLOAD
# =====================================================

uploaded_file = st.file_uploader(
    "Upload your completed CSV template to begin calculations",
    type=["csv"],
)


# =====================================================
# HARMON FACTOR
# =====================================================

def harmon_factor(population):
    P = population / 1000

    M = 1 + (14 / (4 + np.sqrt(P)))

    return np.clip(M, 2, 4)


# =====================================================
# NETWORK ORDERING
# =====================================================

def order_pipes_by_network(data):
    """
    Sort pipe records in upstream-to-downstream order.

    A pipe is processed after every pipe discharging into
    its From manhole has been processed.

    The algorithm:
      1. Identifies upstream/downstream pipe relationships.
      2. Performs a topological sort.
      3. Preserves original row order for available branches.
      4. Detects directed cycles.

    Missing connections are retained in the dataset.
    """

    data = data.copy()

    if data.empty:
        return data

    def clean_node(value):
        if pd.isna(value):
            return None

        value = str(value).strip()

        return value if value else None

    from_nodes = [
        clean_node(value)
        for value in data["From_MH_ID"]
    ]

    to_nodes = [
        clean_node(value)
        for value in data["To_MH_ID"]
    ]

    row_count = len(data)

    # Map each manhole to pipes discharging into it.
    incoming_pipes = {}

    for pipe_index, to_node in enumerate(to_nodes):

        if to_node is not None:

            incoming_pipes.setdefault(
                to_node, []
            ).append(pipe_index)

    # Identify the upstream pipes for each pipe.
    downstream_children = [
        [] for _ in range(row_count)
    ]

    pending_parent_count = [
        0 for _ in range(row_count)
    ]

    for child_index, from_node in enumerate(from_nodes):

        upstream_indices = (
            incoming_pipes.get(from_node, [])
            if from_node is not None
            else []
        )

        # Exclude the pipe itself.
        upstream_indices = [
            idx for idx in upstream_indices
            if idx != child_index
        ]

        pending_parent_count[child_index] = len(
            upstream_indices
        )

        for parent_index in upstream_indices:

            downstream_children[parent_index].append(
                child_index
            )

    # Start with pipes that have no upstream pipes.
    queue = [
        idx
        for idx, count in enumerate(pending_parent_count)
        if count == 0
    ]

    queue.sort()

    ordered_indices = []

    queue_position = 0

    while queue_position < len(queue):

        parent_index = queue[queue_position]

        queue_position += 1

        ordered_indices.append(parent_index)

        for child_index in downstream_children[parent_index]:

            pending_parent_count[child_index] -= 1

            if pending_parent_count[child_index] == 0:

                queue.append(child_index)

    # Detect directed cycles.
    if len(ordered_indices) != row_count:

        cycle_indices = [
            idx
            for idx, count in enumerate(pending_parent_count)
            if count > 0
        ]

        cycle_pipe_ids = (
            data.iloc[cycle_indices]["Pipe_ID"]
            .astype(str)
            .tolist()
        )

        raise ValueError(
            "A loop/cycle was detected in the pipe network. "
            "Check the From and To manhole IDs for these pipes: "
            f"{', '.join(cycle_pipe_ids)}."
        )

    return (
        data.iloc[ordered_indices]
        .copy()
        .reset_index(drop=True)
    )


# =====================================================
# NETWORK CUMULATIVE CALCULATIONS
# =====================================================

def calculate_network_cumulative(data):
    """
    Accumulate population, total area, and ICI area
    through the directed From -> To pipe network.

    The function is independent of CSV row order.
    """

    data = data.copy()

    row_count = len(data)

    def clean_node(value):
        if pd.isna(value):
            return None

        value = str(value).strip()

        return value if value else None

    from_nodes = [
        clean_node(value)
        for value in data["From_MH_ID"]
    ]

    to_nodes = [
        clean_node(value)
        for value in data["To_MH_ID"]
    ]

    incoming_pipes = {}

    for pipe_index, to_node in enumerate(to_nodes):

        if to_node is not None:

            incoming_pipes.setdefault(
                to_node, []
            ).append(pipe_index)

    downstream_children = [
        [] for _ in range(row_count)
    ]

    pending_parent_count = [
        0 for _ in range(row_count)
    ]

    for child_index, from_node in enumerate(from_nodes):

        upstream_indices = (
            incoming_pipes.get(from_node, [])
            if from_node is not None
            else []
        )

        upstream_indices = [
            idx for idx in upstream_indices
            if idx != child_index
        ]

        pending_parent_count[child_index] = len(
            upstream_indices
        )

        for parent_index in upstream_indices:

            downstream_children[parent_index].append(
                child_index
            )

    cumulative_population = (
        data["Residential Population"].astype(int).tolist()
    )

    local_total_area = (
        data["Residential_Area_ha"]
        + data["Industrial_Area_ha"]
    )

    cumulative_total_area = local_total_area.astype(float).tolist()

    cumulative_ici_area = (
        data["Industrial_Area_ha"].astype(float).tolist()
    )

    queue = [
        idx
        for idx, count in enumerate(pending_parent_count)
        if count == 0
    ]

    queue.sort()

    queue_position = 0
    processed_count = 0

    while queue_position < len(queue):

        parent_index = queue[queue_position]

        queue_position += 1
        processed_count += 1

        for child_index in downstream_children[parent_index]:

            cumulative_population[child_index] += (
                cumulative_population[parent_index]
            )

            cumulative_total_area[child_index] += (
                cumulative_total_area[parent_index]
            )

            cumulative_ici_area[child_index] += (
                cumulative_ici_area[parent_index]
            )

            pending_parent_count[child_index] -= 1

            if pending_parent_count[child_index] == 0:

                queue.append(child_index)

    if processed_count != row_count:

        cycle_indices = [
            idx
            for idx, count in enumerate(pending_parent_count)
            if count > 0
        ]

        cycle_pipe_ids = (
            data.iloc[cycle_indices]["Pipe_ID"]
            .astype(str)
            .tolist()
        )

        raise ValueError(
            "A loop/cycle was detected in the pipe network. "
            "Check the From and To manhole IDs for these pipes: "
            f"{', '.join(cycle_pipe_ids)}."
        )

    data["Population Cumulative"] = cumulative_population

    data["Total Area (ha)"] = cumulative_total_area

    data["Industrial / Commercial Cumulative Area (ha)"] = (
        cumulative_ici_area
    )

    return data


# =====================================================
# HYDRAULIC CALCULATIONS
# =====================================================

def calculate_hydraulics(data, manning_n):

    data = data.copy()

    data["Slope (%)"] = np.where(
        data["Length_m"] > 0,
        (
            (
                data["Upstream_Invert_m"]
                - data["Downstream_Invert_m"]
            )
            / data["Length_m"]
        ) * 100,
        0.0,
    )

    data["Diameter_m"] = data["Pipe_Diameter_mm"] / 1000

    data["Area_m2"] = (
        np.pi * data["Diameter_m"] ** 2 / 4
    )

    data["Hydraulic_Radius_m"] = (
        data["Diameter_m"] / 4
    )

    effective_slope = (
        data["Slope (%)"].clip(lower=0) / 100
    )

    data["Capacity_m3s"] = (
        (1 / manning_n)
        * data["Area_m2"]
        * data["Hydraulic_Radius_m"] ** (2 / 3)
        * np.sqrt(effective_slope)
    )

    data.loc[
        (data["Diameter_m"] <= 0)
        | (data["Length_m"] <= 0),
        "Capacity_m3s",
    ] = 0.0

    data["Capacity (L/s)"] = (
        data["Capacity_m3s"] * 1000
    )

    data["Full Flow Velocity (m/s)"] = np.where(
        data["Area_m2"] > 0,
        data["Capacity_m3s"] / data["Area_m2"],
        0.0,
    )

    data["Q Peak / Q Capacity (%)"] = np.where(
        data["Capacity (L/s)"] > 0,
        (
            data["Peak Design Flow Q(t)"]
            / data["Capacity (L/s)"]
        ) * 100,
        np.nan,
    )

    return data


# =====================================================
# STYLING HELPERS
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
        for col in frame.select_dtypes(
            include=[np.number]
        ).columns
    }

    formats.update({
        "Upstream_Invert_m": "{:.3f}",
        "Downstream_Invert_m": "{:.3f}",
        "Q Peak / Q Capacity (%)": "{:.2f}%",
    })

    for col in [
        "Residential Population",
        "Population Cumulative",
    ]:

        if col in frame.columns:
            formats[col] = "{:.0f}"

    styled = frame.style

    if "Full Flow Velocity (m/s)" in frame.columns:

        styled = styled.map(
            velocity_style,
            subset=["Full Flow Velocity (m/s)"],
        )

    if "Q Peak / Q Capacity (%)" in frame.columns:

        styled = styled.map(
            capacity_ratio_style,
            subset=["Q Peak / Q Capacity (%)"],
        )

    return styled.format(formats)


# =====================================================
# EDITOR CALLBACK
# =====================================================

def save_editor_changes(editor_key, columns):
    """
    Merge editor changes into the persistent dataframe.

    All editor row positions refer to the network-sorted
    dataframe established before session state initialization.
    """

    editor_state = st.session_state.get(editor_key, {})

    edited_rows = (
        editor_state.get("edited_rows", {})
        if isinstance(editor_state, dict)
        else {}
    )

    working = st.session_state.get("design_inputs_df")

    if working is None:
        return

    working = working.copy(deep=True)

    for row_index, changes in edited_rows.items():

        try:
            row_index = int(row_index)
        except (TypeError, ValueError):
            continue

        if 0 <= row_index < len(working):

            for col in columns:

                if col in changes:

                    value = pd.to_numeric(
                        pd.Series([changes[col]]),
                        errors="coerce",
                    ).iloc[0]

                    working.at[row_index, col] = (
                        0.0 if pd.isna(value) else value
                    )

    st.session_state["design_inputs_df"] = working

    # Reset editor widget state while preserving current inputs.
    st.session_state["editor_generation"] = (
        st.session_state.get("editor_generation", 0) + 1
    )


# =====================================================
# PROCESS FILE
# =====================================================

if uploaded_file is not None:

    try:

        # =====================================================
        # READ CSV
        # =====================================================

        df = pd.read_csv(uploaded_file)

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

            elif (
                c in [
                    "pop",
                    "population per ha",
                    "population/ha",
                    "population per hectare",
                    "pop/ha",
                ]
                or (
                    ("pop" in c or "population" in c)
                    and (
                        "/ha" in c
                        or "per ha" in c
                        or "hectare" in c
                    )
                )
            ):
                rename_map[col] = "Population_per_ha"

            elif "industrial" in c:
                rename_map[col] = "Industrial_Area_ha"

            elif (
                c in [
                    "area",
                    "area (ha)",
                    "residential area",
                    "residential area (ha)",
                ]
                or (
                    "residential" in c
                    and "area" in c
                )
            ):
                rename_map[col] = "Residential_Area_ha"

            elif "length" in c:
                rename_map[col] = "Length_m"

            elif (
                "diameter" in c
                or c in ["pipe size", "pipe size (mm)"]
            ):
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
            np.nan,
        )

        text_cols = [
            "Location",
            "Pipe_ID",
            "From_MH_ID",
            "To_MH_ID",
            "Subcatchment_ID",
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
                    np.nan,
                )

        existing_cols = [
            col for col in text_cols
            if col in df.columns
        ]

        if existing_cols:

            df = df.dropna(
                subset=existing_cols,
                how="all",
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
            "Pipe_Type": "",
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
            "Residential_Area_ha",
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
            "Downstream_Invert_m",
        ]

        for col in numeric_cols:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            ).fillna(0)

        # =====================================================
        # NETWORK-BASED TABLE ORDERING
        # =====================================================

        # IMPORTANT:
        # Sort the input dataframe before storing it in
        # session state or creating any editable tables.
        #
        # All tables and editor row positions will therefore
        # follow the same upstream-to-downstream order.

        df = order_pipes_by_network(df)

        # =====================================================
        # PERSIST INPUTS
        # =====================================================

        population_editable_columns = [
            "Population_per_ha",
            "Residential_Area_ha",
            "Industrial_Area_ha",
        ]

        editable_columns = [
            "Length_m",
            "Pipe_Diameter_mm",
            "Upstream_Invert_m",
            "Downstream_Invert_m",
        ]

        upload_signature = hashlib.sha256(
            uploaded_file.getvalue()
        ).hexdigest()

        if (
            st.session_state.get("upload_signature")
            != upload_signature
        ):

            st.session_state["upload_signature"] = (
                upload_signature
            )

            # Store the network-sorted dataframe.
            st.session_state["design_inputs_df"] = (
                df.copy(deep=True)
            )

            st.session_state["editor_generation"] = (
                st.session_state.get("editor_generation", 0) + 1
            )

        elif "design_inputs_df" not in st.session_state:

            st.session_state["design_inputs_df"] = (
                df.copy(deep=True)
            )

            st.session_state["editor_generation"] = (
                st.session_state.get("editor_generation", 0) + 1
            )

        # Use persistent values instead of rereading the original CSV.
        df = st.session_state["design_inputs_df"].copy(deep=True)

        # =====================================================
        # POPULATION AND AREA CALCULATIONS
        # =====================================================

        df["Population_per_ha"] = (
            pd.to_numeric(
                df["Population_per_ha"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        df["Residential_Area_ha"] = (
            pd.to_numeric(
                df["Residential_Area_ha"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        df["Industrial_Area_ha"] = (
            pd.to_numeric(
                df["Industrial_Area_ha"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        # Round residential population to the nearest person.
        df["Residential Population"] = np.floor(
            df["Population_per_ha"]
            * df["Residential_Area_ha"]
            + 0.5
        ).astype(int)

        df = calculate_network_cumulative(df)

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

        # ICI flow based on cumulative ICI area.
        df["Peak ICI Flow Q(p)"] = (
            df["Industrial / Commercial Cumulative Area (ha)"]
            * commercial_domestic_sewage
            * 10000
            * ici_peak
            / 24
            / 3600
        )

        # Extraneous flow:
        # (Local residential area + cumulative ICI area) * rate.
        df["Peak Extraneous Flow Q(i)"] = (
            df["Residential_Area_ha"]
            + df["Industrial / Commercial Cumulative Area (ha)"]
        ) * i

        df["Peak Design Flow Q(t)"] = (
            df["Peak Population Flow Q(p)"]
            + df["Peak ICI Flow Q(p)"]
            + df["Peak Extraneous Flow Q(i)"]
        )

        # =====================================================
        # HYDRAULIC CALCULATIONS
        # =====================================================

        df = calculate_hydraulics(df, n)

        id_columns = [
            "Location",
            "Pipe_ID",
            "From_MH_ID",
            "To_MH_ID",
            "Subcatchment_ID",
        ]

        # =====================================================
        # MANHOLE / PIPE NETWORK DIAGRAM
        # =====================================================

        st.subheader("Manhole and Pipe Network Diagram")

        st.caption(
            "Each oval represents a manhole. Arrows show pipe direction "
            "from the From manhole to the To manhole. Each arrow displays "
            "the Pipe ID and Location. Shared manhole IDs are drawn as "
            "one node, so connected branches meet at the same location."
        )

        def diagram_text(value, default=""):

            if pd.isna(value):
                return default

            text_value = str(value).strip()

            return text_value if text_value else default

        def dot_quote(value):

            return (
                str(value)
                .replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\r", "")
                .replace("\n", "\\n")
            )

        from_values = [
            diagram_text(value)
            for value in df["From_MH_ID"]
        ]

        to_values = [
            diagram_text(value)
            for value in df["To_MH_ID"]
        ]

        pipe_values = [
            diagram_text(value, "(Pipe ID missing)")
            for value in df["Pipe_ID"]
        ]

        location_values = [
            diagram_text(value, "(Location missing)")
            for value in df["Location"]
        ]

        manhole_labels = []
        manhole_node_ids = {}

        valid_edge_rows = []
        missing_connection_rows = []

        for row_index, (
            from_mh,
            to_mh,
            pipe_id,
            location,
        ) in enumerate(
            zip(
                from_values,
                to_values,
                pipe_values,
                location_values,
            )
        ):

            if not from_mh or not to_mh:

                missing_connection_rows.append({
                    "Pipe ID": pipe_id,
                    "From MH ID": from_mh or "(missing)",
                    "To MH ID": to_mh or "(missing)",
                })

                continue

            for manhole_id in (from_mh, to_mh):

                if manhole_id not in manhole_node_ids:

                    generated_id = (
                        f"mh_{len(manhole_node_ids)}"
                    )

                    manhole_node_ids[manhole_id] = generated_id

                    manhole_labels.append(
                        (generated_id, manhole_id)
                    )

            valid_edge_rows.append((
                manhole_node_ids[from_mh],
                manhole_node_ids[to_mh],
                pipe_id,
                location,
                row_index,
            ))

        if not valid_edge_rows:

            st.warning(
                "The network diagram cannot be drawn because no rows "
                "have both a From manhole ID and a To manhole ID."
            )

        else:

            dot_lines = [
                "digraph SewerNetwork {",
                '  graph [rankdir=LR, overlap=false, splines=true, '
                'nodesep="0.45", ranksep="0.85", pad="0.25", '
                'bgcolor="transparent"];',
                '  node [shape=ellipse, style="filled", '
                'fillcolor="#E8F2EB", color="#397456", '
                'penwidth="1.2", fontname="Arial", fontsize="10", '
                'margin="0.12,0.08"];',
                '  edge [color="#627D8B", fontname="Arial", '
                'fontsize="9", fontcolor="#263746", '
                'arrowsize="0.75", penwidth="1.2"];',
            ]

            for generated_id, manhole_id in manhole_labels:

                dot_lines.append(
                    f'  {generated_id} '
                    f'[label="{dot_quote("MH\\n" + manhole_id)}"];'
                )

            for (
                from_node,
                to_node,
                pipe_id,
                location,
                row_index,
            ) in valid_edge_rows:

                pipe_label = (
                    f"Pipe ID: {pipe_id}"
                    if pipe_id != "(Pipe ID missing)"
                    else f"Pipe row {row_index + 1}"
                )

                edge_label = (
                    f"{pipe_label}\nLocation: {location}"
                )

                dot_lines.append(
                    f'  {from_node} -> {to_node} '
                    f'[label="{dot_quote(edge_label)}"];'
                )

            dot_lines.append("}")

            dot_source = "\n".join(dot_lines)

            st.caption(
                f"Diagram contains {len(manhole_node_ids)} unique "
                f"manholes and {len(valid_edge_rows)} pipes "
                "with complete From/To connections."
            )

            st.graphviz_chart(
                dot_source,
                use_container_width=True,
            )

            if missing_connection_rows:

                st.warning(
                    f"{len(missing_connection_rows)} pipe row(s) are "
                    "not shown because a From or To manhole ID is missing."
                )

                with st.expander(
                    "Review pipes with missing manhole connections"
                ):

                    st.dataframe(
                        pd.DataFrame(missing_connection_rows),
                        use_container_width=True,
                        hide_index=True,
                    )

        # =====================================================
        # POPULATION TABLE
        # =====================================================

        st.subheader("Population")

        st.caption(
            "Edit population density, residential area, and industrial "
            "area. Cumulative population and area are recalculated "
            "through the connected upstream network."
        )

        population_columns = id_columns + [
            "Population_per_ha",
            "Residential_Area_ha",
            "Residential Population",
            "Industrial_Area_ha",
            "Industrial / Commercial Cumulative Area (ha)",
            "Population Cumulative",
            "Total Area (ha)",
        ]

        population_results = df[population_columns].copy()

        population_formats = {
            col: "{:.2f}"
            for col in population_results.select_dtypes(
                include=[np.number]
            ).columns
        }

        for col in [
            "Residential Population",
            "Population Cumulative",
        ]:

            population_formats[col] = "{:.0f}"

        styled_population_results = (
            population_results.style.format(population_formats)
        )

        population_disabled_columns = [
            col for col in population_columns
            if col not in population_editable_columns
        ]

        editor_generation = st.session_state.get(
            "editor_generation", 0
        )

        population_editor_key = (
            f"population_data_editor_{editor_generation}"
        )

        st.data_editor(
            styled_population_results,
            column_config={
                "Location": st.column_config.TextColumn("Location"),
                "Pipe_ID": st.column_config.TextColumn("Pipe ID"),
                "From_MH_ID": st.column_config.TextColumn("From MH ID"),
                "To_MH_ID": st.column_config.TextColumn("To MH ID"),
                "Subcatchment_ID": st.column_config.TextColumn(
                    "Subcatchment Area ID"
                ),
                "Population_per_ha": st.column_config.NumberColumn(
                    "Population per ha",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                ),
                "Residential_Area_ha": st.column_config.NumberColumn(
                    "Residential Area (ha)",
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                ),
                "Residential Population": st.column_config.NumberColumn(
                    "Residential Population",
                    format="%.0f",
                ),
                "Industrial_Area_ha": st.column_config.NumberColumn(
                    "Industrial Area (ha)",
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                ),
                "Industrial / Commercial Cumulative Area (ha)":
                    st.column_config.NumberColumn(
                        "Industrial / Commercial Cumulative Area (ha)",
                        format="%.2f",
                    ),
                "Population Cumulative": st.column_config.NumberColumn(
                    "Population Cumulative",
                    format="%.0f",
                ),
                "Total Area (ha)": st.column_config.NumberColumn(
                    "Total Area (ha)",
                    format="%.2f",
                ),
            },
            disabled=population_disabled_columns,
            use_container_width=True,
            hide_index=True,
            key=population_editor_key,
            on_change=save_editor_changes,
            args=(
                population_editor_key,
                population_editable_columns,
            ),
        )

        # =====================================================
        # FLOWS TABLE
        # =====================================================

        st.subheader("Flows")

        flow_columns = id_columns + [
            "Industrial / Commercial Cumulative Area (ha)",
            "Peaking Factor M",
            "Peak Population Flow Q(p)",
            "Peak ICI Flow Q(p)",
            "Peak Extraneous Flow Q(i)",
            "Peak Design Flow Q(t)",
        ]

        flow_results = df[flow_columns].copy()

        flow_formats = {
            col: "{:.2f}"
            for col in flow_results.select_dtypes(
                include=[np.number]
            ).columns
        }

        st.dataframe(
            flow_results.style.format(flow_formats),
            use_container_width=True,
            hide_index=True,
        )

        # =====================================================
        # SEWER DATA TABLE
        # =====================================================

        st.subheader("Sewer Data")

        st.caption(
            "Edit Length, Pipe Size, and invert elevations. "
            "Hydraulic results and the Results table recalculate "
            "automatically. Pipes follow the same network order "
            "as the Population and Flows tables."
        )

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
            "Q Peak / Q Capacity (%)",
        ]

        sewer_editor_df = df[sewer_columns].copy()

        disabled_columns = [
            col for col in sewer_columns
            if col not in editable_columns
        ]

        sewer_editor_formats = {
            col: "{:.2f}"
            for col in sewer_editor_df.select_dtypes(
                include=[np.number]
            ).columns
        }

        sewer_editor_formats.update({
            "Upstream_Invert_m": "{:.3f}",
            "Downstream_Invert_m": "{:.3f}",
            "Q Peak / Q Capacity (%)": "{:.2f}%",
        })

        styled_sewer_editor_df = (
            sewer_editor_df.style
            .map(
                velocity_style,
                subset=["Full Flow Velocity (m/s)"],
            )
            .map(
                capacity_ratio_style,
                subset=["Q Peak / Q Capacity (%)"],
            )
            .format(sewer_editor_formats)
        )

        editor_generation = st.session_state.get(
            "editor_generation", 0
        )

        sewer_editor_key = (
            f"sewer_data_editor_{editor_generation}"
        )

        st.data_editor(
            styled_sewer_editor_df,
            column_config={
                "Location": st.column_config.TextColumn("Location"),
                "Pipe_ID": st.column_config.TextColumn("Pipe ID"),
                "From_MH_ID": st.column_config.TextColumn("From MH ID"),
                "To_MH_ID": st.column_config.TextColumn("To MH ID"),
                "Subcatchment_ID": st.column_config.TextColumn(
                    "Subcatchment Area ID"
                ),
                "Peak Design Flow Q(t)": st.column_config.NumberColumn(
                    "Peak Design Flow Q(t) (L/s)",
                    format="%.2f",
                ),
                "Length_m": st.column_config.NumberColumn(
                    "Length (m)",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                ),
                "Pipe_Diameter_mm": st.column_config.NumberColumn(
                    "Pipe Size (mm)",
                    min_value=0.0,
                    step=25.0,
                    format="%.2f",
                ),
                "Upstream_Invert_m": st.column_config.NumberColumn(
                    "Upstream Invert (m)",
                    step=0.001,
                    format="%.3f",
                ),
                "Downstream_Invert_m": st.column_config.NumberColumn(
                    "Downstream Invert (m)",
                    step=0.001,
                    format="%.3f",
                ),
                "Pipe_Type": st.column_config.TextColumn(
                    "Type of Pipe"
                ),
                "Slope (%)": st.column_config.NumberColumn(
                    "Slope (%)",
                    format="%.2f",
                ),
                "Capacity (L/s)": st.column_config.NumberColumn(
                    "Capacity (L/s)",
                    format="%.2f",
                ),
                "Full Flow Velocity (m/s)":
                    st.column_config.NumberColumn(
                        "Full Flow Velocity (m/s)",
                        format="%.2f",
                    ),
                "Q Peak / Q Capacity (%)":
                    st.column_config.NumberColumn(
                        "Q Peak / Q Capacity",
                        format="%.2f%%",
                    ),
            },
            disabled=disabled_columns,
            use_container_width=True,
            hide_index=True,
            key=sewer_editor_key,
            on_change=save_editor_changes,
            args=(
                sewer_editor_key,
                editable_columns,
            ),
        )

        # =====================================================
        # RESULTS TABLE
        # =====================================================

        result_columns = id_columns + [
            "Population_per_ha",
            "Residential_Area_ha",
            "Residential Population",
            "Industrial_Area_ha",
            "Industrial / Commercial Cumulative Area (ha)",
            "Population Cumulative",
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
            "Q Peak / Q Capacity (%)",
        ]

        results = df[result_columns].copy()

        results = (
            results[results["Pipe_ID"].notna()]
            .reset_index(drop=True)
        )

        st.success(
            "Sanitary sewer design completed successfully. "
            f"{len(results)} records processed."
        )

        st.subheader("Results")

        st.dataframe(
            style_results(results),
            use_container_width=True,
            hide_index=True,
        )

        # =====================================================
        # PROJECT TOTALS
        # =====================================================

        st.subheader("Project Totals")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Population",
            int(df["Residential Population"].sum()),
        )

        col2.metric(
            "Residential Area (ha)",
            f"{df['Residential_Area_ha'].sum():.2f}",
        )

        col3.metric(
            "Industrial Area (ha)",
            f"{df['Industrial_Area_ha'].sum():.2f}",
        )

        # =====================================================
        # DOWNLOAD RESULTS
        # =====================================================

        export_results = results.copy()

        population_count_columns = [
            "Residential Population",
            "Population Cumulative",
        ]

        for col in export_results.select_dtypes(
            include=[np.number]
        ).columns:

            if col in population_count_columns:

                export_results[col] = export_results[col].map(
                    lambda value: (
                        f"{value:.0f}"
                        if pd.notna(value)
                        else ""
                    )
                )

            elif col in [
                "Upstream_Invert_m",
                "Downstream_Invert_m",
            ]:

                export_results[col] = export_results[col].map(
                    lambda value: (
                        f"{value:.3f}"
                        if pd.notna(value)
                        else ""
                    )
                )

            else:

                export_results[col] = export_results[col].map(
                    lambda value: (
                        f"{value:.2f}"
                        if pd.notna(value)
                        else ""
                    )
                )

        export_results["Q Peak / Q Capacity (%)"] = (
            results["Q Peak / Q Capacity (%)"].map(
                lambda value: (
                    f"{value:.2f}%"
                    if pd.notna(value)
                    else ""
                )
            )
        )

        csv_data = export_results.to_csv(index=False)

        st.download_button(
            label="Download Sewer Design CSV",
            data=csv_data,
            file_name="sanitary_sewer_design.csv",
            mime="text/csv",
        )

    except Exception as e:

        st.error(f"Error: {str(e)}")

        st.exception(e)

else:

    st.info("Upload a CSV file to begin.")
