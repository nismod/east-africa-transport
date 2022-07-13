""" Assign flows of commodities using weighted nodes

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

def make_od_pairs(nodes, trade_od, weight_col, industry_code, min_value):
    nodes = nodes[nodes[weight_col] > min_value][["node_id","iso_code",weight_col]]
    trade_od = trade_od[trade_od["Industries"] == industry_code]
    
    od_pairs = []
    for row in trade_od.itertuples():
        origins = nodes[nodes["iso_code"] == row.iso3_O]
        origins["from_tonnage"] = (1.0*row.q_land_predict/365.0)*origins[weight_col]/origins[weight_col].sum()
        origins["from_value"] = (1.0*row.v_land_predict/365.0)*origins[weight_col]/origins[weight_col].sum()

        destinations = nodes[nodes["iso_code"] == row.iso3_D]
        destinations["weight"] = destinations[weight_col]/destinations[weight_col].sum()
        for o in origins.itertuples():
            for d in destinations.itertuples():
                od_pairs.append((o.node_id,d.node_id,o.iso_code,d.iso_code,row.Industries,o.from_tonnage*d.weight,o.from_value*d.weight))
    return od_pairs

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


def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']
    
    trade_od = pd.read_csv(os.path.join(data_path,"flow_od_data","africa_trade_2015_modified.csv"))

    # # HVT countries only
    # road_nodes = gpd.read_file(
    #     os.path.join(data_path,"networks","road","road_weighted.gpkg"),
    #     layer = "nodes")

    # # Entire African continent
    road_nodes = gpd.read_file(
        os.path.join(data_path,"networks","road","africa","afr_road_weighted.gpkg"),
        layer = "nodes")
    
    sector_attributes = pd.read_csv(
        os.path.join(data_path,"flow_od_data","sector_description.csv"),
        header=0,
        index_col=False)

    od_pairs = []
    for i in sector_attributes.itertuples():
        od_pairs_sector = make_od_pairs(road_nodes,trade_od,i.weight_col,i.industry_code,i.min_value)
        od_pairs.extend(od_pairs_sector)
        del od_pairs_sector
        
    od_pairs = pd.DataFrame(od_pairs,columns=["origin_id","destination_id","iso3_O","iso3_D","industry","tonnage","value_usd"]) 

    

    # Assign to edges

    road_od_pairs = pd.read_csv(os.path.join(results_data_path,
                                            "flow_paths",
                                            "road_od_pairs.csv")) 
    rail_od_pairs = pd.read_csv(os.path.join(results_data_path,
                                            "flow_paths",
                                            "rail_od_pairs.csv")) 
    port_od_pairs = pd.read_csv(os.path.join(results_data_path,
                                            "flow_paths",
                                            "port_od_pairs.csv"))
    airport_od_pairs = pd.read_csv(os.path.join(results_data_path,
                                            "flow_paths",
                                            "airport_od_pairs.csv"))

    od_pairs = pd.concat([road_od_pairs,rail_od_pairs,port_od_pairs,airport_od_pairs],axis=0,ignore_index=True)   
    print (od_pairs)                                      

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

    airport_edges = gpd.read_file(os.path.join(processed_data_path,"africa/networks",
                        "africa_airports_connected.gpkg"), layer='edges')[network_columns]
    airport_edges["mode"] = "road"
    
    multi_modal_edges = gpd.read_file(os.path.join(processed_data_path,
                        "africa/networks","africa_multi_modal.gpkg"),layer="edges")[network_columns]
    multi_modal_edges["mode"] = "multi"
    


    edges = gpd.GeoDataFrame(pd.concat([road_edges,rail_edges,
                                    port_edges,airport_edges,
                                    multi_modal_edges],
                                    axis=0,ignore_index=True),
                            geometry="geometry",crs="EPSG:4326")
    network_columns = ["from_node","to_node","edge_id","mode","min_flow_cost","max_flow_cost"]
    network_edges = edges[network_columns]
    print (network_edges)

    G = ig.Graph.TupleList(network_edges.itertuples(index=False), edge_attrs=list(network_edges.columns)[2:])
    
    save_paths = []
    flow_paths = network_od_paths_assembly(od_pairs,G,
                                "max_flow_cost","tonnage")
    flow_paths.to_csv(os.path.join(results_data_path,"flow_paths","all_flow_paths.csv"), index=False)

    edge_tonnages = get_flow_on_edges(flow_paths,"edge_id","edge_path",
                                                    "tonnage")
    edge_values = get_flow_on_edges(flow_paths,"edge_id","edge_path",
                                                    "value_usd")

    edge_flows = pd.merge(edge_tonnages,edge_values,how="left",on=["edge_id"]).fillna(0)
    del edge_tonnages,edge_values
    edges = pd.merge(edges,edge_flows,how="left",on=["edge_id"]).fillna(0)
    edges.to_file(os.path.join(results_data_path,
                                "flow_paths",
                                "network_flows.gpkg"), layer='edges',driver="GPKG")
if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)