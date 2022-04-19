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
from plot_utils import *
from east_africa_plotting_attributes import *
from east_africa_basemaps import *

AFRICA_GRID_EPSG = 4326

def main(config):
    processed_data_path = config['paths']['data']
    figure_path = config['paths']['figures']
    
    folder_path = os.path.join(figure_path,"network_edges")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    sector_details = sector_attributes() 

    for sector in sector_details:
        if sector["sector"] in ("road","rail"):
            edges = gpd.read_file(os.path.join(
                                processed_data_path,
                                "networks",
                                sector["sector"],
                                sector["sector_gpkg"]),
                                layer=sector["edge_layer"])
            if edges.crs is None:
                edges = edges.set_crs(epsg=AFRICA_GRID_EPSG)
            else:
                edges = edges.to_crs(epsg=AFRICA_GRID_EPSG)
            nodes = []
            legend_handles = []
            
            ax = make_basemap(config)

            if len(edges) > 0:
                    ax, legend_handles = plot_lines_and_points(ax,legend_handles,sector,sector_dataframe=edges,layer_key="edge")
            if len(nodes) > 0:
                ax, legend_handles = plot_lines_and_points(ax,legend_handles,sector,sector_dataframe=nodes,layer_key="node")
            
            ax.legend(handles=legend_handles,fontsize=10,loc="upper left") 
            save_fig(os.path.join(folder_path,f"{sector['sector']}-network.png"))

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

