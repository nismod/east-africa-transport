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
    output_data_path = config['paths']['output']
    figure_path = config['paths']['figures']

    admin_boundaries = os.path.join(processed_data_path,"Admin_boundaries","east_africa_admin_levels","admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = country_basemap_attributes()
    # print (map_country_codes)
    sector_details = sector_attributes() 
    for sector in sector_details:
        if sector["sector"] in ("road","rail"):
            for map_plot in map_country_codes:
                countries = geopandas.read_file(admin_boundaries,layer="level0").to_crs(AFRICA_GRID_EPSG)
                countries = countries[countries["GID_0"].isin(map_plot["boundary_countries"])]
                bounds = countries[countries["GID_0"].isin(map_plot["center_countries"])].geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
                bounds = (bounds[0]-0.2,bounds[2]+0.4,bounds[1]-0.1,bounds[3]+0.2)
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
                scale_bar_and_direction(ax,scalebar_distance=50)
                edges = gpd.read_file(os.path.join(
                                    processed_data_path,
                                    map_plot["country"],
                                    "networks",
                                    sector["sector_gpkg"]),
                                    layer=sector["edge_layer"])
                if edges.crs is None:
                    edges = edges.set_crs(epsg=AFRICA_GRID_EPSG)
                else:
                    edges = edges.to_crs(epsg=AFRICA_GRID_EPSG)
                nodes = []
                legend_handles = []
                if len(edges) > 0:
                        ax, legend_handles = plot_lines_and_points(ax,legend_handles,sector,sector_dataframe=edges,layer_key="edge")
                if len(nodes) > 0:
                    ax, legend_handles = plot_lines_and_points(ax,legend_handles,sector,sector_dataframe=nodes,layer_key="node")
                
                ax.legend(handles=legend_handles,fontsize=10,loc=map_plot["legend_location"]) 
                save_fig(os.path.join(figure_path,f"{map_plot['country']}-{sector['sector']}-network.png"))

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

