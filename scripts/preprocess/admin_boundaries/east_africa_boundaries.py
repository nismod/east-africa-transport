"""Functions for plotting
"""
import os
import sys
import json
import warnings
import geopandas
import pandas
import numpy

AFRICA_GRID_EPSG = 4326

def load_config():
    """Read config.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..","..", "config.json")
    with open(config_path, "r") as config_fh:
        config = json.load(config_fh)
    return config

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']

    input_admin_boundaries = os.path.join(processed_data_path,"Admin_boundaries","gadm36_levels_gpkg","gadm36_levels.gpkg")
    output_admin_boundaries = os.path.join(processed_data_path,"Admin_boundaries","east_africa_admin_levels","admin_levels.gpkg")

    east_africa_countires = ["KEN","TZA","UGA","ZMB",
                            "RWA","BDI","ETH","SSD",
                            "SOM","COD","MWI","MOZ",
                            "ZWE","AGO","NAM","BWA"]
    levels = ["level0","level1","level2"]
    for level in levels:
        countries = geopandas.read_file(input_admin_boundaries,layer=level).to_crs(AFRICA_GRID_EPSG)
        countries = countries[countries["GID_0"].isin(east_africa_countires)]
        countries.to_file(output_admin_boundaries,layer=level,driver="GPKG")
    

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

