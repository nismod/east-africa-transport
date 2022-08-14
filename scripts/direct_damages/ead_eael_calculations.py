"""Estimate direct damages to physical assets exposed to hazards

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

def add_economic_loss_estimates(dataframe,dataframe_id_column,time_epoch,economic_loss_scenario):
    if economic_loss_scenario != "none":
        if str(time_epoch).isdigit() is True:
            year = int(str(time_epoch))
            if year < 2030:
                year = 2019
        else:
            year = 2019
        loss_df = pd.read_csv(os.path.join(
                                    economic_loss_scenario,
                                    f"economic_losses_{year}.csv"))
        dataframe = pd.merge(dataframe,loss_df[[dataframe_id_column,"economic_loss"]],
                        how="left",on=[dataframe_id_column]).fillna(0)
        dataframe["economic_loss_unit"] = "US$/day"
    
    return dataframe

def main(config,results_folder,
        network_csv,hazard_csv,
        flood_protection_period,
        flood_protection_name,
        set_count,
        cost_uncertainty_parameter,
        damage_uncertainty_parameter):
    
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    direct_damages_results = os.path.join(results_data_path,results_folder)
    asset_data_details = pd.read_csv(network_csv)

    for asset_info in asset_data_details.itertuples():
        asset_id = asset_info.asset_id_column
        asset_damages_results = os.path.join(direct_damages_results,f"{asset_info.asset_gpkg}_{asset_info.asset_layer}")
        damage_file = os.path.join(
                            asset_damages_results,
                            f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_direct_damages_parameter_set_{set_count}.parquet"
                            )
        if os.path.isfile(damage_file) is True:
            expected_damages = []
            total_losses = []
            df = pd.read_parquet(damage_file)
            hazard_columns = [c for c in df.columns.values.tolist() if c not in [
                                                                    asset_id,
                                                                    'damage_cost_unit'
                                                                    'exposure']]
            df = df.groupby([asset_id,'damage_cost_unit'])[hazard_columns].sum().reset_index()
            hazard_data_details = pd.read_csv(hazard_csv,encoding="latin1").fillna(0)
            hazard_data_details = hazard_data_details[hazard_data_details.key.isin(hazard_columns)]
            # haz_rcp_epoch_confidence = list(set(hazard_data_details.set_index(["hazard","rcp","epoch","confidence"]).index.values.tolist()))
            haz_rcp_epoch_confidence_subsidence_model = list(set(hazard_data_details.set_index(["hazard","rcp","epoch","confidence","subsidence","model"]).index.values.tolist()))
            # for i,(haz,rcp,epoch,confidence) in enumerate(haz_rcp_epoch_confidence):
            for i,(haz,rcp,epoch,confidence,subsidence,model) in enumerate(haz_rcp_epoch_confidence_subsidence_model):
                haz_df = hazard_data_details[
                                    (hazard_data_details.hazard == haz
                                    ) & (
                                    hazard_data_details.rcp == rcp
                                    ) & (
                                    hazard_data_details.epoch == epoch
                                    ) & (
                                    hazard_data_details.confidence == confidence
                                    ) & (
                                    hazard_data_details.subsidence == subsidence
                                    ) & (
                                    hazard_data_details.model == model
                                    )]
                haz_cols, haz_rps = map(list,list(zip(*sorted(
                                            list(zip(haz_df.key.values.tolist(),
                                            haz_df.rp.values.tolist()
                                            )),key=lambda x:x[-1],reverse=True))))
                haz_prob = [1.0/rp for rp in haz_rps]
                df = add_economic_loss_estimates(df,
                                                    asset_info.asset_id_column,
                                                    epoch,
                                                    os.path.join(results_data_path,asset_info.economic_loss_scenarios))
                if 'economic_loss' in df.columns.values.tolist():
                    index_columns = [asset_id,"damage_cost_unit","economic_loss_unit"]
                    loss_column = ["economic_loss"]
                    losses = df.copy()
                    losses[haz_cols] = losses["economic_loss"].to_numpy()[:,None]*np.where(losses[haz_cols]>0,1,0)
                    losses.drop("economic_loss",axis=1,inplace=True)
                    print (losses[haz_cols])
                    total_losses.append(losses)
                    del losses
                else:
                    index_columns = [asset_id,"damage_cost_unit"]
                    loss_column = []

                damages = df[index_columns + loss_column + haz_cols]
                df.drop("economic_loss",axis=1,inplace=True)
                damages["hazard"] = haz
                damages["rcp"] = rcp
                damages["epoch"] = epoch
                damages["confidence"] = confidence
                damages["subsidence"] = subsidence
                damages["model"] = model
                damages.columns = index_columns + loss_column + haz_prob + ["hazard","rcp","epoch","confidence","subsidence","model"] 
                index_columns += ["hazard","rcp","epoch","confidence","subsidence","model"] 
                damages = damages[damages[haz_prob].sum(axis=1) > 0]
                losses = damages.copy()
                losses.columns = losses.columns.map(str)

                expected_damage_df = risks(damages,index_columns,haz_prob,
                                            "EAD",
                                            flood_protection_period=flood_protection_period,
                                            flood_protection_name=flood_protection_name)
                if 'economic_loss' in damages.columns.values.tolist():
                    losses[[str(h) for h in haz_prob]] = losses["economic_loss"].to_numpy()[:,None]*np.where(losses[[str(h) for h in haz_prob]]>0,1,0)
                    economic_loss_df = risks(losses,index_columns,haz_prob,
                                            "EAEL",
                                            flood_protection_period=flood_protection_period,
                                            flood_protection_name=flood_protection_name
                                            )
                    expected_damage_df = pd.merge(expected_damage_df,economic_loss_df,how='left',on=index_columns).fillna(0)
                    del economic_loss_df

                expected_damages.append(expected_damage_df)
                del expected_damage_df

            expected_damages = pd.concat(expected_damages,axis=0,ignore_index=True)
            expected_loss_columns = [c for c in expected_damages.columns.values.tolist() if "EAD_" in c or "EAEL_" in c]
            expected_damages = expected_damages[expected_damages[expected_loss_columns].sum(axis=1) > 0]
            expected_damages["cost_uncertainty_parameter"] = cost_uncertainty_parameter
            expected_damages["damage_uncertainty_parameter"] = damage_uncertainty_parameter
            asset_damages_results = os.path.join(direct_damages_results,f"{asset_info.asset_gpkg}_{asset_info.asset_layer}")
            if os.path.exists(asset_damages_results) == False:
                os.mkdir(asset_damages_results)
            expected_damages.to_csv(os.path.join(asset_damages_results,
                        f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_EAD_EAEL_parameter_set_{set_count}.csv"),
                        index=False)

            if len(total_losses) > 0:
                print (total_losses)
                total_losses = pd.concat(total_losses,axis=0,ignore_index=True)
                loss_index_columns = [asset_info.asset_id_column,"economic_loss_unit"]
                loss_coluumns = [c for c in total_losses.columns.values.tolist() if c not in loss_index_columns]
                total_losses = total_losses.groupby(loss_index_columns)[loss_coluumns].sum().reset_index()
                
                total_losses.to_parquet(os.path.join(
                        asset_damages_results,
                        f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_economic_losses_parameter_set_{set_count}.parquet"),
                        index=False)
                total_losses.to_csv(os.path.join(asset_damages_results,
                        f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_economic_losses_parameter_set_{set_count}.csv"),
                        index=False)

        print (f"* Done with {asset_info.asset_gpkg} {asset_info.asset_layer}")
                

if __name__ == "__main__":
    CONFIG = load_config()
    try:
        results_folder = str(sys.argv[1])
        network_csv = str(sys.argv[2])
        hazard_csv = str(sys.argv[3])
        flood_protection_period = float(sys.argv[4])
        flood_protection_name = str(sys.argv[5])
        if flood_protection_name == "None":
            flood_protection_name = None
        set_count = str(sys.argv[6])
        cost_uncertainty_parameter = float(sys.argv[7])
        damage_uncertainty_parameter = float(sys.argv[8])
    except IndexError:
        print("Got arguments", sys.argv)
        exit()

    main(CONFIG,results_folder,
        network_csv,hazard_csv,
        flood_protection_period,
        flood_protection_name,
        set_count,
        cost_uncertainty_parameter,
        damage_uncertainty_parameter)
