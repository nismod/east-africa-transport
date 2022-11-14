"""Functions for plotting
"""
import os
import sys
import warnings
import geopandas
import pandas
import numpy
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
from .plot_utils import *
from .east_africa_plotting_attributes import *

AFRICA_GRID_EPSG = 4326

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,"climate_scenarios_risk")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)


    admin_boundaries = os.path.join(processed_data_path,
                                    "Admin_boundaries",
                                    "east_africa_admin_levels",
                                    "admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")



if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

