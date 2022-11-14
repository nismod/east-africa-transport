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
from .analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def flow_disruption_estimation(network_dataframe, edge_failure_set,
    flow_dataframe,edge_flow_path_indexes,edge_id_column,flow_column,cost_column):
    """Estimate network impacts of each failures
    When the tariff costs of each path are fixed by vehicle weight

    Parameters
    ---------
    network_df_in - Pandas DataFrame of network
    edge_failure_set - List of string edge ID's
    flow_dataframe - Pandas DataFrame of list of edge paths
    path_column - String name of column of edge paths in flow dataframe
    tons_column - String name of column of path tons in flow dataframe
    cost_column - String name of column of path costs in flow dataframe
    time_column - String name of column of path travel time in flow dataframe


    Returns
    -------
    edge_failure_dictionary : list[dict]
        With attributes
        edge_id - String name or list of failed edges
        origin - String node ID of Origin of disrupted OD flow
        destination - String node ID of Destination of disrupted OD flow
        no_access - Boolean 1 (no reroutng) or 0 (rerouting)
        new_cost - Float value of estimated cost of OD journey after disruption
        new_distance - Float value of estimated distance of OD journey after disruption
        new_path - List of string edge ID's of estimated new route of OD journey after disruption
        new_time - Float value of estimated time of OD journey after disruption
    """
    edge_path_index = get_path_indexes_for_edges(edge_flow_path_indexes,edge_failure_set)
    select_flows = flow_dataframe[flow_dataframe.index.isin(edge_path_index)]
    del edge_path_index

    """Find the flows in the disrupted edges 
    """
    affected_flows = get_flow_on_edges(select_flows,edge_id_column,"edge_path",flow_column)
    affected_flows.rename(columns={flow_column:"affected_flows"},inplace=True)
    # print (affected_flows)
    network_df_in = network_dataframe.copy()
    network_df_in = pd.merge(network_df_in,affected_flows,how='left',on=[edge_id_column])
    network_df_in['affected_flows'].fillna(0,inplace=True)
    network_df_in[flow_column] = network_df_in[flow_column] - network_df_in['affected_flows']
    network_df_in.drop('affected_flows',axis=1,inplace=True)
    del affected_flows

    affected_flows =  select_flows.copy()
    affected_flows.drop("edge_path",axis=1,inplace=True)
    affected_flows.rename(columns={"gcost":"old_cost"},inplace=True)
    reassinged_flows, no_flows = od_flow_allocation_capacity_constrained(affected_flows,
                                    network_df_in[~network_df_in[edge_id_column].isin(edge_failure_set)],
                                    flow_column,cost_column,store_edge_path=False)
    del network_df_in, affected_flows
    
    return reassinged_flows, no_flows

def main(config,year,failure_results,min_node_number,max_node_number):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    flow_column = "total_tonnage"
    flow_value_usd = "total_value_usd"
    cost_column = "max_flow_cost"
    od_columns = ["origin_id","destination_id","edge_path","gcost"]
    od_flows_file = os.path.join(results_data_path,"flow_paths",
                    f"flow_paths_assigned_{year}.parquet")
    edge_flows_file = os.path.join(results_data_path,"flow_paths",
                    f"edge_flows_capacity_constrained_{year}.csv")
    
    flow_df = pd.read_parquet(od_flows_file)
    flow_df['edge_path'] = flow_df.progress_apply(lambda x:ast.literal_eval(x['edge_path']),axis=1)
    network_df = pd.read_csv(edge_flows_file)
    ods_values_columns = [c for c in flow_df.columns.values.tolist() if c not in od_columns] 
    edge_path_idx = get_flow_paths_indexes_of_edges(flow_df,'edge_path')
    
    # Perform failure analysis
    # Generate a failure sample. We will update this later

    # Get the list of nodes of the initiating sector to fail
    damages_results_path = os.path.join(results_data_path,"risk_results_original","direct_damages_summary")

    rail_failure_edges = pd.read_csv(os.path.join(damages_results_path,"rail_edges_damages.csv"))
    road_failure_edges = pd.read_csv(os.path.join(damages_results_path,"road_edges_damages.csv"))

    all_failures = rail_failure_edges["edge_id"].values.tolist() + road_failure_edges["edge_id"].values.tolist()
    
    if max_node_number > len(all_failures):
        max_node_number = len(all_failures)
    #  Start the failure simiulations by looping over each failure scenario corresponding to an inidviual failed edge
    if min_node_number < len(all_failures):
        ef_list = []
        for nd in range(min_node_number,max_node_number):
            fail_edges = all_failures[nd]
            if isinstance(fail_edges,list) == False:
                fail_edges = [fail_edges]

            if network_df[network_df["edge_id"].isin(fail_edges)][flow_column].sum() > 0: 
                rerouted_flows, isolated_flows = flow_disruption_estimation(network_df,fail_edges,
                                                    flow_df,edge_path_idx,"edge_id",flow_column,
                                                    cost_column)

                rerouting_loss = 0
                isolation_loss = 0
                if len(rerouted_flows) > 0:
                    for rf in rerouted_flows:
                        rf["rerouting_loss"] = (rf["gcost"]  - rf["old_cost"])*rf[flow_column]
                        rerouting_loss += rf["rerouting_loss"].sum()
                if len(isolated_flows) > 0:
                    for is_fl in isolated_flows:
                        isolation_loss += is_fl[flow_value_usd].sum()
                
                del rerouted_flows, isolated_flows

                if len(fail_edges) == 1:
                    ef_list.append((fail_edges[0],rerouting_loss,isolation_loss,rerouting_loss + isolation_loss))
                else:
                    ef_list.append((fail_edges,rerouting_loss,isolation_loss,rerouting_loss + isolation_loss))
            else:
                if len(fail_edges) == 1:
                    ef_list.append((fail_edges[0],0,0,0))
                else:
                    ef_list.append((fail_edges,0,0,0))

            print (f"* Done with failure scenario {fail_edges}")

        ef_list = pd.DataFrame(ef_list,columns=["edge_id","rerouting_loss","isolation_loss","economic_loss"])
        ef_list.to_csv(os.path.join(failure_results,
                        f"flow_disruption_losses_{min_node_number}_{max_node_number}.csv"),index=False)

if __name__ == "__main__":
    CONFIG = load_config()
    try:
        year = sys.argv[1]
        failure_results = sys.argv[2]
        min_node_number = int(sys.argv[3])
        max_node_number = int(sys.argv[4])
    except IndexError:
        print("Got arguments", sys.argv)
        exit()
        
    main(CONFIG,year,failure_results,min_node_number, max_node_number)