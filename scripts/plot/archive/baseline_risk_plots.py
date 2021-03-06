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

def get_asset_total_damage_values(sector,damage_data_path,
                            damage_string,asset_dataframe,
                            damages_filter_columns,damages_filter_values,
                            damage_groupby,
                            damage_sum_columns,layer_key):
    asset_id_column = sector[f"{layer_key}_id_column"]
    asset_filter_column = sector[f"{layer_key}_damage_filter_column"]
    asset_filter_list = sector[f"{layer_key}_damage_categories"]
    damages = pd.read_csv(
                    os.path.join(
                        damage_data_path,
                        f"{sector['sector_gpkg'].replace('.gpkg','')}_{sector[f'{layer_key}_layer']}_{damage_string}.csv"
                        )
                    )
    for d_filter in damages_filter_columns:
        damages[d_filter] = damages[d_filter].apply(str)
    damages = damages.set_index(damages_filter_columns)
    damages = damages[damages.index.isin(damages_filter_values)].reset_index()
    if asset_filter_column is not None:
        asset_ids = asset_dataframe[asset_dataframe[asset_filter_column].isin(asset_filter_list)][asset_id_column].values.tolist()
        damages = damages[damages[asset_id_column].isin(asset_ids)]
    damages = damages.groupby(
                    [asset_id_column] + damage_groupby,dropna=False
                    ).agg(
                        dict(
                            zip(
                                damage_sum_columns,["sum"]*len(damage_sum_columns)
                                )
                            )
                        ).reset_index() 
    # print (damages)
    return pd.merge(
                    asset_dataframe[[asset_id_column,sector[f"{layer_key}_classify_column"],"geometry"]],
                    damages,how="left",on=[asset_id_column]).fillna(0)

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,"baseline_risk")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    admin_boundaries = os.path.join(processed_data_path,"Admin_boundaries","east_africa_admin_levels","admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = country_basemap_attributes()
    sector_details = sector_attributes() 
    damage_string = "EAD" 
    damage_columns = ["EAD_undefended_mean"]
    damage_groupby = ["exposure_unit","damage_cost_unit","epoch"]
    damages_filter_columns = ["hazard","epoch"]
    damage_file_string = "_EAD_river_baseline"
    damages_filter_values = [("river",'1980')]
    no_value_string = "No risk/exposure/operation"
    legend_title = "Expected Annual Damages (US$)"
    for sector in sector_details:
        if sector["sector"] in ["road","rail"]:
            for map_plot in map_country_codes:
                edges = gpd.read_file(os.path.join(
                                    processed_data_path,
                                    map_plot["country"],
                                    "networks",
                                    sector["sector_gpkg"]),
                                    layer=sector["edge_layer"])
                if len(edges) > 0:
                    if edges.crs is None:
                        edges = edges.set_crs(epsg=AFRICA_GRID_EPSG)
                    else:
                        edges = edges.to_crs(epsg=AFRICA_GRID_EPSG)
                    damage_data_path = os.path.join(output_data_path,
                                                    map_plot["country"],    
                                                    "direct_damages_summary")
                    edges_damages = get_asset_total_damage_values(sector,
                                                        damage_data_path,damage_string,
                                                        edges,
                                                        damages_filter_columns,
                                                        damages_filter_values,
                                                        damage_groupby,damage_columns,"edge")
                    if len(edges_damages) > 0:
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
                        ax = line_map_plotting_colors_width(
                                                            ax,edges_damages,"EAD_undefended_mean",
                                                            legend_label=legend_title,
                                                            no_value_label=no_value_string,
                                                            width_step=0.01,
                                                            interpolation="fisher-jenks",
                                                            plot_title=f"{sector['sector_label']} Expected Annual Damages",
                                                            legend_location=map_plot["legend_location"]
                                                            )
                        save_fig(
                                os.path.join(
                                    folder_path, 
                                    f"{map_plot['country']}_{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{damage_file_string}.png"
                                    )
                                )

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

