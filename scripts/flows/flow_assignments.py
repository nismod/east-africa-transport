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

    assigned_output_path = os.path.join(results_data_path,"flow_paths",
                    'flow_paths_assignment_true.csv')
    unassigned_output_path = os.path.join(results_data_path,"flow_paths",
                    'flow_paths_assignment_false.csv')
    edge_flows_path = os.path.join(results_data_path,"flow_paths",
                    'edge_flows_capacity_constrained.csv')
    
    tonnage_column = "total_tonnage"
    cost_column = "max_flow_cost"
    ods_df = pd.read_csv(os.path.join(results_data_path,
                                        "flow_paths",
                                        "od_matrix_nodes.csv"))
    all_ods = ods_df[["origin_id","destination_id",tonnage_column]]
    network_df = create_multi_modal_network_africa(return_network=False)
    net_df = network_df.copy()
    net_df["over_capacity"] = -1.0*net_df["capacity"]
    net_df[tonnage_column] = 0
    capacity_ods = []
    unassigned_paths = []
    itr = 0
    # while len(net_df[net_df["over_capacity"] < -1.0e-3].index) > 0:
    while len(all_ods.index) > 0 and itr < 5:
        itr+= 1
        graph = ig.Graph.TupleList(
                        net_df[
                        ~((net_df["over_capacity"] > -1.0e-3) & (net_df["over_capacity"] < 1e-3))
                        ].itertuples(index=False), 
                        edge_attrs=list(
                            net_df[
                                ~((net_df["over_capacity"] > -1.0e-3) & (net_df["over_capacity"] < 1e-3))
                            ].columns)[2:])
        graph_nodes = [x['name'] for x in graph.vs]
        unassigned_paths.append(all_ods[~((all_ods["origin_id"].isin(graph_nodes)) & (all_ods["destination_id"].isin(graph_nodes)))])
        all_ods = all_ods[(all_ods["origin_id"].isin(graph_nodes)) & (all_ods["destination_id"].isin(graph_nodes))]
        if len(all_ods.index) > 0:
            all_ods = network_od_paths_assembly(all_ods,graph,cost_column)
            unassigned_paths.append(all_ods[all_ods["edge_path"].astype(str) == '[]'])
            
            all_ods = all_ods[all_ods["edge_path"].astype(str) != '[]']
            if len(all_ods.index) > 0:
                edge_tonnages = get_flow_on_edges(all_ods,"edge_id","edge_path",tonnage_column)
                edge_tonnages.rename(columns={tonnage_column:"added_tonnage"},inplace=True)
                net_df = pd.merge(net_df,edge_tonnages,how="left",on=["edge_id"]).fillna(0)
                net_df[tonnage_column] += net_df["added_tonnage"]
                net_df["over_capacity"] = net_df["capacity"] - net_df[tonnage_column]
                net_df.drop("added_tonnage",axis=1,inplace=True)
                over_capacity_edges = net_df[net_df["over_capacity"] < -1.0e-3]["edge_id"].values.tolist()
                # del net_df
                if len(over_capacity_edges) > 0:
                    edge_id_paths = get_flow_paths_indexes_of_edges(all_ods,"edge_path")
                    edge_paths_overcapacity = list(
                                                set(
                                                    list(
                                                        chain.from_iterable([
                                                            path_idx for path_key,path_idx in edge_id_paths.items() if path_key in over_capacity_edges
                                                            ]
                                                        )
                                                    )
                                                )
                                            )
                    capacity_ods.append(all_ods[~all_ods.index.isin(edge_paths_overcapacity)])

                    over_capacity_ods = all_ods[all_ods.index.isin(edge_paths_overcapacity)]
                    over_capacity_ods["path_indexes"] = over_capacity_ods.index.values.tolist()
                    

                    over_capacity_edges_df = pd.DataFrame([
                                                (
                                                    path_key,path_idx
                                                ) for path_key,path_idx in edge_id_paths.items() if path_key in over_capacity_edges
                                            ],columns = ["edge_id","path_indexes"]
                                                )
                    over_capacity_edges_df = pd.merge(over_capacity_edges_df,
                                                net_df[["edge_id","capacity",tonnage_column]],
                                                how="left",
                                                on=["edge_id"])
                    over_capacity_edges_df["edge_path_flow"] = over_capacity_edges_df.progress_apply(
                                                        lambda x:over_capacity_ods[
                                                            over_capacity_ods.path_indexes.isin(x.path_indexes)
                                                            ][tonnage_column].values,
                                                        axis=1
                                                        )
                    over_capacity_edges_df["edge_path_flow_cor"] = over_capacity_edges_df.progress_apply(
                                                        lambda x:list(
                                                            1.0*x.capacity*x.edge_path_flow/x[tonnage_column]),
                                                        axis=1
                                                        )
                    over_capacity_edges_df["path_flow_tuples"] = over_capacity_edges_df.progress_apply(
                                                        lambda x:list(zip(x.path_indexes,x.edge_path_flow_cor)),axis=1)

                    min_flows = []
                    for r in over_capacity_edges_df.itertuples():
                        min_flows += r.path_flow_tuples

                    min_flows = pd.DataFrame(min_flows,columns=["path_indexes","min_flows"])
                    min_flows = min_flows.sort_values(by=["min_flows"],ascending=True)
                    min_flows = min_flows.drop_duplicates(subset=["path_indexes"],keep="first")

                    over_capacity_ods = pd.merge(over_capacity_ods,min_flows,how="left",on=["path_indexes"])
                    del min_flows, over_capacity_edges_df
                    over_capacity_ods["residual_tonnage"] = over_capacity_ods[tonnage_column] - over_capacity_ods["min_flows"]

                    cap_ods = over_capacity_ods.copy() 
                    cap_ods.drop(["path_indexes",tonnage_column,"residual_tonnage"],axis=1,inplace=True)
                    cap_ods.rename(columns={"min_flows":"total_tonnage"},inplace=True)
                    capacity_ods.append(cap_ods)
                    del cap_ods

                    over_capacity_ods.drop(["path_indexes","edge_path","gcost",tonnage_column,"min_flows"],axis=1,inplace=True)
                    over_capacity_ods.rename(columns={"residual_tonnage":tonnage_column},inplace=True)
                    all_ods = over_capacity_ods.copy()

                    
                    cap_ods = pd.concat(capacity_ods,axis=0,ignore_index=True)
                    edge_tonnages = get_flow_on_edges(cap_ods,"edge_id","edge_path",tonnage_column)
                    net_df = pd.merge(network_df.copy(),edge_tonnages,how="left",on=["edge_id"]).fillna(0)
                    net_df["over_capacity"] = net_df["capacity"] - net_df[tonnage_column]
                    del cap_ods

                    # net_df.to_csv(edge_flows_path,index=False)
                    # capacity_edges = net_df[net_df["over_capacity"] < 1e-3]["edge_id"].values.tolist()
                    # over_capacity_ods.drop(["edge_path","gcost","total_tonnage","min_flows"],axis=1,inplace=True)
                    # over_capacity_ods.rename(columns={"residual_tonnage":"total_tonnage"},inplace=True)
                    
                    # all_ods = over_capacity_ods.copy()
                    # net_df = network_df[~network_df["edge_id"].isin(capacity_edges)]
                    # graph = ig.Graph.TupleList(net_df.itertuples(index=False), 
                    #                         edge_attrs=list(net_df.columns)[2:])
                    # all_ods = network_od_paths_assembly(all_ods, graph,
                    #                             "max_flow_cost")
                    # capacity_ods.append(all_ods)

                    # cap_ods = pd.concat(capacity_ods,axis=0,ignore_index=True)
                    # edge_tonnages = get_flow_on_edges(cap_ods,"edge_id","edge_path",
                    #                             "total_tonnage")

                    # edge_flows_path = os.path.join(results_data_path,"flow_paths",
                    #                 'edge_flows_capacity_constrained_3.csv')
                    # net_df = pd.merge(network_df.copy(),edge_tonnages,how="left",on=["edge_id"]).fillna(0)
                    # net_df["over_capacity"] = net_df["capacity"] - net_df["total_tonnage"]
                    # net_df.to_csv(edge_flows_path,index=False)
                    # assigned_output_path = os.path.join(results_data_path,"flow_paths",
                    #                 'flow_paths_assignment_true_2.csv')
                    # cap_ods.to_csv(assigned_output_path,index=False)
                    # print (cap_ods)
                else:
                    capacity_ods.append(all_ods)
                    all_ods = pd.DataFrame()

    net_df.to_csv(edge_flows_path,index=False)
    if len(capacity_ods) > 0:
        capacity_ods = pd.concat(capacity_ods,axis=0,ignore_index=True)
        capacity_ods.to_csv(assigned_output_path,index=False)
        print (capacity_ods)

    if len(unassigned_paths) > 0:
        unassigned_paths = pd.concat(unassigned_paths,axis=0,ignore_index=True)
        unassigned_paths.to_csv(unassigned_output_path,index=False)
        print (unassigned_paths)

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)