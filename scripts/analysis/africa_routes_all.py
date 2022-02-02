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
    

    # country_boundaries = gpd.read_file(os.path.join(processed_data_path,
    #                                         "Admin_boundaries",
    #                                         "gadm36_levels_gpkg",
    #                                         "gadm36_levels_continents.gpkg"),
    #                         layer="level0")[["GID_0","NAME","CONTINENT","geometry"]]
    # country_boundaries = country_boundaries.to_crs(epsg=4326)
    # print (country_boundaries)

    # country_subadmin = gpd.read_file(os.path.join(processed_data_path,
    #                                         "Admin_boundaries",
    #                                         "gadm36_levels_gpkg",
    #                                         "gadm36_levels.gpkg"),
    #                         layer="level1")[["GID_1","GID_0","geometry"]]
    # country_subadmin = country_subadmin.to_crs(epsg=4326)
    # country_subadmin = pd.merge(country_subadmin,country_boundaries[["GID_0","CONTINENT"]],how="left",on=["GID_0"])
    # country_subadmin = country_subadmin[country_subadmin["CONTINENT"] == "Africa"]
    # print (country_subadmin)

    # pairs = []
    # country_subadmin["geometry"] = country_subadmin.progress_apply(lambda x:x.geometry.centroid,axis=1)
    # countries = list(set(country_subadmin["GID_0"].values.tolist()))
    # for i in range(len(countries)-1):
    #     from_country = countries[i]
    #     for to_country in countries[i+1:]:
    #         from_subadmin = country_subadmin[country_subadmin["GID_0"] == from_country]
    #         to_subadmin = country_subadmin[country_subadmin["GID_0"] == to_country]
    #         for from_row in from_subadmin.itertuples():
    #             for to_row in to_subadmin.itertuples():
    #                 pairs.append((from_row.GID_0,to_row.GID_0,
    #                             from_row.GID_1,to_row.GID_1,
    #                             LineString([from_row.geometry,to_row.geometry])))
    # pairs = gpd.GeoDataFrame(pd.DataFrame(pairs,
    #                         columns=["from_GID_0","to_GID_0","from_GID_1","to_GID_1","geometry"]),
    #                         geometry="geometry",crs="EPSG:4326")
    # pairs.to_file(os.path.join(processed_data_path,"africa/networks",
    #                     "africa_roads_connected.gpkg"), layer='od-pairs',driver="GPKG")
    # print (pairs)
    # country_boundaries = country_boundaries.explode(ignore_index=True)
    # country_boundaries = country_boundaries[country_boundaries["CONTINENT"] == "Africa"]
    # print (country_boundaries)
    # pair_matches = []
    # spatial_index = pairs.sindex
    # for c in country_boundaries.itertuples():
    #     possible_matches_index = list(spatial_index.intersection(c.geometry.bounds))
    #     possible_matches = pairs.iloc[possible_matches_index]
    #     possible_matches["GID_0"] = c.GID_0
    #     pair_matches.append(possible_matches[["from_GID_0","to_GID_0","GID_0"]])
    #     print ("* Done with",c.GID_0)

    # pair_matches = pd.concat(pair_matches,axis=0,ignore_index=True)   
    # # pair_matches = gpd.sjoin(pairs,country_boundaries[["GID_0","geometry"]],how="left", op='intersects').reset_index()
    # print (pair_matches) 

    # eac_countries = ["KEN","TZA","UGA","ZMB"]
    # pair_matches = pair_matches[pair_matches["GID_0"].isin(eac_countries)]
    # country_pairs = list(set(zip(pair_matches["from_GID_0"].values.tolist(),pair_matches["to_GID_0"].values.tolist())))
    # country_pairs += list(set(zip(pair_matches["to_GID_0"].values.tolist(),pair_matches["from_GID_0"].values.tolist())))
    # country_pairs = pd.DataFrame(country_pairs,columns=["iso3_O","iso3_D"])

    # trade_od = pd.read_csv(os.path.join(processed_data_path,"flow_od_data","africa_trade_2015_modified.csv"))
    # country_pairs = pd.merge(country_pairs,trade_od,how="left",on=["iso3_O","iso3_D"]).fillna(0)
    # country_pairs.to_csv(os.path.join(processed_data_path,"flow_od_data",
    #                     "africa_trade_2015_modified_eac.csv"), index=False)
    # print (country_pairs) 

    # country_pairs = country_pairs[country_pairs["q_land_predict"]/365.0 >= 10]
    # # country_pairs['check_string'] = country_pairs.apply(lambda row: ''.join(sorted([row['iso3_O'], row['iso3_D']])), axis=1)
    # # country_pairs.to_csv(os.path.join(processed_data_path,"africa/networks",
    # #                     "country_od_pairs.csv"), index=False)
    # # country_pairs = country_pairs.drop_duplicates('check_string',keep="first")
    # # print (country_pairs)

    # nodes = gpd.read_file(os.path.join(processed_data_path,"africa/networks",
    #                     "africa_roads_connected.gpkg"), layer='nodes-population')
    # nodes = nodes[nodes["population"] > 30000][["node_id","iso_code","population"]]
    # print (nodes)

    # od_pairs = []
    # for row in country_pairs.itertuples():
    #     origins = nodes[nodes["iso_code"] == row.iso3_O]
    #     origins["from_tonnage"] = (1.0*row.q_land_predict/365.0)*origins["population"]/origins["population"].sum()
    #     origins["from_value"] = (1.0*row.v_land_predict/365.0)*origins["population"]/origins["population"].sum()

    #     destinations = nodes[nodes["iso_code"] == row.iso3_D]
    #     destinations["weight"] = destinations["population"]/destinations["population"].sum()
    #     for o in origins.itertuples():
    #         for d in destinations.itertuples():
    #             od_pairs.append((o.node_id,d.node_id,o.iso_code,d.iso_code,o.from_tonnage*d.weight,o.from_value*d.weight))

    #     print (f"* Done with {row.iso3_O}-{row.iso3_D}")

    # od_pairs = pd.DataFrame(od_pairs,columns=["origin_id","destination_id","iso3_O","iso3_D","tonnage","value_usd"])
    # print (od_pairs)
    # od_pairs.to_csv(os.path.join(results_data_path,"flow_paths","all_roads_od_pairs.csv"), index=False)
    # od_pairs[od_pairs["tonnage"] >= 0.1].to_csv(os.path.join(results_data_path,
    #                                         "flow_paths",
    #                                         "all_roads_od_pairs_significant.csv"), index=False)

    # print (od_pairs[od_pairs["tonnage"] >= 0.1])

    # od_pairs = od_pairs[od_pairs["tonnage"] >= 0.1]

    # """Port assignments
    # """
    # od_pairs = []
    # road_nodes = gpd.read_file(os.path.join(processed_data_path,"africa/networks",
    #                     "africa_roads_connected.gpkg"), layer='nodes-population')
    # road_nodes = road_nodes[road_nodes["population"] > 30000][["node_id","iso_code","population"]]
    # port_nodes = gpd.read_file(os.path.join(processed_data_path,"africa/networks","ports_modified.gpkg"),layer="nodes")
    # rail_nodes = gpd.read_file(os.path.join(processed_data_path,"africa/networks","africa_rails_modified.gpkg"),layer="nodes")
    # rail_nodes = rail_nodes[~rail_nodes["facility"].isna()]
    # port_node_od = pd.read_csv(os.path.join(processed_data_path,
    #                         "flow_od_data",
    #                         "mombasa_dsm_2015_country_splits.csv"))
    # for row in port_node_od.itertuples():
    #     # iso_code = [i for i in [row.iso3_O,row.iso3_D]]
    #     if row.trade_type == "imports":
    #         iso_code = row.iso3_D
    #     else:
    #         iso_code = row.iso3_O
    #     if row.q_sea_predict_rail > 0:
    #         if iso_code in ["COD","UGA","BDI"]:
    #             od_nodes = port_nodes[port_nodes["iso_code"] == iso_code][["node_id"]]
    #         elif iso_code == "ZMB":
    #             od_nodes = rail_nodes[rail_nodes["iso_code"] == iso_code][["node_id"]]
    #         od_nodes["weight"] = 1.0/len(od_nodes.index)
    #         od_nodes["tonnage"] = (1.0*row.q_sea_predict_rail/365)*od_nodes["weight"]
    #         od_nodes["value_usd"] = (1.0*row.v_sea_predict_rail/365)*od_nodes["weight"]
    #     else:
    #         od_nodes = road_nodes[road_nodes["iso_code"] == iso_code][["node_id","population"]]
    #         od_nodes["weight"] = od_nodes["population"]/od_nodes["population"].sum()
    #         od_nodes["tonnage"] = (1.0*row.q_sea_predict_road/365)*od_nodes["weight"]
    #         od_nodes["value_usd"] = (1.0*row.v_sea_predict_road/365)*od_nodes["weight"]

    #     for od in od_nodes.itertuples():
    #         if row.trade_type == "imports":
    #             od_pairs.append((row.node_id,od.node_id,row.iso3_O,row.iso3_D,od.tonnage,od.value_usd))
    #         else:
    #             od_pairs.append((od.node_id,row.node_id,row.iso3_O,row.iso3_D,od.tonnage,od.value_usd))

    #     print (f"* Done with {row.iso3_O}-{row.iso3_D}")
    # od_pairs = pd.DataFrame(od_pairs,columns=["origin_id","destination_id","iso3_O","iso3_D","tonnage","value_usd"])
    # print (od_pairs)
    # od_pairs.to_csv(os.path.join(results_data_path,"flow_paths","all_port_od_pairs.csv"), index=False)

    """airport assignments
    """
    # od_pairs = []
    # road_nodes = gpd.read_file(os.path.join(processed_data_path,"africa/networks",
    #                     "africa_roads_connected.gpkg"), layer='nodes-population')
    # road_nodes = road_nodes[road_nodes["population"] > 30000][["node_id","iso_code","population"]]
    # port_node_od = pd.read_csv(os.path.join(processed_data_path,
    #                         "flow_od_data",
    #                         "airport_country_splits.csv"))
    # for row in port_node_od.itertuples():
    #     iso_code = row.iso3_O
    #     od_nodes = road_nodes[road_nodes["iso_code"] == iso_code][["node_id","population"]]
    #     od_nodes["weight"] = od_nodes["population"]/od_nodes["population"].sum()
    #     od_nodes["tonnage"] = (1.0*row.q_air_predict_road/365)*od_nodes["weight"]
    #     od_nodes["value_usd"] = (1.0*row.v_air_predict_road/365)*od_nodes["weight"]

    #     for od in od_nodes.itertuples():
    #         if row.trade_type == "imports":
    #             od_pairs.append((row.node_id,od.node_id,row.iso3_O,row.iso3_D,od.tonnage,od.value_usd))
    #         else:
    #             od_pairs.append((od.node_id,row.node_id,row.iso3_O,row.iso3_D,od.tonnage,od.value_usd))

    #     print (f"* Done with {row.iso3_O}-{row.iso3_D}")
    # od_pairs = pd.DataFrame(od_pairs,columns=["origin_id","destination_id","iso3_O","iso3_D","tonnage","value_usd"])
    # print (od_pairs)
    # od_pairs.to_csv(os.path.join(results_data_path,"flow_paths","all_airport_od_pairs.csv"), index=False)
    
    road_od_pairs = pd.read_csv(os.path.join(results_data_path,
                                            "flow_paths",
                                            "all_roads_od_pairs_significant.csv")) 
    port_od_pairs = pd.read_csv(os.path.join(results_data_path,
                                            "flow_paths",
                                            "all_port_od_pairs.csv"))
    port_od_pairs = port_od_pairs[port_od_pairs["tonnage"] >= 0.1]

    airport_od_pairs = pd.read_csv(os.path.join(results_data_path,
                                            "flow_paths",
                                            "all_airport_od_pairs.csv"))
    airport_od_pairs = airport_od_pairs[airport_od_pairs["tonnage"] >= 0.1]
    od_pairs = pd.concat([port_od_pairs,airport_od_pairs,road_od_pairs],axis=0,ignore_index=True)   
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
    G = ig.Graph.TupleList(network_edges.itertuples(index=False), edge_attrs=list(network_edges.columns)[2:])
    save_paths = []
    flow_paths = network_od_paths_assembly(od_pairs,G,
                                "max_flow_cost","tonnage")
    flow_paths.to_csv(os.path.join(results_data_path,"flow_paths","all_roads_paths_max_costs.csv"), index=False)

    # flow_paths = pd.read_csv(os.path.join(results_data_path,"flow_paths","all_roads_paths_max_costs.csv"))
    # flow_paths["edge_path"] = flow_paths.progress_apply(lambda x:ast.literal_eval(x['edge_path']),axis=1)
    
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