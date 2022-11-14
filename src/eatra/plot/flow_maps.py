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

def get_weights(years,output_data_path,edges,flow_column):
    df = []
    
    for year in years:
        filename = "edge_flows_capacity_constrained_" + year + ".csv"
                    
        flow_data = pd.read_csv(os.path.join(output_data_path,
                                          "flow_paths",
                                          filename))
        
        flow_data_gpd = flow_data.merge(edges, on='edge_id').fillna(0)
        flow_data_gpd = gpd.GeoDataFrame(flow_data_gpd, geometry="geometry")
        flow_data_gpd["year"] = year
        
        df.append(flow_data_gpd)
        
    df = pd.concat(df,axis=0,ignore_index=True).fillna(0)
    
    weights = [
                getattr(record,flow_column)
                for record in df.itertuples() if getattr(record,flow_column) > 0
            ]

    return weights, df

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,"flow_maps")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    admin_boundaries = os.path.join(processed_data_path,
                                    "Admin_boundaries",
                                    "east_africa_admin_levels",
                                    "admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = country_risk_basemap_attributes()
    map_plot = map_country_codes[4]


    years = ["2019","2030","2050","2080"]
    flow_column = "total_tonnage"
    legend_title = "Freight flow (tons/day)"
    no_value_string = "No risk/exposure/operation"

    sector_details = sector_attributes()
    for sector in sector_details:
        if sector["sector"] in ["rail","road"]: 
            edges = gpd.read_file(os.path.join(
                                    processed_data_path,
                                    "networks",
                                    sector["sector"],
                                    sector["sector_gpkg"]),
                                    layer=sector["edge_layer"])

            if len(edges) > 0:
                if edges.crs is None:
                    edges = edges.set_crs(epsg=AFRICA_GRID_EPSG)
                else:
                    edges = edges.to_crs(epsg=AFRICA_GRID_EPSG)

            edges["mode"] = sector["sector"]

            edges = edges[["edge_id","mode","geometry"]]

            weights, df = get_weights(years,output_data_path,edges,flow_column)
            
            if weights != []:
                for year in years:
                    flow_data_gpd = df[df["year"] == year]

                    countries = geopandas.read_file(admin_boundaries,layer="level0").to_crs(AFRICA_GRID_EPSG)
                    countries = countries[countries["GID_0"].isin(map_plot["boundary_countries"])]
                    
                    lakes = geopandas.read_file(lakes_path).to_crs(AFRICA_GRID_EPSG)
                    regions = geopandas.read_file(admin_boundaries,layer="level1").to_crs(AFRICA_GRID_EPSG)
                    regions = regions[regions["GID_0"].isin(map_plot["center_countries"])]
                    coastal_prov = regions[regions["GID_1"].isin(map_plot["coastal_provinces"])]

                    bounds = countries[countries["GID_0"].isin(map_plot["center_countries"])].geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
                    offset = map_plot["offset_river"]
                    figsize = (14,16)
                    arrow_location=(0.88,0.08)
                    scalebar_location=(0.92,0.05)

                    bounds = (bounds[0]-offset[0],bounds[2]+offset[1],bounds[1]-offset[2],bounds[3]+offset[3])
                    ax_proj = get_projection(extent=bounds) 

                    figsize = (12,12)

                    fig, ax = plt.subplots(1,1,
                        subplot_kw={'projection': ax_proj},
                        figsize=figsize,
                        dpi=300)

                    ax = get_axes(ax,extent=bounds)

                    plot_basemap(ax, countries,lakes,
                                regions=regions
                                )
                    scale_bar_and_direction(ax,arrow_location,scalebar_location,scalebar_distance=50)
                    ax = line_map_plotting_colors_width(
                                ax,flow_data_gpd,weights,flow_column,
                                # edge_colors=['#d82e00','#b31c11','#841f0f','#5e0709','#200000'], red
                                #edge_colors=['#009a43','#047932','#045922','#033b14','#002000'], # green
                                legend_label=legend_title,
                                no_value_label=no_value_string,
                                width_step=0.01,
                                line_steps = 8,
                                edge_categories=["1","2","3","4","5","6","7"],
                                edge_colors=['#fdae6b','#f16913','#4c9b82','#2d6c69','#3182bd','#29557a','#000020'],
                                edge_labels=[None,None,None,None,None,None,None],
                                edge_zorder=[6,7,8,9,10,11,12],
                                interpolation="fisher-jenks",
                                plot_title=f"{legend_title}",
                                legend_location=map_plot["legend_location"]
                                )
                    ax.text(
                            0.02,
                            0.80,
                            year,
                            horizontalalignment='left',
                            transform=ax.transAxes,
                            size=18,
                            weight='bold',
                            zorder=24)

                    save_fig(
                        os.path.join(
                            folder_path, 
                            f"{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{year}.png"
                            )
                        )


                    print("Done with " + year)
            


if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

