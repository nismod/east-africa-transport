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
            "flood_protection":0.05
        },
        {
            "num":1,
            "option":"spillways",
            "option_name":"Spillways",
            "folder_name":"adaptation_option_1",
            "flood_protection":0.1
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
            "flood_protection":0.05
        },
        {
            "num":4,
            "option":"drainage",
            "option_name":"Drainage (rehabilitation)",
            "folder_name":"adaptation_option_4",
            "flood_protection":0.02
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

def get_benefits(id_column,df1,df2,df1_columns,df2_columns):
    modified_columns = dict([(c,c.replace("risk","protection_risk")) for c in df2_columns])
    df2.rename(columns=modified_columns,inplace=True)
    benefit_columns = [c.replace("risk","avoided_risk") for c in df1_columns]

    df1 = pd.merge(df1,df2,how="left",on=[id_column]).fillna(0)
    for i, (b,c) in enumerate(list(zip(benefit_columns,df1_columns))):
        if c in df2_columns:
            df1[b] = df1[c] - df1[c.replace("risk","protection_risk")]
        else:
            df1[b] = df1[c]

    return df1, benefit_columns


def get_ead_eael_benefits(id_column,df1,df2,df1_columns,df2_columns):
    modified_columns = dict([(c,c.replace("EAD","protection_EAD").replace("EAEL","protection_EAEL")) for c in df2_columns])
    df2.rename(columns=modified_columns,inplace=True)
    benefit_columns = [c.replace("EAD","avoided_EAD").replace("EAEL","avoided_EAEL") for c in df1_columns]

    df1 = pd.merge(df1,df2,how="left",on=[id_column]).fillna(0)
    for i, (b,c) in enumerate(list(zip(benefit_columns,df1_columns))):
        if c in df2_columns:
            df1[b] = df1[c] - df1[c.replace("EAD","protection_EAD").replace("EAEL","protection_EAEL")]
        else:
            df1[b] = df1[c]

    return df1, benefit_columns


def get_all_column_combinations(hzd,rcps,risk_type,val_type):
    all_c = [] 
    rcp_c = []
    for rcp in rcps:
        r_c = []
        for h in hzd:
            for rt in risk_type:
                for vt in val_type:
                    all_c.append(f"{h}__rcp_{rcp}__{rt}_{vt}")
                    r_c.append(f"{h}__rcp_{rcp}__{rt}_{vt}")
        rcp_c.append(r_c)
    return all_c,rcp_c

def get_risk_and_adaption_columns(dataframe_columns):
    EAD_columns = [c for c in dataframe_columns if "EAD_" in c]
    EAEL_columns = [c.replace("EAD","EAEL") for c in EAD_columns]
    benefit_columns = [c.replace("EAD","avoided_risk") for c in EAD_columns]
    bcr_columns = [c.replace("EAD","BCR") for c in EAD_columns]
    return EAD_columns, EAEL_columns, benefit_columns, bcr_columns

def get_risks(df,asset_id,hazard,hazard_types,rcps,risk_type,val_type,days=10):
    all_columns, rcp_columns = get_all_column_combinations(hazard_types,rcps,risk_type,val_type)
    all_columns = [c for c in df.columns.values.tolist() if c in all_columns]
    eael_columns = [c for c in all_columns if "EAEL_" in c]
    if len(eael_columns) > 0:
        df[eael_columns] = days*df[eael_columns]

    risk_rcp_columns = []
    for ri,(rcp,rcp_c) in enumerate(list(zip(rcps,rcp_columns))):
        rcp_c = [c for c in rcp_c if c in df.columns.values.tolist()]
        if len(rcp_c) > 0:
            for vt in val_type:
                vt_cols = [c for c in rcp_c if f"_{vt}" in c]
                risk_rcp_columns.append(f"{hazard}__rcp_{rcp}__risk_{vt}")
                df[f"{hazard}__rcp_{rcp}__risk_{vt}"] = df[vt_cols].sum(axis=1)

    return df[[asset_id] + risk_rcp_columns], risk_rcp_columns

def get_ead_eael(df,asset_id,hazard,hazard_types,rcps,risk_type,val_type):
    all_columns, rcp_columns = get_all_column_combinations(hazard_types,rcps,risk_type,val_type)
    all_columns = [c for c in df.columns.values.tolist() if c in all_columns]
    
    risk_rcp_columns = []
    for rt in risk_type:
        for ri,(rcp,rcp_c) in enumerate(list(zip(rcps,rcp_columns))):
            rcp_c = [c for c in rcp_c if c in df.columns.values.tolist()]
            if len(rcp_c) > 0:
                for vt in val_type:
                    vt_cols = [c for c in rcp_c if f"{rt}_{vt}" in c]
                    risk_rcp_columns.append(f"{hazard}__rcp_{rcp}__{rt}_{vt}")
                    df[f"{hazard}__rcp_{rcp}__{rt}_{vt}"] = df[vt_cols].sum(axis=1)

    return df[[asset_id] + risk_rcp_columns], risk_rcp_columns

def bcr_estimates(asset_id,option_cost_df,risk_df,hazard_thresholds_column_name,adapt_benefit_columns):
    option_cost_df["cost_units"] = "J$"
    risk_df = pd.merge(option_cost_df[[asset_id,"adaptation_option",
                                    hazard_thresholds_column_name,"cost_units","adapt_cost_npv"]],
                                risk_df,how="left",on=[asset_id]).fillna(0)
    risk_df = risk_df[risk_df["adapt_cost_npv"] > 0]
    bcr_columns = [c.replace("avoided_risk","BCR") for c in adapt_benefit_columns]
    risk_df[bcr_columns] = risk_df[adapt_benefit_columns].div(risk_df["adapt_cost_npv"],axis=0)

    return risk_df, bcr_columns

def ead_eael_estimates(asset_id,option_cost_df,risk_df,hazard_thresholds_column_name,adapt_benefit_columns):
    option_cost_df["adapt_cost_unit"] = "J$"
    option_cost_df["ead_cost_unit"] = "J$"
    option_cost_df["eael_cost_unit"] = "J$/day"
    risk_df = pd.merge(option_cost_df[[asset_id,"adaptation_option",
                                    hazard_thresholds_column_name,"adapt_cost_unit",
                                    "ead_cost_unit","eael_cost_unit","adapt_cost_npv"]],
                                risk_df,how="left",on=[asset_id]).fillna(0)
    risk_df = risk_df[risk_df["adapt_cost_npv"] > 0]

    return risk_df

def get_bcr_values(results_path,asset_id,bcr_results,asset_info,
                    hazard,rcps,risk_type,val_type,
                    no_adapt_risk_df,risk_columns,
                    option_df,
                    hazard_thresholds,cost_multiplication_factors,hazard_thresholds_column_name,
                    protection_type_name,days=10):
    # print (option_df)
    for idx, (ft,cmf) in enumerate(list(zip(hazard_thresholds,cost_multiplication_factors))):
        folder_name = f"{protection_type_name}_{str(ft).replace('.','p')}"
        results_folder = os.path.join(results_path,folder_name)
        risk_file = os.path.join(results_folder,"loss_damage_npvs",
                        f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_EAD_EAEL_npvs.csv")
        if os.path.isfile(risk_file) is True:
            adapt_risk_df = pd.read_csv(risk_file)
            # print ("Adapt")
            # print (adapt_risk_df)
            adapt_risk_df, adapt_risk_columns = get_risks(adapt_risk_df,asset_id,
                                                hazard['hazard'],hazard['hazard_type'],
                                                rcps,risk_type,val_type,days=days)
            risk_df, adapt_benefit_columns = get_benefits(asset_id,no_adapt_risk_df.copy(),adapt_risk_df,
                                                                risk_columns,adapt_risk_columns)
            
            option_cost_df = option_df.copy()
            option_cost_df[hazard_thresholds_column_name] = ft
            option_cost_df["adapt_cost_npv"] = cmf*option_cost_df["adapt_cost_npv"]
            risk_df, bcr_columns = bcr_estimates(asset_id,option_cost_df,risk_df,hazard_thresholds_column_name,adapt_benefit_columns)
            risk_df = risk_df[[asset_id,
                            "adaptation_option",
                            hazard_thresholds_column_name,
                            "cost_units",
                            "adapt_cost_npv"] + adapt_benefit_columns + bcr_columns]

            bcr_results.append(risk_df)

    return bcr_results

def get_ead_eael_costs(results_path,asset_id,ead_eael_results,asset_info,
                    hazard,rcps,risk_type,val_type,
                    no_adapt_ead_eael_df,ead_eael_columns,
                    option_df,
                    hazard_thresholds,cost_multiplication_factors,hazard_thresholds_column_name,
                    protection_type_name):
    for idx, (ft,cmf) in enumerate(list(zip(hazard_thresholds,cost_multiplication_factors))):
        folder_name = f"{protection_type_name}_{str(ft).replace('.','p')}"
        results_folder = os.path.join(results_path,folder_name)
        risk_file = os.path.join(results_folder,"loss_damage_npvs",
                        f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_EAD_EAEL_npvs.csv")
        if os.path.isfile(risk_file) is True:
            adapt_risk = pd.read_csv(risk_file)
            adapt_ead_eael_df, adapt_ead_eael_columns = get_ead_eael(adapt_risk,asset_id,
                                                hazard['hazard'],hazard['hazard_type'],
                                                rcps,risk_type,val_type)
            # print (no_adapt_ead_eael_df.columns.values.tolist())
            ead_eael_df, ead_eael_benefit_columns = get_ead_eael_benefits(asset_id,no_adapt_ead_eael_df.copy(),
                                                                adapt_ead_eael_df,
                                                                ead_eael_columns,adapt_ead_eael_columns)
            
            option_cost_df = option_df.copy()
            option_cost_df[hazard_thresholds_column_name] = ft
            option_cost_df["adapt_cost_npv"] = cmf*option_cost_df["adapt_cost_npv"]
            option_cost_df["adapt_cost_unit"] = "J$"
            option_cost_df["ead_cost_unit"] = "J$"
            option_cost_df["eael_cost_unit"] = "J$/day"
            ead_eael_df = pd.merge(option_cost_df[[asset_id,"adaptation_option",
                                    hazard_thresholds_column_name,"adapt_cost_unit",
                                    "ead_cost_unit","eael_cost_unit","adapt_cost_npv"]],
                                    ead_eael_df,how="left",on=[asset_id]).fillna(0)
            ead_eael_df = ead_eael_df[ead_eael_df["adapt_cost_npv"] > 0]
            ead_eael_df = ead_eael_df[[asset_id,
                            "adaptation_option",
                            hazard_thresholds_column_name,
                            "adapt_cost_unit",
                            "ead_cost_unit",
                            "eael_cost_unit",
                            "adapt_cost_npv"] + ead_eael_benefit_columns]

            ead_eael_results.append(ead_eael_df)

    return ead_eael_results

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['output']
     
    days = 15
    adaptation_results = os.path.join(output_data_path,"adaptation_costs")
    adaptation_bcr_results = os.path.join(output_data_path,"adaptation_benefits_costs_bcr")
    if os.path.exists(adaptation_bcr_results) == False:
        os.mkdir(adaptation_bcr_results)

    non_adapt_risk_results = os.path.join(output_data_path,"risk_results","loss_damage_npvs")
    hazard_adapt_costs = os.path.join(output_data_path,"adaptation_costs")
    asset_data_details = pd.read_csv(os.path.join(processed_data_path,
                        "damage_curves",
                        "network_layers_hazard_intersections_details.csv"))
    for asset_info in asset_data_details.itertuples():
        asset_adaptation_df = []
        asset_id = asset_info.asset_id_column
        for option in adaptation_options:
            folder_name = option['folder_name']
            option_results_folder = os.path.join(results_path,f"{folder_name}/loss_damage_npvs")
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
                    adapt_ids = adapt_costs_df[asset_id].values.tolist()
                    no_adapt_risk_df = pd.read_csv(no_adapt_risk_file)
                    adapt_risk_df = pd.read_csv(os.path.join(
                                                option_results_folder,
                                                f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_EAD_EAEL_npvs.csv"))
                    
                    EAD_columns, EAEL_columns, benefit_columns, bcr_columns = get_risk_and_adaption_columns(adapt_risk_df.columns.values.tolist())
                    
                    no_adapt_risk_df = no_adapt_risk_df[no_adapt_risk_df[asset_id].isin(adapt_ids)]
                    adapt_risk_df = adapt_risk_df[adapt_risk_df[asset_id].isin(adapt_ids)]

                    no_adapt_risk_df = no_adapt_risk_df[[asset_id] + EAD_columns + EAEL_columns].set_index(asset_id)
                    adapt_risk_df = adapt_risk_df[[asset_id] + EAD_columns + EAEL_columns].set_index(asset_id)

                    no_adapt_risk_df[EAEL_columns] = days*no_adapt_risk_df[EAEL_columns]
                    adapt_risk_df[EAEL_columns] = days*adapt_risk_df[EAEL_columns]


                    adapt_risk_df[benefit_columns] = adapt_risk_df[EAD_columns].substract(no_adapt_risk_df[EAD_columns],axis='index',fill_value=0)
                    adapt_risk_df[benefit_columns] += adapt_risk_df[EAEL_columns].substract(no_adapt_risk_df[EAEL_columns],axis='index',fill_value=0)
                    adapt_risk_df[benefit_columns] = -1.0*adapt_risk_df[benefit_columns]

                    adapt_risk_df = adapt_risk_df.reset_index()
                    adapt_costs_df = pd.merge(adapt_costs_df,adapt_risk_df[[asset_id] + benefit_columns],how="left",on=[asset_id])
                    adapt_costs_df[bcr_columns] = adapt_costs_df[benefit_columns].div(adapt_costs_df["adapt_cost_npv"],axis=0)

                    asset_adaptation_df.append(adapt_costs_df)
                else:
                    print (f"* {option['option_name']} does not apply to {asset_info.asset_gpkg} {asset_info.asset_layer}")

        if len(asset_adaptation_df) > 0:
            asset_adaptation_df = pd.concat(asset_adaptation_df,axis=0,ignore_index=False)

            asset_adaptation_df.to_csv(os.path.join(adaptation_bcr_results,
                f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_adaptation_benefits_costs_bcr.csv"),index=False)

            print (f"* Done with {asset_info.asset_gpkg} {asset_info.asset_layer} BCRs")




                



if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)