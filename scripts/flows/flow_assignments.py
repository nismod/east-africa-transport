"""Dissagregate OD matrix for air flows to node pairs

"""
import sys
import os

import pandas as pd
import geopandas as gpd
import fiona
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

    tonnage_column = "total_tonnage"
    all_ods = pd.read_csv(os.path.join(results_data_path,
                                        "flow_paths",
                                        "od_matrix_nodes.csv"))
    print (all_ods)

    print (all_ods.groupby(["origin_id","destination_id","iso3_O","iso3_D"])["total_tonnage"].sum().reset_index())

    results = all_ods.groupby(["origin_id", "destination_id"]).size()                                 
    print (results[results > 1])
    # assigned_flow_columns=['od_index','origin_id', 'destination_id', 'edge_path',
    #                 'gcost', tonnage_column]
    # network_df = create_multi_modal_network_africa(return_network=False)
    # # network_df[tonnage_column] = 0
    # # # network_df["capacity"] = 1e10
    # # # print (network_df[network_df["capacity"] <= 0])
    # # # print (min(network_df["capacity"]))
    # # all_ods = all_ods.sort_values(by=[tonnage_column],ascending=False,ignore_index=True)
    # # all_ods['od_index'] = all_ods.index.values.tolist()
    # # assigned_output_path = os.path.join(results_data_path,"flow_paths",
    # #                 'flow_paths_assignment_true.csv')
    # # unassigned_output_path = os.path.join(results_data_path,"flow_paths",
    # #                 'flow_paths_assignment_false.csv')
    # edge_flows_path = os.path.join(results_data_path,"flow_paths",
    #                 'edge_flows_capacity_constrained.csv')
    # # all_paths, no_paths, network_df = od_assignment_capacity_constrained(all_ods,network_df,
    # #                                                                     'edge_id',
    # #                                                                     'max_flow_cost',
    # #                                                                     tonnage_column,
    # #                                                                     'capacity',
    # #                                                                     assigned_flow_columns=assigned_flow_columns)

    # # del all_ods
    # # # all_paths['edge_path'] = all_paths.progress_apply(lambda x:str(x['edge_path']),axis=1)
    # # # all_paths = all_paths.groupby(['origin', 'destination', 'edge_path',
    # # #         'distance', 'time', 'gcost'])['max_tons'].sum().reset_index()
    # # # all_paths['od_index'] = all_paths.index.values.tolist()
    # # # # all_paths, edges_in = flow_assignment_elco(all_ods,edges_in,
    # # # #                         'max_gcost','max_time',
    # # # #                         'max_tons','capacity')
    # # all_paths.to_csv(assigned_output_path,index=False)
    # # no_paths.to_csv(unassigned_output_path,index=False)
    # # network_df.to_csv(edge_flows_path,index=False)

    # graph = create_multi_modal_network_africa()
    # all_ods = network_od_paths_assembly(all_ods, graph,
    #                             "max_flow_cost")
    # edge_tonnages = get_flow_on_edges(all_ods,"edge_id","edge_path",
    #                             "total_tonnage")

    # network_df = pd.merge(network_df,edge_tonnages,how="left",on=["edge_id"]).fillna(0)
    # network_df["over_capacity"] = network_df["capacity"] - network_df["total_tonnage"]
    # network_df.to_csv(edge_flows_path,index=False)
    # over_capacity_edges = network_df[network_df["over_capacity"] <= 0]["edge_id"].values.tolist()
    # edge_id_paths = get_flow_paths_indexes_of_edges(all_ods,"edge_path")
    # edge_paths_overcapacity = list(
    # 							set(
    # 								list(
    # 									chain.from_iterable([
    # 										path_idx for path_key,path_idx in edge_id_paths.items() if path_key in over_capacity_edges
    # 										]
    # 									)
    # 								)
    # 							)
    # 						)
    # over_capacity_ods = all_ods[all_ods.index.isin(edge_paths_overcapacity)]
    # print (all_ods)
    # print (over_capacity_ods) 



if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)