# ------------------------------------------
# CLEAN COLUMN NAMES
# ------------------------------------------

df.columns = (
    df.columns
    .str.strip()
    .str.replace("(", "", regex=False)
    .str.replace(")", "", regex=False)
    .str.replace(".", "_", regex=False)
)

# ------------------------------------------
# AUTOMATIC COLUMN DETECTION
# ------------------------------------------

column_map = {}

for col in df.columns:

    col_lower = col.lower()

    if "location" in col_lower or "street" in col_lower:
        column_map[col] = "Location"

    elif "pipe id" in col_lower or col_lower == "pipeid":
        column_map[col] = "Pipe_ID"

    elif "from mh" in col_lower:
        column_map[col] = "From_MH_ID"

    elif "to mh" in col_lower:
        column_map[col] = "To_MH_ID"

    elif col_lower in ["from", "frommh"]:
        column_map[col] = "From_MH_ID"

    elif col_lower in ["to", "tomh"]:
        column_map[col] = "To_MH_ID"

    elif "subcatchment" in col_lower:
        column_map[col] = "Subcatchment_ID"

    elif "subc" in col_lower:
        column_map[col] = "Subcatchment_ID"

    elif "population per ha" in col_lower:
        column_map[col] = "Residential_Pop_per_ha"

    elif col_lower == "pop":
        column_map[col] = "Residential_Pop_per_ha"

    elif (
        "industrial" in col_lower
        and "area" in col_lower
    ):
        column_map[col] = "Industrial_Commercial_Area_ha"

    elif (
        "area" in col_lower
        and "industrial" not in col_lower
    ):
        column_map[col] = "Residential_Area_ha"

df.rename(columns=column_map, inplace=True)

st.write("Detected columns:")
st.write(df.columns.tolist())
