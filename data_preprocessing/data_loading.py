import os
import json
import pandas as pd 
import numpy as np
CONFIG_PATH = "data_preprocessing/configs.json"
VOTER_DATA_FILE_NAME = "voters_2021.sav"


def load_common_variables_mapping(path: str) -> dict:
    """Load the mapping for common variables between the two datasets
    """
    with open(path, "r") as f:
        cfg = json.load(f)
    try:
        return cfg["common_items"]
    except KeyError:
        raise KeyError(f"'common_items_mapping' not found in {path}")
    

def load_party_manifesto_mapping(config_path: str) -> dict:
    """
    Pull the `manifesto_mapping` dict from the JSON config.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    mapping = cfg.get("party_manifesto_mapping", {})
    if not mapping:
        raise KeyError("'party_manifesto_mapping' not found (or empty) in config.json")
    return mapping


def get_party_positions_data(file_dir, country, file_name='party_dataset.csv') -> pd.DataFrame:
    """
    Load the party positions dataset and return rows that match a given country
    """
    csv_path = os.path.join(file_dir, file_name)
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    df = pd.read_csv(csv_path)
    # Filter by country and date
    df_filtered = df[df["countryname"] == country]

    # Columns that aren’t needed for analysis
    cols_to_drop = ["country", "oecdmember", "eumember", "party", "partyname", "parfam",
        "candidatename", "coderid", "manual", "coderyear", "id_perm", "testresult",
        "testeditsim", "pervote", "voteest", "presvote", "absseat", "totseats", "progtype", 
        "datasetorigin", "corpusversion", "total", "peruncod", "datasetversion"]
    
    df_filtered = df_filtered.drop(columns=cols_to_drop).reset_index(drop=True)
    
    # Rename Manifesto variables 
    mapping = load_party_manifesto_mapping(CONFIG_PATH)
    df_filtered.rename(columns=mapping, inplace=True)

    # Preprocessing dataframe - NaN values of numerical columns 
    df_filtered = df_filtered.apply(pd.to_numeric, errors="ignore")
    num_cols = df_filtered.select_dtypes(include="number").columns
    for col in num_cols:
        df_filtered[col] = df_filtered[col].fillna(0)

    # Preprocessing dataframe - 0 valued columns
    # zero_share = (df_filtered[num_cols] == 0).sum() / len(df_filtered)  
    # zero_cols_to_drop = zero_share[zero_share >= 0.80].index.tolist()
    # df_filtered.drop(columns=zero_cols_to_drop, inplace=True)

    # Preprocessing dataframe - datatypes and awkward column names
    df_filtered["Calendar_Week"] = df_filtered["Calendar_Week"].astype(str)
    df_filtered = df_filtered.loc[:, ~df_filtered.columns.str.startswith("+ per505")]

    common_items_mapping = load_common_variables_mapping(CONFIG_PATH)
    base_columns = ["Country", "Date", "Calendar_Week", "Party_Name"]
    policy_columns = list(common_items_mapping.keys())
    df_filtered = df_filtered[base_columns + policy_columns]

    return df_filtered


def load_gesis_mapping(fp: str=CONFIG_PATH, file_name=VOTER_DATA_FILE_NAME) -> dict:
    """Load the mapping for column names of gesis data
    """
    with open(fp, "r") as f:
        cfg = json.load(f)

    year = file_name[-8:-4]

    try:
        return cfg[f"voter_positions_{year}_mapping"]
    except KeyError:
        raise KeyError(f"'voter_positions_{year}_mapping' not found in {fp}")
    

def load_party_leaders(fp: str=CONFIG_PATH, file_name=VOTER_DATA_FILE_NAME) -> dict:
    """Load the party leaders of that year to calculate valences
    """
    with open(fp, "r") as f:
        cfg = json.load(f)

    year = file_name[-8:-4]

    try:
        return cfg["party_leaders"][year]
    except KeyError:
        raise KeyError(f"no party leaders for {year} found in {fp}")
    

def get_gesis_data(path: str="data_folder", cutoff: int=-70, file_name: str=VOTER_DATA_FILE_NAME) -> tuple[pd.DataFrame, pd.Series]:
    """Load the gesis dataset, which represents voter positions, into a dataframe and does some preprocessing 

    Parameters
    ----------
    path : str
        path to the file
    cutoff : int, optional
        all items with value below this are replaced with NaN, by default -70
        no answer is often encoded with -71

    Returns
    -------
    pd.DataFrame
        dataset loaded into a dataframe
    pd.Series
        how often each unique answer was given

    Raises
    ------
    FileNotFoundError
        file at *path* not found
    """
    sav_path = os.path.join(path, file_name)

    if not os.path.isfile(sav_path):
        raise FileNotFoundError(f"CSV file not found at: {sav_path}")

    df = pd.read_spss(path=sav_path, convert_categoricals=False)

    # rename columns
    mapping = load_gesis_mapping(CONFIG_PATH, file_name)
    df.rename(mapping, inplace=True, axis=1)

    # drop all unneeded columns
    cols = list(mapping.values())
    df.drop(df.columns.difference(cols), axis=1, inplace=True)

    cols_to_flip = [
        "importance:more social service, more taxes", 
        "not satisfied with democracy in germany"
    ]
    df = flip_columns(df, cols_to_flip)

    # replace all values below cutoff with NaN (e.g. encoding for "no answer given")
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].mask(df[num_cols] < cutoff)
    df = df.fillna(0)

    # how often each answer was given
    count = df.value_counts()

    return df, count


def flip_columns(df: pd.DataFrame, columns: list) -> pd.DataFrame:

    mappings = {}
    for column in columns:
        min = df[column].min()
        max = df[column].max() 
        before = np.arange(min, max+1)
        after = np.flip(before)
        mapping = dict(zip(before, after))
        mappings[column] = mapping
    
    df = df.replace(mappings)

    return df