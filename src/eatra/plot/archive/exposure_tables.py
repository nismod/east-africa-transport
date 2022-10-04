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

def quantiles(dataframe,grouping_by_columns,grouped_columns):
    quantiles_list = ['median','q5','q95']
    df_list = []
    df_columns = []
    for quant in quantiles_list:
        if quant == 'median':
            df = dataframe.groupby(grouping_by_columns)[grouped_columns].quantile(0.5)
        elif quant == 'q5':
            df = dataframe.groupby(grouping_by_columns)[grouped_columns].quantile(0.05)
        elif quant == 'q95':
            df = dataframe.groupby(grouping_by_columns)[grouped_columns].quantile(0.95)

        df.rename(columns=dict((g,f"{g}_{quant}") for g in grouped_columns),inplace=True)
        df_columns += [f"{g}_{quant}" for g in grouped_columns]
        df_list.append(df)
    return pd.concat(df_list,axis=1).reset_index(), df_columns

def filter_asset_total_damage_values(sector,damage_data_path,
                            damage_string,
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

    #damages, damage_sum_columns = quantiles(damages,[asset_id_column] + damage_groupby,damage_sum_columns)

    damages = damages.groupby(
                    damage_groupby,dropna=False
                    ).agg(
                        dict(
                            zip(
                                damage_sum_columns,["sum"]*len(damage_sum_columns)
                                )
                            )
                        ).reset_index() 
    
    min_damages = min(damages[damage_sum_columns].min())
    max_damages = max(damages[damage_sum_columns].max())

    return damages, min_damages, max_damages

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_path = config['paths']['results']
    output_path = config['paths']['output']

    folder_path = os.path.join(output_path,"exposure_table")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    map_country_codes = country_risk_basemap_attributes()
    sector_details = sector_attributes() 
    damage_string = "direct_damages" 
    damage_columns = ["exposure_median","exposure_q5","exposure_q95"]
    damage_groupby = ["hazard","rcp","rp","epoch"]
    damages_filter_columns = ["hazard","rcp","epoch"]

    hazard = ["coastal","river"]
    years = ["2030","2050","2080"]
    rcp = ["4.5","8.5"]
    rcp_colors = ['#2171b5','#08306b']
    rcp_markers = ['s-','^-']

    for sector in sector_details:
        if sector["sector"] in ["road","rail"]:
            for map_plot in map_country_codes:
                    damage_data_path = os.path.join(results_path,
                                                            map_plot["country"],    
                                                            "direct_damages_summary") 
                    for h in hazard:
                        tot_damages_filter_values = [
                                                    (h,"baseline","1980"),
                                                    (h,"baseline","hist"),
                                                    (h,"4.5","2030"),
                                                    (h,"4.5","2050"),
                                                    (h,"4.5","2080"),
                                                    (h,"8.5","2030"),
                                                    (h,"8.5","2050"),
                                                    (h,"8.5","2080")
                                                    ]
                        
                        tot_damages, min_limits, max_limits = filter_asset_total_damage_values(sector,
                                                                damage_data_path,damage_string,
                                                                damages_filter_columns,
                                                                tot_damages_filter_values,
                                                                damage_groupby,damage_columns,"edge")
                        if tot_damages.empty == False:
                            tot_damages.to_excel(
                             os.path.join(
                                        folder_path, 
                                        f"{map_plot['country']}_{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{h}_exposures_table.xlsx"
                                        )
                                    )

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

