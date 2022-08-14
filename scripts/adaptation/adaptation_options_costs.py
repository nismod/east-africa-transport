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

def get_adaptation_options_costs(asset_df,asset_id):
    asset_df["dimension_cost_factor"] = asset_df.progress_apply(lambda x:get_dimension_factor(x),axis=1)
    asset_df[["dimension_factor","asset_adaptation_cost"]] = asset_df["dimension_cost_factor"].apply(pd.Series)
    asset_df["cost_multiplier"] = asset_df["dimension_factor"]*asset_df["currency_conversion"]*asset_df["asset_dimension_coversion"]
    asset_df[["initial_investment_cost",
            "periodic_maintenance_cost",
            "routine_maintenance_cost"]] = asset_df[["initial_investment_cost_per_unit",
                                                    "periodic_maintenance_cost_per_unit",
                                                    "routine_maintenance_cost_per_unit"]].multiply(asset_df["cost_multiplier"],axis="index")

    return asset_df[[asset_id,
                    "adaptation_option",
                    "option_unit_cost",
                    "initial_investment_cost_per_unit",
                    "periodic_maintenance_cost_per_unit",
                    "routine_maintenance_cost_per_unit",
                    "periodic_maintenance_intervals_years",
                    "routine_maintenance_intervals_years",
                    "asset_adaptation_cost",
                    "initial_investment_cost",
                    "periodic_maintenance_cost",
                    "routine_maintenance_cost"]]

def get_dimension_factor(x):
    dimension_type = x["asset_dimensions"]
    if dimension_type in ["length","perimeter"]:
        dimension = x.geometry.length
    elif dimension_type == "area":
        dimension = x.geometry.length * x["lanes"]
    else:
        dimension = 1

    change_type = x["change_parameter"]
    if change_type == "flood depth":
        cost_unit = "USD/m"
    else:
        cost_unit = "USD"
    return dimension, cost_unit

def assign_costs_over_time(df,asset_id,start_year=2019,end_year=2100,discounting_rate=10):
    timeseries = np.arange(start_year,end_year+1,1)
    df[timeseries] = 0
    df[timeseries[0]] += df["initial_investment_cost"]

    df = assign_maintenance_cost_over_time(df,"routine_maintenance_intervals_years",
                                        "routine_maintenance_cost",
                                        start_year=start_year,end_year=end_year)
    df = assign_maintenance_cost_over_time(df,"periodic_maintenance_intervals_years",
                                        "periodic_maintenance_cost",
                                        start_year=start_year,end_year=end_year)
    return df[[asset_id,
            "adaptation_option",
            "asset_adaptation_cost"] + list(timeseries)]

def assign_maintenance_cost_over_time(df,maintenance_intervals_years,maintenance_cost,start_year=2019,end_year=2100):
    maintain_intervals = list(set(df[maintenance_intervals_years].values.tolist()))

    if len(maintain_intervals) > 1:
        df_maintain = []
        for interval in routine_maintain_intervals:
            if interval > 0:
                maintain_years = np.arange(start_year, end_year+1,interval)
                df_mod = df[df[maintenance_intervals_years] == interval]
                df_mod[maintain_years[1:]] = df_mod[maintain_years[1:]].add(df_mod[maintenance_cost], axis=0)
                df_maintain.append(df_mod)
        if len(df_maintain) > 0:
            df_maintain = pd.concat(df_maintain,axis=0,ignore_index=True).fillna(0)
        else:
            df_maintain = df.copy()
    else:
        if maintain_intervals[0] > 0:
            df_maintain = df.copy()
            maintain_years = np.arange(start_year, end_year+1,maintain_intervals[0])
            df_maintain[maintain_years[1:]] = df_maintain[maintain_years[1:]].add(df_maintain[maintenance_cost], axis=0)
        else:
            df_maintain = df.copy()

    return df_maintain
        

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']
    
    epsg = 3857
    baseline_year = 2019
    projection_end_year = 2080
    discounting_rate = 10


    dsc_rate = calculate_discounting_rate_factor(discount_rate=discounting_rate,
                                    start_year=baseline_year,end_year=projection_end_year,maintain_period=1)
    cost_timeseries = np.arange(baseline_year,projection_end_year+1,1)

    cost_df = pd.read_excel(os.path.join(processed_data_path,
                            "adaptation",
                            "adaptation_options_and_costs.xlsx"),sheet_name="Sheet1").fillna(0)

    adaptation_results = os.path.join(results_data_path,"adaptation_costs")
    if os.path.exists(adaptation_results) == False:
        os.mkdir(adaptation_results)

    asset_data_details = pd.read_csv(os.path.join(processed_data_path,
                        "damage_curves",
                        "network_layers_hazard_intersections_details.csv"))


    for asset_info in asset_data_details.itertuples():
        asset_id = asset_info.asset_id_column
        asset_hazard = getattr(asset_info,f"river_asset_damage_lookup_column")
        asset_df = gpd.read_file(os.path.join(processed_data_path,asset_info.path),layer=asset_info.asset_layer)
        asset_df = asset_df.to_crs(epsg=epsg)
       
        adapt_costs = cost_df[cost_df['asset_name'] == asset_info.asset_gpkg]

        df = []
        for rc in adapt_costs.itertuples():
            adapt_df = asset_df
            if rc.asset_details != "all":
                adapt_df = adapt_df[adapt_df[asset_hazard] == rc.asset_details]
            for column in ["asset_dimensions",
                                "change_parameter",
                                "currency_conversion",
                                "asset_dimension_coversion",
                                "adaptation_option",
                                "option_unit_cost",
                                "initial_investment_cost_per_unit",
                                "periodic_maintenance_cost_per_unit",
                                "routine_maintenance_cost_per_unit",
                                "periodic_maintenance_intervals_years",
                                "routine_maintenance_intervals_years"]:
                adapt_df[column] = getattr(rc,column)
            adapt_df = get_adaptation_options_costs(adapt_df,asset_id)
            df.append(adapt_df)
        df = pd.concat(df, axis = 0, ignore_index = True)
        
        df.to_csv(os.path.join(adaptation_results,
                            f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_adaptation_unit_costs.csv"),
                            index=False)
        
        df = assign_costs_over_time(df,asset_id,start_year=baseline_year,
                                                        end_year=projection_end_year,
                                                        discounting_rate=discounting_rate)
        df_npv = df.copy()
        df_npv[cost_timeseries] = np.multiply(df_npv[cost_timeseries],dsc_rate)
        df["adapt_cost_npv"] = df_npv[cost_timeseries].sum(axis=1)
        
        df.to_csv(os.path.join(adaptation_results,
                f"{asset_info.asset_gpkg}_{asset_info.asset_layer}_adaptation_timeseries_and_npvs.csv"),
                index=False)
        
        print (f"Done with {asset_info.asset_gpkg}")


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)