"""Dissagregate OD matrix for air flows to node pairs

"""
import sys
import os

import pandas as pd
import geopandas as gpd
import fiona
import ast
import igraph as ig
from collections import defaultdict
from itertools import chain
from shapely.geometry import shape, mapping
pd.options.mode.chained_assignment = None  # default='warn'
# import warnings
# warnings.simplefilter(action='ignore', category=SettingWithCopyWarning)
import numpy as np
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    time_epochs = [2019,2030,2050,2080]
    time_epochs = [2019,2030]
    # Assumption that all road link capacities in the future will increase by 10%,30%,50%
    road_capacity_factors = [None,0.1,0.3,0.5]
    road_capacity_factors = [None,0.1]
    # Assumption that all rail line capacities in the future will be at 30%, 50% and 80% of design capacity
    rail_capacity_factors = [None,0.3,0.5,0.8]
    rail_capacity_factors = [None,0.3]
    baseline_od_year = 2015
    gdp_growth_rate = 5  # 4% growth rate assumed for the EAC region

    flow_column = "total_tonnage"
    cost_column = "max_flow_cost"
    od_columns = ["origin_id","destination_id"]
    ods_data_df = pd.read_csv(os.path.join(results_data_path,
                                        "flow_paths",
                                        "od_matrix_nodes_unique_pairs.csv"))
    ods_values_columns = [c for c in ods_data_df.columns.values.tolist() if c not in od_columns] 
    flow_combinations = list(zip(time_epochs,road_capacity_factors,rail_capacity_factors))
    for f_idx,(t_eph,road_cf,rail_cf) in enumerate(flow_combinations):   
        assigned_output_path = os.path.join(results_data_path,"flow_paths",
                        f"flow_paths_assigned_{t_eph}.csv")
        unassigned_output_path = os.path.join(results_data_path,"flow_paths",
                        f"flow_paths_unassignment_{t_eph}.csv")
        edge_flows_path = os.path.join(results_data_path,"flow_paths",
                        f"edge_flows_capacity_constrained_{t_eph}.csv")
        
        ods_df = ods_data_df.copy()
        ods_df[ods_values_columns] = ((1+1.0*gdp_growth_rate/100.0)**(t_eph - baseline_od_year))*ods_df[ods_values_columns]
        all_ods = ods_df[["origin_id","destination_id",flow_column]]
        if t_eph == time_epochs[0]:
            rail_status = ["open"]
        else:
            rail_status = ["open","proposed","rehabilitation","construction"]

        network_df = create_multi_modal_network_africa(rail_status=rail_status,
                                                    road_future_usage=road_cf,
                                                    rail_future_usage=rail_cf,
                                                    return_network=False)
        net_df = network_df.copy()
        net_df[flow_column] = 0

        capacity_ods,unassigned_paths = od_flow_allocation_capacity_constrained(all_ods,
        										net_df,flow_column,cost_column)

        if len(capacity_ods) > 0:
            capacity_ods = pd.concat(capacity_ods,axis=0,ignore_index=True)
            capacity_ods.rename(columns={flow_column:"assigned_tonnage"},inplace=True)
            capacity_ods = pd.merge(capacity_ods,ods_df,how="left",on=["origin_id","destination_id"])
            capacity_ods[ods_values_columns] = capacity_ods[ods_values_columns].multiply(
                                                capacity_ods["assigned_tonnage"]/capacity_ods[flow_column],
                                                axis="index")
            capacity_ods.drop("assigned_tonnage",axis=1,inplace=True)
            # print (capacity_ods)

            net_df = network_df.copy()
            for c in ods_values_columns:
                edge_flows = get_flow_on_edges(capacity_ods,"edge_id","edge_path",c)
                net_df = pd.merge(net_df,edge_flows,how="left",on=["edge_id"]).fillna(0)
                del edge_flows

            net_df.to_csv(edge_flows_path,index=False)

            capacity_ods["edge_path"] = capacity_ods["edge_path"].astype(str)
            vc = [c for c in capacity_ods.columns.values.tolist() if c not in ["origin_id","destination_id","edge_path"]]
            capacity_ods.groupby(["origin_id","destination_id","edge_path"])[vc].sum().reset_index()
            capacity_ods.to_csv(assigned_output_path,index=False)

        if len(unassigned_paths) > 0:
            unassigned_paths = pd.concat(unassigned_paths,axis=0,ignore_index=True)
            unassigned_paths.to_csv(unassigned_output_path,index=False)
            # print (unassigned_paths)

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)