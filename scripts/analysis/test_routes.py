"""Estimate direct damages to physical assets exposed to hazards

"""
import sys
import os

import pandas as pd
import geopandas as gpd
import numpy as np
import igraph as ig
import ast
from collections import defaultdict
from shapely.geometry import Point,LineString
from itertools import chain
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def get_flow_on_edges(save_paths_df,edge_id_column,edge_path_column,
    flow_column):
    """Write results to Shapefiles

    Outputs ``gdf_edges`` - a shapefile with minimum and maximum tonnage flows of all
    commodities/industries for each edge of network.

    Parameters
    ---------
    save_paths_df
        Pandas DataFrame of OD flow paths and their tonnages
    industry_columns
        List of string names of all OD commodities/industries indentified
    min_max_exist
        List of string names of commodity/industry columns for which min-max tonnage column names already exist
    gdf_edges
        GeoDataFrame of network edge set
    save_csv
        Boolean condition to tell code to save created edge csv file
    save_shapes
        Boolean condition to tell code to save created edge shapefile
    shape_output_path
        Path where the output shapefile will be stored
    csv_output_path
        Path where the output csv file will be stored

    """
    edge_flows = defaultdict(float)
    for row in save_paths_df.itertuples():
        for item in getattr(row,edge_path_column):
            edge_flows[item] += getattr(row,flow_column)

    return pd.DataFrame([(k,v) for k,v in edge_flows.items()],columns=[edge_id_column,flow_column])


def get_flow_paths_indexes_of_edges(flow_dataframe,path_criteria):
    # tqdm.pandas()
    # flow_dataframe[path_criteria] = flow_dataframe.progress_apply(lambda x:ast.literal_eval(x[path_criteria]),axis=1)
    edge_path_index = defaultdict(list)
    for k,v in zip(chain.from_iterable(flow_dataframe[path_criteria].ravel()), flow_dataframe.index.repeat(flow_dataframe[path_criteria].str.len()).tolist()):
        edge_path_index[k].append(v)

    del flow_dataframe
    return edge_path_index

def network_od_path_estimations(graph,
    source, target, cost_criteria):
    """Estimate the paths, distances, times, and costs for given OD pair

    Parameters
    ---------
    graph
        igraph network structure
    source
        String/Float/Integer name of Origin node ID
    source
        String/Float/Integer name of Destination node ID
    tonnage : float
        value of tonnage
    vehicle_weight : float
        unit weight of vehicle
    cost_criteria : str
        name of generalised cost criteria to be used: min_gcost or max_gcost
    time_criteria : str
        name of time criteria to be used: min_time or max_time
    fixed_cost : bool

    Returns
    -------
    edge_path_list : list[list]
        nested lists of Strings/Floats/Integers of edge ID's in routes
    path_dist_list : list[float]
        estimated distances of routes
    path_time_list : list[float]
        estimated times of routes
    path_gcost_list : list[float]
        estimated generalised costs of routes

    """
    paths = graph.get_shortest_paths(source, target, weights=cost_criteria, output="epath")


    edge_path_list = []
    path_gcost_list = []
    # for p in range(len(paths)):
    for path in paths:
        edge_path = []
        path_gcost = 0
        if path:
            for n in path:
                edge_path.append(graph.es[n]['edge_id'])
                path_gcost += graph.es[n][cost_criteria]

        edge_path_list.append(edge_path)
        path_gcost_list.append(path_gcost)

    
    return edge_path_list, path_gcost_list

def network_od_paths_assembly(points_dataframe, graph,
                                cost_criteria,tonnage_column):
    """Assemble estimates of OD paths, distances, times, costs and tonnages on networks

    Parameters
    ----------
    points_dataframe : pandas.DataFrame
        OD nodes and their tonnages
    graph
        igraph network structure
    region_name : str
        name of Province
    excel_writer
        Name of the excel writer to save Pandas dataframe to Excel file

    Returns
    -------
    save_paths_df : pandas.DataFrame
        - origin - String node ID of Origin
        - destination - String node ID of Destination
        - min_edge_path - List of string of edge ID's for paths with minimum generalised cost flows
        - max_edge_path - List of string of edge ID's for paths with maximum generalised cost flows
        - min_netrev - Float values of estimated netrevenue for paths with minimum generalised cost flows
        - max_netrev - Float values of estimated netrevenue for paths with maximum generalised cost flows
        - min_croptons - Float values of estimated crop tons for paths with minimum generalised cost flows
        - max_croptons - Float values of estimated crop tons for paths with maximum generalised cost flows
        - min_distance - Float values of estimated distance for paths with minimum generalised cost flows
        - max_distance - Float values of estimated distance for paths with maximum generalised cost flows
        - min_time - Float values of estimated time for paths with minimum generalised cost flows
        - max_time - Float values of estimated time for paths with maximum generalised cost flows
        - min_gcost - Float values of estimated generalised cost for paths with minimum generalised cost flows
        - max_gcost - Float values of estimated generalised cost for paths with maximum generalised cost flows

    """
    save_paths = []
    points_dataframe = points_dataframe.set_index('origin_id')
    origins = list(set(points_dataframe.index.values.tolist()))
    for origin in origins:
        try:
            destinations = points_dataframe.loc[[origin], 'destination_id'].values.tolist()

            get_path, get_gcost = network_od_path_estimations(
                graph, origin, destinations, cost_criteria)

            tons = points_dataframe.loc[[origin], tonnage_column].values
            save_paths += list(zip([origin]*len(destinations),
                                destinations, get_path,
                                list(tons*np.array(get_gcost))))

            print(f"done with {origin}")
        except:
            print(f"* no path between {origin}-{destinations}")
    cols = [
        'origin_id', 'destination_id', 'edge_path','gcost'
    ]
    save_paths_df = pd.DataFrame(save_paths, columns=cols)
    points_dataframe = points_dataframe.reset_index()
    save_paths_df = pd.merge(save_paths_df, points_dataframe, how='left', on=[
                             'origin_id', 'destination_id']).fillna(0)

    save_paths_df = save_paths_df[(save_paths_df[tonnage_column] > 0)
                                  & (save_paths_df['origin_id'] != 0)]

    return save_paths_df

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']                                    

    network_columns = ["from_node","to_node","edge_id","min_flow_cost","max_flow_cost","geometry"]
    road_edges = gpd.read_file(os.path.join(processed_data_path,"africa/networks",
                        "africa_roads_connected.gpkg"), layer='edges')[network_columns]
    road_edges["mode"] = "road"
    rail_edges = gpd.read_file(os.path.join(processed_data_path,
                        "africa/networks","africa_rails_modified.gpkg"),layer="edges")
    rail_edges = rail_edges[rail_edges["status"].isin(["open"])][network_columns]
    rail_edges["mode"] = "rail"
    port_edges = gpd.read_file(os.path.join(processed_data_path,
                        "africa/networks","ports_modified.gpkg"),layer="edges")[network_columns]
    port_edges["mode"] = "port"
    multi_modal_edges = gpd.read_file(os.path.join(processed_data_path,
                        "africa/networks","africa_multi_modal.gpkg"),layer="edges")[network_columns]
    multi_modal_edges["mode"] = "multi"
    edges = gpd.GeoDataFrame(pd.concat([road_edges,rail_edges,
                                    port_edges,multi_modal_edges],
                                    axis=0,ignore_index=True),
                            geometry="geometry",crs="EPSG:4326")
    network_columns = ["from_node","to_node","edge_id","mode","min_flow_cost","max_flow_cost"]
    network_edges = edges[network_columns]
    print (network_edges)
    cost_criteria = "min_flow_cost"
    cost_criteria = "max_flow_cost"
    G = ig.Graph.TupleList(network_edges.itertuples(index=False), edge_attrs=list(network_edges.columns)[2:])
    # source = "TZA_port_1"
    source = "KEN_port_17"
    target = "UGA_port_14"
    # target = "KEN_railn_105"
    # target = "KEN_roadn_3220"
    # target = "ZMB_railn_397"
    get_path, get_gcost_withrail = network_od_path_estimations(G,source, target, cost_criteria)
    print (get_path)
    print ("* Costs with rail",get_gcost_withrail)

    network_edges = network_edges[network_edges["mode"] !="rail"]
    # network_edges = network_edges[network_edges["mode"] !="road"]

    G = ig.Graph.TupleList(network_edges.itertuples(index=False), edge_attrs=list(network_edges.columns)[2:])
    get_path, get_gcostwithoutrail = network_od_path_estimations(G,source, target, cost_criteria)
    # print (get_path)
    print ("* Costs without rail",get_gcostwithoutrail)
    print ("* Cost difference",get_gcost_withrail[0] - get_gcostwithoutrail[0])

    


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)