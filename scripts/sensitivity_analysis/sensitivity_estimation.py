"""Combine all esitimates into one table
"""
import os
import sys
import json
import warnings
import geopandas
import pandas
import numpy

def load_config():
    """Read config.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    with open(config_path, "r") as config_fh:
        config = json.load(config_fh)
    return config

def get_adaptation_options():
    adaptation_options = [
        {
            "num":"None",
            "option":"no_adaptation",
            "folder_name":"risk_results",
            "flood_protection":0
        },
        {
            "num":0,
            "option":"swales",
            "folder_name":"adaptation_option_0",
            "flood_protection":1.0/0.1
        },
        {
            "num":1,
            "option":"spillways",
            "folder_name":"adaptation_option_1",
            "flood_protection":1.0/0.1
        },
        {
            "num":2,
            "option":"embankments",
            "folder_name":"adaptation_option_2",
            "flood_protection":0
        },
        {
            "num":3,
            "option":"floodwall",
            "folder_name":"adaptation_option_3",
            "flood_protection":1.0/0.02
        },
        {
            "num":4,
            "option":"drainage",
            "folder_name":"adaptation_option_4",
            "flood_protection":1.0/0.02
        },
        {
            "num":5,
            "option":"upgrading",
            "folder_name":"adaptation_option_5",
            "flood_protection":0
        }
    ]

    return adaptation_options

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']


    folder_path = os.path.join(results_data_path,'global_sensitivity')
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    hazard_csv = os.path.join(processed_data_path, 
        'hazards',
        'hazard_layers.csv')
    hazard_data_details = pd.read_csv(hazard_csv,encoding='latin1')
    hazard_keys = hazard_data_details["key"].values.tolist()
    
    adaptation_options = get_adaptation_options()
    sector_details = ["rail_edges","road_edges"]
    for sector in sector_details:
        sector_df = []
        for option in adaptation_options:
            folder_name = option['folder_name']        
            damage_results_folder = f"{folder_name}/direct_damages/{sector}"
            with open(parameter_combinations_file,"r") as r:
                for p in r:
                    pv = p.strip(" ").split(",")
                    df = pd.read_parquet(os.path.join(results_data_path,
                                            damage_results_folder,
                                            f"{sector}_direct_damages_parameter_set_{pv[0]}.parquet"))
                    df["cost_uncertainty_parameter"] = pv[1]
                    df["damage_uncertainty_parameter"] = pv[2]
                    df_keys = [c for c in df.columns.values.tolist() if c in hazard_keys]
                    df = df.groupby(["cost_uncertainty_parameter",
                                    "damage_uncertainty_parameter"])[df_keys].sum(axis=0).reset_index()
                    df = df.melt(id_vars=["cost_uncertainty_parameter",
                                    "damage_uncertainty_parameter"], 
                                    var_name="key", 
                                    value_name="value")
                    df["option"] = option["option"]
                    df = pd.merge(df,hazard_keys,how="left",on=["key"])
                    sector_df.append(df)

        sector_df = pd.concat(sector_df,axis=0,ignore_index=True)
        sector_df.to_csv(os.path.join(folder_path,f"{sector}_direct_damages_all_parameters.csv"),index=False)

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

