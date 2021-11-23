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

AFRICA_GRID_EPSG = 4326

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['output']
    figure_path = config['paths']['figures']

    admin_boundaries = os.path.join(processed_data_path,"Admin_boundaries","east_africa_admin_levels","admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = [
                            {
                            "center_countries":["KEN","TZA","UGA","ZMB"],
                            "boundary_countries":["KEN","TZA","UGA","ZMB",
                                                    "RWA","BDI","ETH","SSD",
                                                    "SOM","COD","MWI","MOZ",
                                                    "ZWE","AGO","NAM","BWA"],
                            "country_labels":True,
                            "admin_labels":False,
                            "save_fig":"east-africa-region.png"                        
                            },

                            {
                            "center_countries":["KEN"],
                            "boundary_countries":["KEN","TZA","UGA",
                                                    "RWA","BDI","ETH","SSD",
                                                    "SOM"],
                            "country_labels":True,
                            "admin_labels":True,
                            "save_fig":"kenya-region.png"
                            },
                            {
                            "center_countries":["TZA"],
                            "boundary_countries":["KEN","TZA","UGA","ZMB",
                                                    "RWA","BDI","MWI","MOZ"],
                            "save_fig":"tanzania-region.png"
                            },
                            {
                            "center_countries":["UGA"],
                            "boundary_countries":["KEN","TZA","UGA",
                                                    "RWA","BDI","SSD",
                                                    "COD"],
                            "save_fig":"uganda-region.png"
                            },
                            {
                            "center_countries":["ZMB"],
                            "boundary_countries":["TZA","ZMB",
                                                    "COD","MWI","MOZ",
                                                    "ZWE","AGO","NAM","BWA"],
                            "save_fig":"zambia-region.png"
                            },
                        ]

    for map_plot in map_country_codes:
        countries = geopandas.read_file(admin_boundaries,layer="level0").to_crs(AFRICA_GRID_EPSG)
        countries = countries[countries["GID_0"].isin(map_plot["boundary_countries"])]
        bounds = countries[countries["GID_0"].isin(map_plot["center_countries"])].geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
        print ("Orignial",bounds)
        bounds = (bounds[0]-0.2,bounds[2]+0.2,bounds[1]-0.1,bounds[3])
        print ("Modified",bounds)
        ax_proj = get_projection(extent=bounds)
        lakes = geopandas.read_file(lakes_path).to_crs(AFRICA_GRID_EPSG)
        regions = geopandas.read_file(admin_boundaries,layer="level1").to_crs(AFRICA_GRID_EPSG)
        regions = regions[regions["GID_0"].isin(map_plot["center_countries"])]
        fig, ax = plt.subplots(1,1,
                subplot_kw={'projection': ax_proj},
                figsize=(12,12),
                dpi=500)
        ax = get_axes(ax,extent=bounds)
        plot_basemap(ax, countries,lakes,regions=regions,country_labels=False,region_labels=False)
        # plot_basemap(ax, countries,regions=regions,region_labels=True)
        scale_bar_and_direction(ax,scalebar_distance=50)
        save_fig(os.path.join(figure_path,map_plot["save_fig"]))

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

