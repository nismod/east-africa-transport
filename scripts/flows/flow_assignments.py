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
    # Assumption that all road link capacities in the future will increase by 10%,30%,50%
    road_capacity_factors = [None,0.1,0.3,0.5]
    # Assumption that all rail line capacities in the future will be at 30%, 50% and 80% of design capacity
    rail_capacity_factors = [None,0.3,0.5,0.8]
    baseline_od_year = 2015
    gdp_growth_rate = 5  # 4% growth rate assumed for the EAC region

    tonnage_column = "total_tonnage"
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
        all_ods = ods_df[["origin_id","destination_id",tonnage_column]]
        if t_eph == time_epochs[0]:
            rail_status = ["open"]
        else:
            rail_status = ["open","proposed","rehabilitation","construction"]

        network_df = create_multi_modal_network_africa(rail_status=rail_status,
                                                    road_future_usage=road_cf,
                                                    rail_future_usage=rail_cf,
                                                    return_network=False)
        net_df = network_df.copy()
        net_df[tonnage_column] = 0
        net_df["over_capacity"] = net_df["capacity"] - net_df[tonnage_column]
        net_df[tonnage_column] = 0
        capacity_ods = []
        unassigned_paths = []
        while len(all_ods.index) > 0:
            # graph = ig.Graph.TupleList(
            #                 net_df[
            #                 ~((net_df["over_capacity"] > -1.0e-3) & (net_df["over_capacity"] < 1e-3))
            #                 ].itertuples(index=False), 
            #                 edge_attrs=list(
            #                     net_df[
            #                         ~((net_df["over_capacity"] > -1.0e-3) & (net_df["over_capacity"] < 1e-3))
            #                     ].columns)[2:])
            graph = ig.Graph.TupleList(net_df[net_df["over_capacity"] > 1e-3].itertuples(index=False), 
                            edge_attrs=list(net_df[net_df["over_capacity"] > 1e-3].columns)[2:])
            graph_nodes = [x['name'] for x in graph.vs]
            unassigned_paths.append(all_ods[~((all_ods["origin_id"].isin(graph_nodes)) & (all_ods["destination_id"].isin(graph_nodes)))])
            all_ods = all_ods[(all_ods["origin_id"].isin(graph_nodes)) & (all_ods["destination_id"].isin(graph_nodes))]
            if len(all_ods.index) > 0:
                all_ods = network_od_paths_assembly(all_ods,graph,cost_column)
                unassigned_paths.append(all_ods[all_ods["edge_path"].astype(str) == '[]'])
                
                all_ods = all_ods[all_ods["edge_path"].astype(str) != '[]']
                if len(all_ods.index) > 0:
                    print (all_ods)
                    edge_tonnages = get_flow_on_edges(all_ods,"edge_id","edge_path",tonnage_column)
                    edge_tonnages.rename(columns={tonnage_column:"added_tonnage"},inplace=True)
                    net_df = pd.merge(net_df,edge_tonnages,how="left",on=["edge_id"]).fillna(0)
                    net_df["residual_capacity"] = net_df["over_capacity"]
                    net_df[tonnage_column] += net_df["added_tonnage"]
                    net_df["over_capacity"] = net_df["capacity"] - net_df[tonnage_column]
                    over_capacity_edges = net_df[net_df["over_capacity"] < -1.0e-3]["edge_id"].values.tolist()
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
                                                    net_df[["edge_id","residual_capacity","added_tonnage"]],
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
                                                                1.0*x.residual_capacity*x.edge_path_flow/x.added_tonnage),
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
                    else:
                        capacity_ods.append(all_ods)
                        net_df.drop(["residual_capacity","added_tonnage"],axis=1,inplace=True)
                        all_ods = pd.DataFrame()

        if len(capacity_ods) > 0:
            capacity_ods = pd.concat(capacity_ods,axis=0,ignore_index=True)
            capacity_ods.rename(columns={tonnage_column:"assigned_tonnage"},inplace=True)
            capacity_ods = pd.merge(capacity_ods,ods_df,how="left",on=["origin_id","destination_id"])
            capacity_ods[ods_values_columns] = capacity_ods[ods_values_columns].multiply(
                                                capacity_ods["assigned_tonnage"]/capacity_ods[tonnage_column],
                                                axis="index")
            capacity_ods.drop("assigned_tonnage",axis=1,inplace=True)
            # print (capacity_ods)

            net_df = network_df.copy()
            for c in ods_values_columns:
                edge_tonnages = get_flow_on_edges(capacity_ods,"edge_id","edge_path",c)
                net_df = pd.merge(net_df,edge_tonnages,how="left",on=["edge_id"]).fillna(0)
                del edge_tonnages

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