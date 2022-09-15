"""Estimate adaptation options costs and benefits

"""
import sys
import os

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)
import geopandas as gpd
import numpy as np
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def get_adaptation_options():
    adaptation_options = [
        {
            "num":0,
            "option":"swales",
            "option_name":"Swales",
            "folder_name":"adaptation_option_0",
            "flood_protection":1.0/0.1
        },
        {
            "num":1,
            "option":"spillways",
            "option_name":"Spillways",
            "folder_name":"adaptation_option_1",
            "flood_protection":1.0/0.1
        },
        {
            "num":2,
            "option":"embankments",
            "option_name":"Mobile flood embankments",
            "folder_name":"adaptation_option_2",
            "flood_protection":0
        },
        {
            "num":3,
            "option":"floodwall",
            "option_name":"Flood Wall",
            "folder_name":"adaptation_option_3",
            "flood_protection":1.0/0.02
        },
        {
            "num":4,
            "option":"drainage",
            "option_name":"Drainage (rehabilitation)",
            "folder_name":"adaptation_option_4",
            "flood_protection":1.0/0.02
        },
        {
            "num":5,
            "option":"upgrading",
            "option_name":"Upgrading to paved ",
            "folder_name":"adaptation_option_5",
            "flood_protection":0
        }
    ]

    return adaptation_options


def get_risk_and_adaption_columns(dataframe_columns):
    EAD_columns = [c for c in dataframe_columns if "EAD_" in c]
    EAEL_columns = [c.replace("EAD","EAEL") for c in EAD_columns]
    benefit_columns = [c.replace("EAD","avoided_risk") for c in EAD_columns]
    bcr_columns = [c.replace("EAD","BCR") for c in EAD_columns]
    return EAD_columns, EAEL_columns, benefit_columns, bcr_columns

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']
     
    days = 15
    adaptation_results = os.path.join(results_data_path,"adaptation_costs")
    adaptation_bcr_results = os.path.join(results_data_path,"adaptation_benefits_costs_bcr")
    if os.path.exists(adaptation_bcr_results) == False:
        os.mkdir(adaptation_bcr_results)

    non_adapt_risk_results = os.path.join(results_data_path,"risk_results","loss_damage_npvs")
    hazard_adapt_costs = os.path.join(results_data_path,"adaptation_costs")
    asset_data_details = pd.read_csv(os.path.join(processed_data_path,
                        "damage_curves",
                        "network_layers_hazard_intersections_details.csv"))
    dlist = [1,15,30,60,90,180]
    adaptation_options = get_adaptation_options()
    for days in [1]:
        for asset_info in asset_data_details.itertuples():
            asset_adaptation_df = []
            asset_id = asset_info.asset_id_column
            for option in adaptation_options:
                folder_name = option['folder_name']
                option_results_folder = os.path.join(results_data_path,f"{folder_name}/loss_damage_npvs")
                cost_file = os.path.join(hazard_adapt_costs,
                                            f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_adaptation_timeseries_and_npvs.csv")
                no_adapt_risk_file = os.path.join(non_adapt_risk_results,
                                            f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_EAD_EAEL_npvs.csv")
                if (os.path.isfile(cost_file) is True) and (os.path.isfile(no_adapt_risk_file) is True):
                    print (f"* Starting with {option['option']} {asset_info.asset_gpkg} {asset_info.asset_layer}")
                    cost_df = pd.read_csv(cost_file)
                    adapt_costs_df = cost_df[cost_df["adaptation_option"] == option["option_name"]]
                    if len(adapt_costs_df.index) > 0:
                        adapt_costs_df = adapt_costs_df[[asset_id, "adaptation_option","adapt_cost_npv"]]
                        no_adapt_risk_df = pd.read_csv(no_adapt_risk_file)
                        adapt_risk_df = pd.read_csv(os.path.join(
                                                    option_results_folder,
                                                    f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_EAD_EAEL_npvs.csv"))
                        
                        EAD_columns, EAEL_columns, benefit_columns, bcr_columns = get_risk_and_adaption_columns(adapt_risk_df.columns.values.tolist())
                        
                        adapt_ids = adapt_risk_df[asset_id].values.tolist()

                        no_adapt_risk_df = no_adapt_risk_df[no_adapt_risk_df[asset_id].isin(adapt_ids)]
                        adapt_costs_df = adapt_costs_df[adapt_costs_df[asset_id].isin(adapt_ids)]

                        no_adapt_risk_df = no_adapt_risk_df[[asset_id] + EAD_columns + EAEL_columns].set_index(asset_id)
                        adapt_risk_df = adapt_risk_df[[asset_id] + EAD_columns + EAEL_columns].set_index(asset_id)

                        no_adapt_risk_df[EAEL_columns] = days*no_adapt_risk_df[EAEL_columns]
                        adapt_risk_df[EAEL_columns] = days*adapt_risk_df[EAEL_columns]

                        adapt_risk_df[EAD_columns] = adapt_risk_df[EAD_columns].sub(
                                                            no_adapt_risk_df[EAD_columns],
                                                            axis='index',
                                                            fill_value=0)
                        adapt_risk_df[EAEL_columns] = adapt_risk_df[EAEL_columns].sub(
                                                                no_adapt_risk_df[EAEL_columns],
                                                                axis='index',fill_value=0
                                                                )
                        for idx,(b,d,i) in enumerate(list(zip(benefit_columns,EAD_columns,EAEL_columns))):
                            adapt_risk_df[d] = -1.0*adapt_risk_df[d]
                            adapt_risk_df[i] = -1.0*adapt_risk_df[i]
                            adapt_risk_df[b] = adapt_risk_df[d] + adapt_risk_df[i]


                        adapt_risk_df = adapt_risk_df.reset_index()
                        adapt_costs_df = pd.merge(adapt_costs_df,adapt_risk_df[[asset_id] + EAD_columns + EAEL_columns + benefit_columns],how="left",on=[asset_id])
                        num = adapt_costs_df._get_numeric_data()
                        num[num < 0] = 0
                        adapt_costs_df[bcr_columns] = adapt_costs_df[benefit_columns].div(adapt_costs_df["adapt_cost_npv"],axis=0)

                        asset_adaptation_df.append(adapt_costs_df)
                    else:
                        print (f"* {option['option_name']} does not apply to {asset_info.asset_gpkg} {asset_info.asset_layer}")

            if len(asset_adaptation_df) > 0:
                asset_adaptation_df = pd.concat(asset_adaptation_df,axis=0,ignore_index=False)

                asset_adaptation_df.to_csv(os.path.join(adaptation_bcr_results,
                    f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_adaptation_benefits_costs_bcr_{days}_days_disruption.csv"),
                    index=False)

                asset_adaptation_df.to_parquet(os.path.join(adaptation_bcr_results,
                    f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_adaptation_benefits_costs_bcr_{days}_days_disruption.parquet"),
                    index=False)

                print (f"* Done with {asset_info.asset_gpkg} {asset_info.asset_layer} BCRs for {days} days disruption")

                """Find optimal asset values by BCR
                """
                asset_adaptation_df["max_BCR"] = asset_adaptation_df[bcr_columns].max(axis=1)
                asset_adaptation_df["max_benefit"] = asset_adaptation_df[benefit_columns].max(axis=1)
                preferred_options = asset_adaptation_df[asset_adaptation_df["max_BCR"] >= 1]
                non_preferred_options = asset_adaptation_df[
                                            ~asset_adaptation_df[asset_id].isin(
                                                list(
                                                    set(
                                                        preferred_options[asset_id].values.tolist()
                                                        )
                                                    )
                                                )
                                            ]
                non_preferred_options = non_preferred_options.sort_values(by="max_BCR",ascending=False)
                non_preferred_options = non_preferred_options.drop_duplicates(subset=[asset_id],keep="first")
                preferred_options = preferred_options.sort_values(by="max_benefit",ascending=False)
                preferred_options = preferred_options.drop_duplicates(subset=[asset_id],keep="first")
                pd.concat([preferred_options,non_preferred_options],axis=0,ignore_index=True).to_csv(
                        os.path.join(adaptation_bcr_results,
                        f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_optimal_benefits_costs_bcr_{days}_days_disruption.csv"),
                        index=False)

                pd.concat([preferred_options,non_preferred_options],axis=0,ignore_index=True).to_parquet(
                        os.path.join(adaptation_bcr_results,
                        f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_optimal_benefits_costs_bcr_{days}_days_disruption.parquet"),
                        index=False)


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)