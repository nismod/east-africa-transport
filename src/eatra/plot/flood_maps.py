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

AFRICA_GRID_EPSG = 4326

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    # output_data_path = config['paths']['output']
    figure_path = config['paths']['figures']
    
    folder_path = os.path.join(figure_path,"floodmaps")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)


    admin_boundaries = os.path.join(processed_data_path,"Admin_boundaries","east_africa_admin_levels","admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = country_basemap_attributes()
    for map_plot in map_country_codes:
        if map_plot["country"] == "kenya": # This line can be changed or deleted to plot more countries 
            countries = geopandas.read_file(admin_boundaries,layer="level0").to_crs(AFRICA_GRID_EPSG)
            countries = countries[countries["GID_0"].isin(map_plot["boundary_countries"])]
            
            if map_plot["center_countries"] == ['TZA']:
                countries.loc[countries.GID_0 == "COD", "NAME_0"] = ""
                countries.loc[countries.GID_0 == "MWI", "NAME_0"] = ""
                # gets rid of DRC and Malawi label for Tanzania
        
            bounds = countries[countries["GID_0"].isin(map_plot["center_countries"])].geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
            bounds = (bounds[0]-0.2,bounds[2]+0.4,bounds[1]-0.1,bounds[3]+0.2)
            ax_proj = get_projection(extent=bounds)
            lakes = geopandas.read_file(lakes_path).to_crs(AFRICA_GRID_EPSG)
            regions = geopandas.read_file(admin_boundaries,layer="level1").to_crs(AFRICA_GRID_EPSG)
            regions = regions[regions["GID_0"].isin(map_plot["center_countries"])]

            river_flood_map_path = os.path.join(processed_data_path,
                                        map_plot["country"],
                                        "hazards",
                                        "inunriver_historical_000000000WATCH_1980_rp01000.tif") 
            coastal_flood_map_path = os.path.join(processed_data_path,
                                        map_plot["country"],
                                        "hazards",
                                        "inuncoast_historical_wtsub_hist_rp1000_0.tif")
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
            scale_bar_and_direction(ax,scalebar_distance=50)

            im = plot_raster(ax, coastal_flood_map_path, cmap="Blues", levels=None, colors=None,
                    reproject_transform=AFRICA_GRID_EPSG,clip_extent=None)

            im = plot_raster(ax, river_flood_map_path, cmap="Blues", levels=None, colors=None,
                    reproject_transform=AFRICA_GRID_EPSG,clip_extent=None)

            # Add colorbar
            # I am just using the scale of the river flooding map, which I would assume would cover the coastal flood map as well
            cbar = plt.colorbar(im, ax=ax,fraction=0.1, shrink=0.87,pad=0.01, drawedges=False, orientation='horizontal')
            # cbar.set_clim(vmin=0,vmax=max_val)

            cbar.outline.set_color("none")
            cbar.ax.yaxis.set_tick_params(color='black')
            cbar.ax.set_xlabel('Flood depths (m)',fontsize=7,color='black')

            plt.title("Baseline - 1 in 1000 year river and coastal flooding", fontsize = 10)
            
            save_fig(os.path.join(folder_path,f"{map_plot['country']}-floodmap.png"))

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

