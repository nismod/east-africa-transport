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

    folder_path = os.path.join(figure_path,"adaptation_maps")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    admin_boundaries = os.path.join(processed_data_path,
                                    "Admin_boundaries",
                                    "east_africa_admin_levels",
                                    "admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = country_risk_basemap_attributes()
    map_plot = map_country_codes[4]


    days = ["15","30","60","90","180"]
    day = days[0]

    plots = [
                {
                "plot_column":"max_benefit",
                "legend_title":"Max Benefit (USD) over time",
                "no_value_string":"No risk/exposure/operation"
                },
                {
                "plot_column":"adapt_cost_npv",
                "legend_title":"Max Investment (USD) over time",
                "no_value_string":"No risk/exposure/operation"
                },
                {
                "plot_column":"max_BCR",
                "legend_title":"Max BCR over time",
                "no_value_string":"No risk/exposure/operation"
                }
                ]

    for plot in plots:
        if plot["plot_column"] in ["max_benefit","adapt_cost_npv","max_BCR"]:
            plot_column = plot["plot_column"]
            legend_title = plot["legend_title"]
            no_value_string = plot["no_value_string"]

            width_step=0.02
            line_step=6

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

                    filename = sector["sector"] + "_edges_optimal_benefits_costs_bcr_" + day + "_days_disruption.csv"
                            
                    data = pd.read_csv(os.path.join(output_data_path,
                                                      "adaptation_benefits_costs_bcr",
                                                      filename))
                    
                    data_gpd = data.merge(edges, on='edge_id').fillna(0)
                    data_gpd = gpd.GeoDataFrame(data_gpd, geometry="geometry")

                    weights = [
                                    getattr(record,plot_column)
                                    for record in data_gpd.itertuples() if getattr(record,plot_column) > 0
                                ]

                    if plot_column == "max_BCR":
                        # change the weight bins 

                        width_ranges = generate_weight_bins(weights, n_steps=line_step, width_step=width_step, interpolation='fisher-jenks')
                        bcr_bins = [(0.0,1.0),(1.0,4.0),(4.0,8.0),(8.0,16.0),(16.0,max(weights))]

                        width_by_range = OrderedDict()

                        i = 0 
                        for key,value in width_ranges.items():
                            width_by_range[bcr_bins[i]] = value
                            i += 1

                        # replace label
                        data_gpd.loc[data_gpd.max_BCR < 1, 'adaptation_option'] = "BCR < 1"
                        
                    
                    if weights != []:
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
                        
                        ax = plot_line_assets(ax,edges.crs,edges,
                                              colors="#969696",
                                              size=0.2,
                                              linestyle="solid",
                                              zorder=5)

                        if plot_column == "max_BCR":
                            ax = line_map_plotting_colors_width(
                                ax,data_gpd,weights,plot_column,
                                legend_label=legend_title,
                                no_value_label=no_value_string,
                                width_step=width_step,
                                line_steps=line_step,
                                edge_classify_column = "adaptation_option",
                                edge_categories=["BCR < 1","Swales","Spillways","Mobile flood embankments","Flood Wall","Drainage (rehabilitation)","Upgrading to paved"],
                                edge_colors=["#ffff33","#4daf4a","#984ea3","#ff7f00","#e41a1c","#377eb8","#a65628"],
                                edge_labels=["BCR < 1","Swales","Spillways","Mobile flood embankments","Flood Wall","Drainage (rehabilitation)","Upgrading to paved"],
                                edge_zorder=[6,7,8,9,10,11,12],
                                interpolation="fisher-jenks",
                                plot_title=f"{legend_title}",
                                legend_location=map_plot["legend_location"],
                                bbox_to_anchor=(0,0.7),
                                width_ranges = width_by_range,
                                max_plus=True
                                )
                        else:
                            ax = line_map_plotting_colors_width(
                                ax,data_gpd,weights,plot_column,
                                legend_label=legend_title,
                                no_value_label=no_value_string,
                                width_step=width_step,
                                line_steps =line_step,
                                edge_classify_column = "adaptation_option",
                                edge_categories=["Swales","Spillways","Mobile flood embankments","Flood Wall","Drainage (rehabilitation)","Upgrading to paved"],
                                edge_colors=["#4daf4a","#984ea3","#ff7f00","#e41a1c","#377eb8","#a65628"],
                                edge_labels=["Swales","Spillways","Mobile flood embankments","Flood Wall","Drainage (rehabilitation)","Upgrading to paved"],
                                edge_zorder=[6,7,8,9,10,11],
                                interpolation="fisher-jenks",
                                plot_title=f"{legend_title}",
                                legend_location=map_plot["legend_location"],
                                bbox_to_anchor=(0,0.7)
                                )

                        save_fig(
                            os.path.join(
                                folder_path, 
                                f"{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{plot_column}.png"
                                )
                            )


                        print("Done with " + plot_column + " of " + sector['sector_label'])
            


if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

