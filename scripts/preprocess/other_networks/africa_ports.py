#!/usr/bin/env python
# coding: utf-8
"""Process road data from OSM extracts and create road network topology 
"""
import os
from glob import glob
import json
import fiona
import geopandas as gpd
import pandas as pd
import igraph as ig
from geopy import distance
import shapely.geometry
from shapely.geometry import Point,LineString
from boltons.iterutils import pairwise
from tqdm import tqdm
tqdm.pandas()
from utils import *

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
    for path in paths:
        edge_path = []
        if path:
            for n in path:
                edge_path.append(graph.es[n]['edge_id'])

        edge_path_list.append(edge_path)

    return edge_path_list

def line_length_km(line, ellipsoid='WGS-84'):
    """Length of a line in meters, given in geographic coordinates.

    Adapted from https://gis.stackexchange.com/questions/4022/looking-for-a-pythonic-way-to-calculate-the-length-of-a-wkt-linestring#answer-115285

    Args:
        line: a shapely LineString object with WGS-84 coordinates.

        ellipsoid: string name of an ellipsoid that `geopy` understands (see http://geopy.readthedocs.io/en/latest/#module-geopy.distance).

    Returns:
        Length of line in kilometers.
    """
    if line.geometryType() == 'MultiLineString':
        return sum(line_length_km(segment) for segment in line)

    return sum(
        distance.distance(tuple(reversed(a)), tuple(reversed(b)),ellipsoid=ellipsoid).km
        for a, b in pairwise(line.coords)
    )


def match_nodes_edges_to_countries(nodes,edges,countries,epsg=4326):
    old_nodes = nodes.copy()
    old_nodes.drop("geometry",axis=1,inplace=True)
    nodes_matches = gpd.sjoin(nodes[["node_id","geometry"]],
                                countries, 
                                how="left", predicate='within').reset_index()

    nodes_matches = nodes_matches[~nodes_matches["ISO_A3"].isna()]
    nodes_matches = nodes_matches[["node_id","ISO_A3","CONTINENT","geometry"]]
    nodes_matches.rename(columns={"ISO_A3":"iso_code","CONTINENT":"continent"},inplace=True)
    nodes_matches = nodes_matches.drop_duplicates(subset=["node_id"],keep="first")
    
    nodes_unmatched = nodes[~nodes["node_id"].isin(nodes_matches["node_id"].values.tolist())]
    if len(nodes_unmatched.index) > 0:
        nodes_unmatched = gpd.sjoin_nearest(nodes_unmatched[["node_id","geometry"]],
                                countries[["ISO_A3","CONTINENT","geometry"]], 
                                how="left").reset_index()
        #nodes_unmatched = nodes_unmatched[["node_id","ISO_A3","CONTINENT","geometry"]]
        nodes_unmatched.rename(columns={"ISO_A3":"iso_code","CONTINENT":"continent"},inplace=True)
        nodes_unmatched = nodes_unmatched.drop_duplicates(subset=["node_id"],keep="first")
        nodes = pd.concat([nodes_matches,nodes_unmatched],axis=0,ignore_index=True)
    else:
        nodes = nodes_matches.copy()
    
    del nodes_matches,nodes_unmatched
    nodes = pd.merge(nodes[["node_id","iso_code","continent","geometry"]],old_nodes,how="left",on=["node_id"])
    # nodes["old_node_id"] = nodes["node_id"]
    nodes = gpd.GeoDataFrame(nodes,geometry="geometry",crs=f"EPSG:{epsg}")
    
    edges = pd.merge(edges,nodes[["node_id","iso_code","continent"]],how="left",left_on=["from_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"from_iso","continent":"from_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)
    edges = pd.merge(edges,nodes[["node_id","iso_code","continent"]],how="left",left_on=["to_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"to_iso","continent":"to_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)

    nodes["node_id"] = nodes.progress_apply(lambda x:f"{x.iso_code}_{x.node_id}",axis=1)
    edges["from_node"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.from_node}",axis=1)
    edges["to_node"] = edges.progress_apply(lambda x:f"{x.to_iso}_{x.to_node}",axis=1)
    edges["old_edge_id"] = edges["edge_id"]
    edges["edge_id"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.to_iso}_{x.edge_id}",axis=1)
    
    return nodes, edges

def correct_wrong_assigning(x):
    to_node = "_".join(x.to_node.split("_")[1:])
    return f"{x.to_iso}_{to_node}"

def correct_iso_code(x):
    if str(x["ISO_A3"]) == "-99":
        return x["ADM0_A3"]
    else:
        return x["ISO_A3"]    

def match_country_code(x,country_codes):
    country = str(x["Country"]).strip().lower()
    match = [c[0] for c in country_codes if str(c[1]).strip().lower() == country]
    if match:
        return match[0]
    else:
        return "XYZ"

def clean_speeds(speed,speed_unit):
    if str(speed_unit).lower() == "mph":
        speed_factor = 1.61
    else:
        speed_factor = 1.0

    if str(speed).isdigit():
        return speed_factor*float(speed),speed_factor*float(speed)
    elif "-" in str(speed):
        return speed_factor*float(str(speed).split("-")[0].strip()),speed_factor*float(str(speed).split("-")[1].strip())
    else:
        return 0.0,0.0 

def add_country_code_to_costs(x,country_codes):
    country = str(x["Country"]).strip().lower()
    match = [c[0] for c in country_codes if str(c[1]).strip().lower() == country]
    if match:
        return match
    else:
        match = [c[0] for c in country_codes if str(c[1]).strip().lower() in country]
        if match:
            return match
        else:
            match = [c[0] for c in country_codes if str(c[2]).strip().lower() in country]
            if match:
                return match
            else:
                return ["XYZ"]

def add_tariff_min_max(x):
    tariff = x["Tariff"]
    if str(tariff).isdigit():
        return float(tariff),float(tariff)
    elif "-" in str(tariff):
        return float(str(tariff).split("-")[0].strip()),float(str(tariff).split("-")[1].strip())
    else:
        return 0.0,0.0 

def add_road_tariff_costs(x):
    if x.road_cond == "paved":
        return x.tariff_min, x.tariff_mean
    else:
        return x.tariff_mean, x.tariff_max

def convert_json_geopandas(df,epsg=4326):
    layer_dict = []    
    for key, value in df.items():
        if key == "features":
            for feature in value:
                if any(feature["geometry"]["coordinates"]):
                    d1 = {"geometry":shape(feature["geometry"])}
                    d1.update(feature["properties"])
                    layer_dict.append(d1)

    return gpd.GeoDataFrame(pd.DataFrame(layer_dict),geometry="geometry", crs=f"EPSG:{epsg}")

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    
    nodes = gpd.read_file(os.path.join(incoming_data_path,"ports","port.gpkg"),layer="nodes")
    nodes.rename(columns={"id":"node_id"},inplace=True)
    nodes["node_id"] = nodes.apply(lambda x:str(x.node_id).replace(f"\ufeff",''),axis=1)
    nodes = nodes.to_crs(epsg=4326)

    global_nodes = gpd.read_file(os.path.join(incoming_data_path,"ports/port_usage","nodes_maritime.gpkg"))
    global_nodes = global_nodes.to_crs(epsg=4326)
    add_port = global_nodes[global_nodes["id"] == "port568"]
    add_port["node_id"] = "port_19"
    add_port["name"] = add_port["name"].values[0].split("_")[0]
    add_port["country"] = "Kenya"
    add_port["location"] = "Indian Ocean"
    add_port["type"] = "Maritime"
    add_port["latitude"] = add_port.geometry.values[0].y
    add_port["longitude"] = add_port.geometry.values[0].x

    nodes = gpd.GeoDataFrame(pd.concat([nodes,
                        add_port[["node_id","name",
                                "country","location",
                                "type","longitude",
                                "latitude","geometry"]]],
                        axis=0,ignore_index=True),
                geometry="geometry",crs="EPSG:4326")
    
    edges = gpd.read_file(os.path.join(incoming_data_path,"ports/tanzania_port_study","tz_port_edges.shp"))
    edges.rename(columns={"edgeid":"edge_id"},inplace=True)
    edges = edges.to_crs(epsg=4326)

    """Find the countries of the nodes and assign them to the node ID's
        Accordingly modify the edge ID's as well
    """
    global_country_info = gpd.read_file(os.path.join(data_path,
        "Admin_boundaries",
        "gadm36_levels_gpkg",
        "gadm36_levels_continents.gpkg"))
    global_country_info = global_country_info.to_crs(epsg=3857)
    global_country_info = global_country_info.explode(ignore_index=True)
    global_country_info = global_country_info.sort_values(by="CONTINENT",ascending=True)

    # Set the crs
    edges = edges.to_crs(epsg=3857)
    nodes = nodes.to_crs(epsg=3857)
    nodes, edges = match_nodes_edges_to_countries(nodes,edges,global_country_info)
    print (nodes)
    print (edges)

    # Set the crs
    edges = edges.to_crs(epsg=4326)
    nodes = nodes.to_crs(epsg=4326)

    edges["min_speed"] = 18.0
    edges["max_speed"] = 22.0
    edges["length_km"] = edges.progress_apply(lambda x:line_length_km(x.geometry),axis=1)
    edges["min_tariff"] = 0.06
    edges["max_tariff"] = 0.07
    time_cost_factor = 0.49
    edges["min_flow_cost"] = time_cost_factor*edges["length_km"]/edges["max_speed"] + edges["min_tariff"]*edges["length_km"]
    edges["max_flow_cost"] = time_cost_factor*edges["length_km"]/edges["min_speed"] + edges["max_tariff"]*edges["length_km"]
    edges["flow_cost_unit"] = "USD/ton"

    # global_nodes.rename(columns={"id":"node_id"},inplace=True)
    global_nodes["node_id"] = global_nodes["id"]
    global_edges = gpd.read_file(os.path.join(incoming_data_path,"ports/port_usage","edges_maritime.gpkg"))
    global_edges["edge_id"] = global_edges.index.values.tolist()
    max_index = len(global_edges.index)+1
    global_edges["edge_id"] = global_edges.progress_apply(lambda x:f"port_route{x.edge_id}",axis=1)
    
    G = ig.Graph.TupleList(global_edges.itertuples(index=False), edge_attrs=list(global_edges.columns)[2:])
    # print (G)

    all_edges = []
    africa_nodes = global_nodes[global_nodes["Continent_Code"] == "AF"]["node_id"].values.tolist()
    for o in range(len(africa_nodes)-1):
        origin = africa_nodes[o]
        destinations = africa_nodes[o+1:]
        all_edges += network_od_path_estimations(G,origin,destinations,"distance")

    all_edges = list(set([item for sublist in all_edges for item in sublist]))
    africa_edges = global_edges[global_edges["edge_id"].isin(all_edges)]
    
    all_nodes = list(set(africa_edges["from_id"].values.tolist() + africa_edges["to_id"].values.tolist()))
    africa_nodes = global_nodes[global_nodes["node_id"].isin(all_nodes)]

    mapping_ports = [("KEN_port_18","port631"),("KEN_port_17","port757"),("TZA_port_3","port1264"),("TZA_port_1","port278")]
    for i,(new_port,old_port) in enumerate(mapping_ports):
        africa_nodes.loc[africa_nodes["id"] == old_port,"node_id"] = new_port

    africa_edges = pd.merge(africa_edges,africa_nodes[["id","node_id"]],how="left",left_on=["from_id"],right_on=["id"])
    africa_edges.rename(columns={"node_id":"from_node"},inplace=True)
    africa_edges.drop("id",axis=1,inplace=True)
    africa_edges = pd.merge(africa_edges,africa_nodes[["id","node_id"]],how="left",left_on=["to_id"],right_on=["id"])
    africa_edges.rename(columns={"node_id":"to_node"},inplace=True)
    africa_edges.drop("id",axis=1,inplace=True)

    new_edge = pd.DataFrame()
    new_edge["edge_id"] = [f"port_route{max_index}"] 
    new_edge["from_id"] = ["port_2"]
    new_edge["from_node"] = ["TZA_port_2"]
    new_edge["to_id"] = ["maritime670"]
    new_edge["to_node"] = ["maritime670"]
    new_edge["from_infra"] = ["port"]
    new_edge["to_infra"] = ["maritime"]
    new_edge["geometry"] = [LineString([nodes[nodes["node_id"] == "TZA_port_2"]["geometry"].values[0],
                                    africa_nodes[africa_nodes["id"] == "maritime670"]["geometry"].values[0]]
                                    )]
    new_edge['distance'] = new_edge.progress_apply(lambda x:line_length_km(x.geometry),axis=1)
    africa_edges = gpd.GeoDataFrame(pd.concat([africa_edges,new_edge],axis=0,ignore_index=True),geometry="geometry",crs="EPSG:4326")

    africa_nodes.to_file(os.path.join(data_path,"networks/ports","africa_ports.gpkg"),layer="nodes",driver="GPKG")
    africa_edges.to_file(os.path.join(data_path,"networks/ports","africa_ports.gpkg"),layer="edges",driver="GPKG")


    nodes.to_file(os.path.join(data_path,"networks/ports","port.gpkg"),layer="nodes",driver="GPKG")
    edges.to_file(os.path.join(data_path,"networks/ports","port.gpkg"),layer="edges",driver="GPKG")

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
