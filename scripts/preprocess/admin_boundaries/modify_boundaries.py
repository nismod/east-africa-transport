"""Functions for plotting
"""
import os
import sys
import json
import warnings
import geopandas as gpd
import pandas as pd
import numpy
from tqdm import tqdm
tqdm.pandas()

def load_config():
    """Read config.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..","..", "config.json")
    with open(config_path, "r") as config_fh:
        config = json.load(config_fh)
    return config

def correct_iso_code(x):
    if str(x["ISO_A3"]) == "-99":
        return x["ADM0_A3"]
    else:
        return x["ISO_A3"] 

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']

    input_admin_boundaries = os.path.join(processed_data_path,"Admin_boundaries","gadm36_levels_gpkg","gadm36_levels.gpkg")
    output_admin_boundaries = os.path.join(processed_data_path,"Admin_boundaries","gadm36_levels_gpkg","gadm36_levels_continents.gpkg")

    global_country_info = gpd.read_file(os.path.join(processed_data_path,
                                            "Admin_boundaries",
                                            "ne_10m_admin_0_countries",
                                            "ne_10m_admin_0_countries.shp"))[["ADM0_A3","ISO_A3","NAME","CONTINENT","geometry"]]
    global_country_info["ISO_A3"] = global_country_info.progress_apply(lambda x:correct_iso_code(x),axis=1)
    
    countries = gpd.read_file(input_admin_boundaries,layer="level0")
    countries = pd.merge(countries,global_country_info[["ISO_A3","NAME","CONTINENT"]],how="left",left_on=["GID_0"],right_on=["ISO_A3"])
    countries.to_file(output_admin_boundaries,layer="level0",driver="GPKG")
    

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

