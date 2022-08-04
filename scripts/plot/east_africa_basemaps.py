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
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,"basemaps")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    ax = make_basemap(config)

    save_fig(os.path.join(folder_path,"east-africa-region.png"))

def make_basemap(config):
    processed_data_path = config['paths']['data']
    admin_boundaries = os.path.join(processed_data_path,"admin_boundaries","east_africa_admin_levels","admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = [
                            {
                            "center_countries":["KEN","TZA","UGA","ZMB"],
                            "boundary_countries":["KEN","TZA","UGA","ZMB",
                                                    "RWA","BDI","ETH","SSD",
                                                    "SOM","COD","MWI","MOZ",
                                                    "ZWE","AGO","NAM","BWA","CAF"],
                            "country_labels":True,
                            "country_label_offset":{"KEN":(0,-0.5),
                                                    "TZA":(0,0), 
                                                    "UGA":(0.5,0.5),
                                                    "ZMB":(0,-1),
                                                    "RWA":(0.15,0),
                                                    "BDI":(0,0.10),
                                                    "ETH":(0,0),
                                                    "SSD":(0.25,0),
                                                    "SOM":(-0.3,-0.3),
                                                    "COD":(1.5,-2),
                                                    "MWI":(-0.65,-0.5),
                                                    "MOZ":(2.5,2.5),
                                                    "ZWE":(0,-0.25),
                                                    "AGO":(0.5,0.5),
                                                    "NAM":(-0.15,-0.15),
                                                    "BWA":(1,-0.15),
                                                    "CAF":(1,0),
                                                    "All":(0.07,0.7)},
                            "admin_labels":False,
                            "save_fig":"east-africa-region.png"                        
                            }
                        ]
    
    for map_plot in map_country_codes:
        countries = geopandas.read_file(admin_boundaries,layer="level0").to_crs(AFRICA_GRID_EPSG)
        countries = countries[countries["GID_0"].isin(map_plot["boundary_countries"])]

        countries.loc[countries.GID_0 == "CAF", "NAME_0"] = ""
        # # gets rid of Central African Republic country label

        bounds = countries[countries["GID_0"].isin(map_plot["center_countries"])].geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
        bounds = (bounds[0]-0.2,bounds[2]+0.7,bounds[1]-0.1,bounds[3]+0.2)
        ax_proj = get_projection(extent=bounds)
        lakes = geopandas.read_file(lakes_path).to_crs(AFRICA_GRID_EPSG)
        regions = geopandas.read_file(admin_boundaries,layer="level1").to_crs(AFRICA_GRID_EPSG)
        regions = regions[regions["GID_0"].isin(map_plot["center_countries"])]
        fig, ax = plt.subplots(1,1,
                subplot_kw={'projection': ax_proj},
                figsize=(12,12),
                dpi=500)
        ax = get_axes(ax,extent=bounds)
        plot_basemap(ax, countries,lakes,
                    regions=regions,
                    country_labels=map_plot["country_labels"],
                    label_offset = map_plot["country_label_offset"],
                    region_labels=map_plot["admin_labels"])
        ax.add_geometries(
            list(countries[countries["GID_0"].isin(map_plot["center_countries"])].geometry),
            crs=AFRICA_GRID_EPSG,
            edgecolor="#a7a7a5",
            facecolor="#00000000",
            zorder=2)
        scale_bar_and_direction(ax,scalebar_distance=50)
        return ax

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

