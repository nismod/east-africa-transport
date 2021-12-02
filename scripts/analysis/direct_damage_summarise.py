"""Estimate direct damages to physical assets exposed to hazards

"""
import sys
import os

import pandas as pd
import geopandas as gpd
from shapely import wkb
import numpy as np
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def quantiles(dataframe,grouping_by_columns,grouped_columns):
    quantiles_list = ['mean','min','max','median','q5','q95']
    df_list = []
    for quant in quantiles_list:
        if quant == 'mean':
            # print (dataframe)
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].mean()
        elif quant == 'min':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].min()
        elif quant == 'max':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].max()
        elif quant == 'median':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].quantile(0.5)
        elif quant == 'q5':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].quantile(0.05)
        elif quant == 'q95':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].quantile(0.95)

        df.rename(columns=dict((g,'{}_{}'.format(g,quant)) for g in grouped_columns),inplace=True)
        df_list.append(df)
    return pd.concat(df_list,axis=1).reset_index()

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    country_attributes = [
                            {
                            'country': 'kenya',
                            },
                            {
                            'country': 'tanzania',
                            },
                            {
                            'country': 'uganda',
                            },
                            {
                            'country': 'zambia',
                            },
                        ]

    damage_data_path = os.path.join(processed_data_path,
                            "damage_estimation_processing")
    asset_data_details = pd.read_csv(os.path.join(damage_data_path,
                        "network_layers_hazard_intersections_details.csv"))

    for country in country_attributes:
        direct_damages_results = os.path.join(results_data_path,
                                            country["country"],
                                            "direct_damages")
        summary_results = os.path.join(results_data_path,country["country"],"direct_damages_summary")
        if os.path.exists(summary_results) == False:
            os.mkdir(summary_results)

        param_values = pd.read_csv(os.path.join(damage_data_path, f"{country['country']}_parameter_combinations.txt"), sep=" ")
        uncertainty_columns = param_values.columns.values.tolist()[1:]
        damage_results_types = ["direct_damages","EAD"]
        
        for asset_info in asset_data_details.itertuples():
            asset_damages_results = os.path.join(direct_damages_results,f"{asset_info.asset_gpkg}_{asset_info.asset_layer}")
            for damages_type in damage_results_types:
                damages = []
                for param in param_values.itertuples():
                    damage_file = os.path.join(
                                    asset_damages_results,
                                    f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_{damages_type}_parameter_set_{param.parameter_set}.csv"
                                    )
                    if os.path.isfile(damage_file) is True:
                        damages.append(pd.read_csv(damage_file).fillna(0))
                print ("* Done with creating list of all dataframes")
                            
                damages = pd.concat(damages,axis=0,ignore_index=True)
                print ("* Done with concatinating all dataframes")
                            
                #index_columns = [asset_info.asset_id_column,"exposure_unit","damage_cost_unit","hazard","rp","rcp","epoch"]
                index_columns = [c for c in damages.columns.values.tolist() if (
                                            c not in ["exposure","direct_damage_cost","subsidence","model","confidence"]
                                            ) and ("EAD_" not in c)]
                index_columns = [i for i in index_columns if i not in uncertainty_columns]
                
                damage_columns = [c for c in damages.columns.values.tolist() if (
                                            c in ["exposure","direct_damage_cost"]
                                            ) or ("EAD_" in c)]

                summarised_damages = quantiles(damages,index_columns,damage_columns)
                        
                summarised_damages.to_csv(os.path.join(summary_results,
                            f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_{damages_type}.csv"),index=False)

                print (f"* Done with {country['country']} {asset_info.asset_gpkg} {asset_info.asset_layer} {damages_type}")

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)