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

def get_asset_total_damage_values(sector,damages,
                            asset_dataframe,
                            damages_filter_columns,damages_filter_values,
                            layer_key,climate_scenario="baseline"):
    asset_id_column = sector[f"{layer_key}_id_column"]
    asset_filter_column = sector[f"{layer_key}_damage_filter_column"]
    asset_filter_list = sector[f"{layer_key}_damage_categories"]    
    
    for d_filter in damages_filter_columns:
        damages[d_filter] = damages[d_filter].apply(str)
    
    damages = damages.set_index(damages_filter_columns)
    damages = damages[damages.index.isin(damages_filter_values)].reset_index()
    if asset_filter_column is not None:
        if asset_filter_column == "status" and climate_scenario == "baseline":
            asset_ids = asset_dataframe[asset_dataframe[asset_filter_column].isin(["open"])][asset_id_column].values.tolist()
        else:
            asset_ids = asset_dataframe[asset_dataframe[asset_filter_column].isin(asset_filter_list)][asset_id_column].values.tolist()
        damages = damages[damages[asset_id_column].isin(asset_ids)]
    

    return pd.merge(
                    asset_dataframe[[asset_id_column,sector[f"{layer_key}_classify_column"],"geometry"]],
                    damages,how="left",on=[asset_id_column]).fillna(0)

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    risk_results_path = os.path.join(output_data_path,"risk_results","direct_damages_summary",)
    admin_boundaries = os.path.join(processed_data_path,
                                    "Admin_boundaries",
                                    "east_africa_admin_levels",
                                    "admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = country_risk_basemap_attributes()
    sector_details = sector_attributes() 
    
    # User input required
    type_damage = "EAEL" # Select between "EAD" or "EAEL" 
    num_plots = "grouped" # Select between single (1 file per plot) or grouped (4 files per plot)

    damage_string = "EAD_EAEL"
    damage_groupby = ["hazard","rcp","epoch"]
    damages_filter_columns = ["hazard","rcp","epoch"]
    no_value_string = "No risk/exposure/operation"

    if type_damage == "EAD":
        damage_column = "EAD_no_adaptation_mean"
        legend_title = "Expected Annual Damages (US$)"
        folder_path = os.path.join(figure_path,"ead_maps",num_plots)

    if type_damage == "EAEL":
        damage_column = "EAEL_no_adaptation_mean"
        legend_title = "Expected Annual Losses (US$/day)"
        folder_path = os.path.join(figure_path,"eael_maps",num_plots)

    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    hazard = ["river","coastal"]
    rcp = ["4.5","8.5"]
     
    for sector in sector_details:
        if sector["sector"] in ["rail","road"]: 
            map_plot = map_country_codes[4] # regional
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

                    # damage_data_path = os.path.join(output_data_path,"risk_results")
                    for h in hazard:
                        if h == "river":
                            baseyear = "1980"
                        if h == "coastal":
                            baseyear = "hist"

                        tot_damages_filter_values = [
                                                    (h,"baseline",baseyear),
                                                    (h,"4.5","2030"),
                                                    (h,"4.5","2050"),
                                                    (h,"4.5","2080"),
                                                    (h,"8.5","2030"),
                                                    (h,"8.5","2050"),
                                                    (h,"8.5","2080")
                                                    ]
                        
                        tot_edges = pd.read_parquet(
                                        os.path.join(
                                        risk_results_path,
                                        f"{sector['sector']}_{sector['edge_layer']}_{damage_string}.parquet"
                                        )
                                    )
                        
                        
                        weights = [
                            getattr(record,damage_column)
                            for record in tot_edges.itertuples() if getattr(record,damage_column) > 0
                        ]

                        if weights != []:
                            for r in rcp:
                                print("* Starting sector: "+sector['sector_label']+", hazard: "+h+", rcp: "+r+".")
                                damages_filter_values = [
                                                            (h,"baseline",baseyear),
                                                            (h,r,"2030"),
                                                            (h,r,"2050"),
                                                            (h,r,"2080")
                                                        ]
                                damages_filter_lables = ["Baseline","RCP "+r+" - 2030","RCP "+r+" - 2050","RCP "+r+" - 2080"]
                            
                                countries = geopandas.read_file(admin_boundaries,layer="level0").to_crs(AFRICA_GRID_EPSG)
                                countries = countries[countries["GID_0"].isin(map_plot["boundary_countries"])]
                                
                                lakes = geopandas.read_file(lakes_path).to_crs(AFRICA_GRID_EPSG)
                                regions = geopandas.read_file(admin_boundaries,layer="level1").to_crs(AFRICA_GRID_EPSG)
                                regions = regions[regions["GID_0"].isin(map_plot["center_countries"])]
                                coastal_prov = regions[regions["GID_1"].isin(map_plot["coastal_provinces"])]

                                if h == "river":
                                    bounds = countries[countries["GID_0"].isin(map_plot["center_countries"])].geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
                                    offset = map_plot["offset_river"]
                                    figsize = (14,16)
                                    arrow_location=(0.88,0.08)
                                    scalebar_location=(0.92,0.05)
                                if h == "coastal":
                                    bounds = coastal_prov.geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
                                    offset = map_plot["offset_coastal"]
                                    figsize = (8,16)
                                    arrow_location=(0.83,0.1)
                                    scalebar_location=(0.87,0.07)
                                bounds = (bounds[0]-offset[0],bounds[2]+offset[1],bounds[1]-offset[2],bounds[3]+offset[3])
                                ax_proj = get_projection(extent=bounds)                                                            

                                if num_plots == "single":
                                    figsize = (12,12)

                                    for j in range(len(damages_filter_values)):
                                        fig, ax = plt.subplots(1,1,
                                            subplot_kw={'projection': ax_proj},
                                            figsize=figsize,
                                            dpi=300)

                                        edges_damages = get_asset_total_damage_values(sector,
                                                                        tot_edges.copy(),
                                                                        edges,
                                                                        damages_filter_columns,
                                                                        [damages_filter_values[j]],
                                                                        "edge",
                                                                        climate_scenario=damages_filter_values[j][1])

                                        ax = get_axes(ax,extent=bounds)

                                        plot_basemap(ax, countries,lakes,
                                                    regions=regions
                                                    )
                                        
                                        scale_bar_and_direction(ax,arrow_location,scalebar_location,scalebar_distance=50)
                                        ax = line_map_plotting_colors_width(
                                                                            ax,edges_damages,weights,damage_column,
                                                                            legend_label=legend_title,
                                                                            no_value_label=no_value_string,
                                                                            width_step=0.01,
                                                                            interpolation="fisher-jenks",
                                                                            plot_title=f"{legend_title} to {sector['sector_label']} from {h} flooding",
                                                                            legend_location=map_plot["legend_location"]
                                                                            )
                                        ax.text(
                                                0.02,
                                                0.80,
                                                f"{damages_filter_lables[j]}",
                                                horizontalalignment='left',
                                                transform=ax.transAxes,
                                                size=18,
                                                weight='bold',
                                                zorder=24)

                                        save_fig(
                                            os.path.join(
                                                folder_path, 
                                                f"{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{h}_climate_scenarios_{r}_{j}.png"
                                                )
                                            )
                                

                                if num_plots == "grouped":

                                    fig, ax_plots = plt.subplots(2,2,
                                        subplot_kw={'projection': ax_proj},
                                        figsize=figsize,
                                        dpi=300)

                                    ax_plots = ax_plots.flatten()

                                    for j in range(len(damages_filter_values)):
                                        edges_damages = get_asset_total_damage_values(sector,
                                                                        tot_edges.copy(),
                                                                        edges,
                                                                        damages_filter_columns,
                                                                        [damages_filter_values[j]],
                                                                        "edge",
                                                                        climate_scenario=damages_filter_values[j][1])
                                        ax = get_axes(ax_plots[j],extent=bounds)

                                        plot_basemap(ax, countries,lakes,
                                                    regions=regions
                                                    )
                                        
                                        scale_bar_and_direction(ax,arrow_location,scalebar_location,scalebar_distance=50)
                                        ax = line_map_plotting_colors_width(
                                                                            ax,edges_damages,weights,damage_column,
                                                                            legend_label=legend_title,
                                                                            no_value_label=no_value_string,
                                                                            width_step=0.01,
                                                                            interpolation="fisher-jenks",
                                                                            plot_title=f"{legend_title} to {sector['sector_label']} from {h} flooding",
                                                                            legend_location=map_plot["legend_location"]
                                                                            )
                                        ax.text(
                                                0.02,
                                                0.80,
                                                f"{damages_filter_lables[j]}",
                                                horizontalalignment='left',
                                                transform=ax.transAxes,
                                                size=18,
                                                weight='bold',
                                                zorder=24)                            

                                    plt.tight_layout()
                                    save_fig(
                                            os.path.join(
                                                folder_path, 
                                                f"{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{h}_climate_scenarios_{r}.png"
                                                )
                                            )

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

