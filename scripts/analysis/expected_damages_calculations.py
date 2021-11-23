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
        param_values = pd.read_csv(os.path.join(damage_data_path, f"{country['country']}_parameter_combinations.txt"), sep=" ")
        direct_damages_results = os.path.join(results_data_path,
                                            country["country"],
                                            "direct_damages")
        
        for asset_info in asset_data_details.itertuples():
            asset_damages_results = os.path.join(
                                            results_data_path,
                                            country["country"],
                                            "direct_damages",
                                            f"{asset_info.asset_gpkg}_{asset_info.asset_layer}"
                                        )
            for param in param_values.itertuples():
                damage_file = os.path.join(
                                    asset_damages_results,
                                    f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_direct_damages_parameter_set_{param.parameter_set}.csv"
                                    )
                if os.path.isfile(damage_file) is True:
                    expected_damages = []
                    df = pd.read_csv(damage_file).fillna(0)
                    haz_rcp_epoch_conf_subs_model = list(set(df.set_index(["hazard","rcp","epoch","confidence","subsidence","model"]).index.values.tolist()))
                    for i,(haz,rcp,epoch,conf,subs,model) in enumerate(haz_rcp_epoch_conf_subs_model):
                        damages = df[(df.hazard == haz) & (df.rcp == rcp) & (df.epoch == epoch) & (df.confidence == conf) & (df.subsidence == subs) & (df.model == model)]
                        damages['probability'] = 1.0/damages['rp']
                        index_columns = [c for c in damages.columns.values.tolist() if c not in [
                                                                            'rp',
                                                                            'probability',
                                                                            'direct_damage_cost',
                                                                            'exposure']
                                        ]

                        
                        damages.to_csv("/Users/dianajaramillo/Desktop/testing/direct_damages/damages.csv") 

                        expected_damage_df = risks_pivot(damages,index_columns,'probability',
                                                    'direct_damage_cost',None,'EAD',
                                                    flood_protection=None)
                        expected_damages.append(expected_damage_df)
                        
                        del expected_damage_df

                    expected_damages = pd.concat(expected_damages,axis=0,ignore_index=True)
                    asset_damages_results = os.path.join(direct_damages_results,f"{asset_info.asset_gpkg}_{asset_info.asset_layer}")
                    if os.path.exists(asset_damages_results) == False:
                        os.mkdir(asset_damages_results)
                    expected_damages.to_csv(os.path.join(asset_damages_results,
                                f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_EAD_parameter_set_{param.parameter_set}.csv"),
                                index=False)
            print (f"* Done with {asset_info.asset_gpkg} {asset_info.asset_layer} for {country['country']}")
                



if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)