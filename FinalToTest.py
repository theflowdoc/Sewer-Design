
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

This tool supports **preliminary sanitary sewer network calculations**. It reads
pipe, manhole, population, area, and pipe geometry data from a CSV file, then
calculates cumulative upstream contributions, estimated sewage flows, and
hydraulic performance for each pipe.

**Main capabilities**

- **CSV input template:** Download a standardized template, enter the initial
  project data, and upload the completed file.
- **Branched network accumulation:** Uses the upstream (`From`) and downstream
  (`To`) manhole IDs to combine residential population, residential area, and
  industrial area from connected upstream pipes at shared manholes, independent
  of CSV row order.
- **Population calculations:** Calculates local residential population from
  population density and residential area, rounds population counts upward to
  whole people, and totals cumulative upstream population.
- **Sewage flow calculations:** Calculates the Harmon peaking factor, peak
  population flow, peak ICI flow, extraneous flow, and total peak design flow
  using the design parameters provided in the sidebar.
- **Pipe hydraulic calculations:** Calculates pipe slope, Manning-based full-flow
  capacity, full-flow velocity, and peak-flow-to-capacity ratio.
- **Interactive input tables:** Allows population density, residential area,
  industrial area, pipe length, pipe diameter, and invert elevations to be edited
  in the app, with dependent calculations refreshed from the edited values.
- **Results and review:** Presents separate Population, Flows, and Sewer Data
  tables, a combined Results table, project totals, and a downloadable results CSV.
- **Visual checks:** Highlights velocities at or below 0.60 m/s or at or above
  3.00 m/s in red, velocities above 0.60 through 0.75 m/s in orange, and
  peak-flow/capacity ratios of 80% or greater in red.

**Design reference:** The app's workflow and selected calculation methods are
informed by the Ontario Ministry of the Environment's *Design Guidelines for
Sewage Works* (MOE). Read the [official Ontario guidelines](https://www.ontario.ca/document/design-guidelines-sewage-works-0).

**Important:** This app is a calculation aid; it does not implement every
requirement in the guidelines or independently certify design compliance.
Confirm the applicable current provincial and municipal criteria, project-specific
conditions, assumptions, and results through appropriate engineering review.
""")

# =====================================================
# START HERE: DOWNLOAD THE INPUT TEMPLATE
# =====================================================

st.info(
    "**Start here:** Download the CSV template below, fill in your initial "
    "sewer and population information, save it as a CSV file, and then upload "
    "it to begin the calculations. Keep the column headers exactly as provided. "
    "The app uses these predefined headers to identify each field."
)

# Keep these headers stable: the app's column-mapping logic uses them to
# recognize the input fields. CSV files themselves cannot lock header cells,
# so the instructions above ask users not to rename them.
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

# Include a few blank rows so users can start entering records immediately.
template_df = pd.DataFrame(
    [{column: "" for column in template_columns} for _ in range(5)],
    columns=template_columns,
)
template_csv = template_df.to_csv(index=False)

st.download_button(
    label="Download CSV Input Template",
    data=template_csv,
    file_name="sanitary_sewer_input_template.csv",
    mime="text/csv",
    help="Download this file, enter your initial data, and upload the completed CSV below.",
)

st.caption(
    "Required input fields: Location, Pipe ID, From, To, Subcatchment Area ID, "
    "Population per ha, and Residential Area (ha). Other fields can be filled "
    "when applicable; missing optional numeric values default to zero."
)

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
    "Upload your completed CSV template to begin calculations",
    type=["csv"],
    help="Use the downloaded template and keep its column headers unchanged.",
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

            elif (
                c in ["pop", "population per ha", "population/ha", "population per hectare", "pop/ha"]
                or (("pop" in c or "population" in c) and ("/ha" in c or "per ha" in c or "hectare" in c))
            ):
                rename_map[col] = "Population_per_ha"

            elif "industrial" in c:
                rename_map[col] = "Industrial_Area_ha"

            elif c in ["area", "area (ha)", "residential area", "residential area (ha)"] or (
                "residential" in c and "area" in c
            ):
                rename_map[col] = "Residential_Area_ha"

            elif "length" in c:
                rename_map[col] = "Length_m"

            elif "diameter" in c or c in ["pipe size", "pipe size (mm)", "diameter (mm)"]:
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
        # PERSIST INPUTS FROM THE UPLOADED CSV AND APP EDITORS
        # =====================================================

        population_editable_columns = [
            "Population_per_ha",
            "Residential_Area_ha",
            "Industrial_Area_ha"
        ]
        editable_columns = [
            "Length_m", "Pipe_Diameter_mm", "Upstream_Invert_m", "Downstream_Invert_m"
        ]

        # Keep a canonical working copy so edits made in the app are not replaced
        # by the original CSV on the next Streamlit rerun. A new CSV resets it.
        upload_signature = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
        if st.session_state.get("upload_signature") != upload_signature:
            st.session_state["upload_signature"] = upload_signature
            st.session_state["design_inputs_df"] = df.copy(deep=True)
            st.session_state["editor_generation"] = (
                st.session_state.get("editor_generation", 0) + 1
            )
        elif "design_inputs_df" not in st.session_state:
            st.session_state["design_inputs_df"] = df.copy(deep=True)
            st.session_state["editor_generation"] = (
                st.session_state.get("editor_generation", 0) + 1
            )

        # The working copy contains the most recently edited values, not values
        # re-read from the CSV. All calculations below use this working copy.
        df = st.session_state["design_inputs_df"].copy(deep=True)

        def save_editor_changes(editor_key, columns):
            """Merge widget edits into the persistent input dataframe."""
            editor_state = st.session_state.get(editor_key, {})
            edited_rows = (
                editor_state.get("edited_rows", {})
                if isinstance(editor_state, dict) else {}
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
                                pd.Series([changes[col]]), errors="coerce"
                            ).iloc[0]
                            working.at[row_index, col] = 0.0 if pd.isna(value) else value

            st.session_state["design_inputs_df"] = working
            # Re-key both editors after a change. This clears stale widget deltas
            # while preserving all current values in design_inputs_df.
            st.session_state["editor_generation"] = (
                st.session_state.get("editor_generation", 0) + 1
            )

        # =====================================================
        # POPULATION CALCULATIONS BY CONNECTED SEWER NETWORK
        # =====================================================

        # Each row's residential/industrial area is treated as the LOCAL
        # contribution assigned to that pipe. For every pipe, cumulative loads
        # include its local contribution plus all upstream pipes whose To_MH_ID
        # connects to this pipe's From_MH_ID. This works regardless of CSV row
        # order and automatically combines tributary branches at shared manholes.
        #
        # Population counts/density are whole people. Round upward before using
        # the values in flow calculations.
        df["Population_per_ha"] = np.ceil(
            pd.to_numeric(df["Population_per_ha"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
        )
        df["Residential_Area_ha"] = (
            pd.to_numeric(df["Residential_Area_ha"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
        )
        df["Industrial_Area_ha"] = (
            pd.to_numeric(df["Industrial_Area_ha"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
        )
        df["Residential Population"] = np.ceil(
            df["Population_per_ha"] * df["Residential_Area_ha"]
        ).astype(int)

        def calculate_network_cumulative(data):
            """Accumulate local pipe loads through the directed From -> To network.

            Uses a topological pass rather than CSV row order, so branches can
            join at shared manholes and large networks do not depend on recursion
            depth.
            """
            data = data.copy()
            row_count = len(data)

            def clean_node(value):
                if pd.isna(value):
                    return None
                value = str(value).strip()
                return value if value else None

            from_nodes = [clean_node(value) for value in data["From_MH_ID"]]
            to_nodes = [clean_node(value) for value in data["To_MH_ID"]]

            # Index pipes by their downstream manhole. Any pipe ending at the
            # current pipe's From manhole is an upstream contributing pipe.
            incoming_pipes = {}
            for pipe_index, to_node in enumerate(to_nodes):
                if to_node is not None:
                    incoming_pipes.setdefault(to_node, []).append(pipe_index)

            parents = []
            downstream_children = [[] for _ in range(row_count)]
            pending_parent_count = [0] * row_count
            for child_index, from_node in enumerate(from_nodes):
                upstream_indices = incoming_pipes.get(from_node, []) if from_node is not None else []
                upstream_indices = [idx for idx in upstream_indices if idx != child_index]
                parents.append(upstream_indices)
                pending_parent_count[child_index] = len(upstream_indices)
                for parent_index in upstream_indices:
                    downstream_children[parent_index].append(child_index)

            cumulative_population = data["Residential Population"].astype(float).tolist()
            cumulative_res_area = data["Residential_Area_ha"].astype(float).tolist()
            cumulative_ind_area = data["Industrial_Area_ha"].astype(float).tolist()

            # Start with pipes that have no upstream pipes. Propagate each pipe's
            # full accumulated load into every pipe leaving its downstream MH.
            queue = [idx for idx, count in enumerate(pending_parent_count) if count == 0]
            processed_count = 0
            queue_position = 0
            while queue_position < len(queue):
                parent_index = queue[queue_position]
                queue_position += 1
                processed_count += 1

                for child_index in downstream_children[parent_index]:
                    cumulative_population[child_index] += cumulative_population[parent_index]
                    cumulative_res_area[child_index] += cumulative_res_area[parent_index]
                    cumulative_ind_area[child_index] += cumulative_ind_area[parent_index]
                    pending_parent_count[child_index] -= 1
                    if pending_parent_count[child_index] == 0:
                        queue.append(child_index)

            if processed_count != row_count:
                cycle_indices = [idx for idx, count in enumerate(pending_parent_count) if count > 0]
                cycle_pipe_ids = data.iloc[cycle_indices]["Pipe_ID"].astype(str).tolist()
                raise ValueError(
                    "A loop/cycle was detected in the pipe network. Check the From and "
                    "To manhole IDs for these pipe records: "
                    f"{', '.join(cycle_pipe_ids)}. A gravity sewer network should not "
                    "contain directed cycles."
                )

            data["Population Cumulative"] = np.ceil(cumulative_population).astype(int)
            data["Area Cumulative (ha)"] = cumulative_res_area
            data["Industrial Cumulative Area (ha)"] = cumulative_ind_area
            return data

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

        # Recalculate using the current persistent editable values before rendering tables.
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
        for col in ["Population_per_ha", "Residential Population", "Population Cumulative"]:
            population_formats[col] = "{:.0f}"
        styled_population_results = population_results.style.format(population_formats)
        population_disabled_columns = [
            col for col in population_columns
            if col not in population_editable_columns
        ]
        editor_generation = st.session_state.get("editor_generation", 0)
        population_editor_key = f"population_data_editor_{editor_generation}"
        edited_population_data = st.data_editor(
            styled_population_results,
            column_config={
                "Location": st.column_config.TextColumn("Location"),
                "Pipe_ID": st.column_config.TextColumn("Pipe ID"),
                "From_MH_ID": st.column_config.TextColumn("From MH ID"),
                "To_MH_ID": st.column_config.TextColumn("To MH ID"),
                "Subcatchment_ID": st.column_config.TextColumn("Subcatchment Area ID"),
                "Population_per_ha": st.column_config.NumberColumn(
                    "Population per ha", min_value=0, step=1, format="%.0f"
                ),
                "Residential_Area_ha": st.column_config.NumberColumn(
                    "Residential Area (ha)", min_value=0.0, step=0.1, format="%.2f"
                ),
                "Residential Population": st.column_config.NumberColumn(
                    "Residential Population", format="%.0f"
                ),
                "Area Cumulative (ha)": st.column_config.NumberColumn(
                    "Area Cumulative (ha)", format="%.2f"
                ),
                "Population Cumulative": st.column_config.NumberColumn(
                    "Population Cumulative", format="%.0f"
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
            key=population_editor_key,
            on_change=save_editor_changes,
            args=(population_editor_key, population_editable_columns)
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
            for col in ["Population_per_ha", "Residential Population", "Population Cumulative"]:
                if col in frame.columns:
                    formats[col] = "{:.0f}"
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

        editor_generation = st.session_state.get("editor_generation", 0)
        sewer_editor_key = f"sewer_data_editor_{editor_generation}"
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
            key=sewer_editor_key,
            on_change=save_editor_changes,
            args=(sewer_editor_key, editable_columns)
        )

        # All current editable values have already been merged into the persistent
        # dataframe by the editor callback before this rerun. Calculations above
        # therefore feed the same current values into Results and the CSV export.

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
        population_count_columns = [
            "Population_per_ha", "Residential Population", "Population Cumulative"
        ]
        for col in export_results.select_dtypes(include=[np.number]).columns:
            if col in population_count_columns:
                export_results[col] = export_results[col].map(
                    lambda value: f"{value:.0f}" if pd.notna(value) else ""
                )
            elif col in ["Upstream_Invert_m", "Downstream_Invert_m"]:
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
