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

def match_edges(edge_dataframe,buffer_dataframe,buffer_id,
                geom_buffer=10,fraction_intersection=0.95,length_intersected=100,save_buffer_file=False):
    # print (nwa_edges)
    buffer_dataframe['geometry'] = buffer_dataframe.geometry.progress_apply(lambda x: x.buffer(geom_buffer))
    
    # Save the result to sense check by visual inspection on QGIS. Not a necessary step 
    if save_buffer_file is not False:
        buffer_dataframe.to_file(save_buffer_file,layer=f'buffer_{geom_buffer}',driver='GPKG')

    edges_matches = gpd.sjoin(edge_dataframe,buffer_dataframe, how="inner", op='intersects').reset_index()
    if len(edges_matches.index) > 0:
        buffer_dataframe.rename(columns={'geometry':'buffer_geometry'},inplace=True)
        edges_matches = pd.merge(edges_matches,buffer_dataframe[[buffer_id,"buffer_geometry"]],how='left',on=[buffer_id])
        
        # Find the length intersected and its percentage as the length of the road segment and the NWA road segment
        edges_matches['length_intersected'] = edges_matches.progress_apply(
                                lambda x: (x.geometry.intersection(x.buffer_geometry).length),
                                axis=1)
        edges_matches['fraction_intersection'] = edges_matches.progress_apply(
                                lambda x: (x.geometry.intersection(x.buffer_geometry).length)/x.geometry.length if x.geometry.length > 0 else 1.0,
                                axis=1)
        edges_matches['fraction_buffer'] = edges_matches.progress_apply(
                                lambda x: (x.geometry.intersection(x.buffer_geometry).length)/x['buffer_length'] if x['buffer_length'] > 0 else 0.0,
                                axis=1)

        edges_matches.drop(['buffer_geometry'],axis=1,inplace=True)
        
        # Filter out the roads whose 95%(0.95) or over 100-meters length intersects with the buffer  
        # return edges_matches[
        #                 (edges_matches['fraction_intersection']>=fraction_intersection
        #                 ) | (edges_matches['length_intersected']>=length_intersected)]
        return edges_matches
    else:
        return pd.DataFrame()

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

def mean_min_max(dataframe,grouping_by_columns,grouped_columns):
    quantiles_list = ['mean','min','max']
    df_list = []
    for quant in quantiles_list:
        if quant == 'mean':
            # print (dataframe)
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].mean()
        elif quant == 'min':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].min()
        elif quant == 'max':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].max()

        df.rename(columns=dict((g,f'{quant}_{g}') for g in grouped_columns),inplace=True)
        df_list.append(df)
    return pd.concat(df_list,axis=1).reset_index()

def get_road_condition_material(x):
    if x.material in [r"^\s+$",'','nan','None','none']:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 'paved','asphalt'
        else:
            return 'unpaved','gravel'
    elif x.material == 'paved':
        return x.material, 'asphalt'
    elif x.material == 'unpaved':
        return x.material, 'gravel'
    elif x.material in ('asphalt','concrete'):
        return 'paved',x.material
    else:
        return 'unpaved',x.material

def get_road_width(x,width,shoulder):
    if x.lanes == 0:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 2.0*width + 2.0*shoulder
        else:
            return 1.0*width + 2.0*shoulder
    else:
        return float(x.lanes)*width + 2.0*shoulder

def get_road_lanes(x):
    if x.lanes == 0:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 2
        else:
            return 1
    else:
        return x.lanes

def assign_road_speeds(x):
    if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
        return x["Highway_min"],x["Highway_max"]
    elif x.road_cond == "unpaved":
        return x["Urban_min"],x["Urban_max"]
    else:
        return x["Rural_min"],x["Rural_max"]

def match_nodes_edges_to_countries(nodes,edges,countries,epsg=4326):
    old_nodes = nodes.copy()
    old_nodes.drop("geometry",axis=1,inplace=True)
    nodes_matches = gpd.sjoin(nodes[["node_id","geometry"]],
                                countries, 
                                how="left", op='within').reset_index()
    nodes_matches = nodes_matches[~nodes_matches["ISO_A3"].isna()]
    nodes_matches = nodes_matches[["node_id","ISO_A3","CONTINENT","geometry"]]
    nodes_matches.rename(columns={"ISO_A3":"iso_code"},inplace=True)
    nodes_matches = nodes_matches.drop_duplicates(subset=["node_id"],keep="first")
    
    nodes_unmatched = nodes[~nodes["node_id"].isin(nodes_matches["node_id"].values.tolist())]
    if len(nodes_unmatched.index) > 0:
        nodes_unmatched["iso_code"] = nodes_unmatched.progress_apply(
                                        lambda x:extract_gdf_values_containing_nodes(x,
                                                                countries,
                                                                "ISO_A3"),
                                        axis=1)
        nodes_unmatched["CONTINENT"] = nodes_unmatched.progress_apply(
                                        lambda x:extract_gdf_values_containing_nodes(x,
                                                                countries,
                                                                "CONTINENT"),
                                        axis=1)
        nodes = pd.concat([nodes_matches,nodes_unmatched],axis=0,ignore_index=True)
    else:
        nodes = nodes_matches.copy()
    del nodes_matches,nodes_unmatched
    nodes = pd.merge(nodes[["node_id","iso_code","CONTINENT","geometry"]],old_nodes,how="left",on=["node_id"])
    nodes["old_node_id"] = nodes["node_id"]
    nodes = gpd.GeoDataFrame(nodes,geometry="geometry",crs=f"EPSG:{epsg}")
    
    edges = pd.merge(edges,nodes[["node_id","iso_code","CONTINENT"]],how="left",left_on=["from_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"from_iso","CONTINENT":"from_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)
    edges = pd.merge(edges,nodes[["node_id","iso_code","CONTINENT"]],how="left",left_on=["to_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"to_iso","CONTINENT":"to_continent"},inplace=True)
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
    
    nodes = gpd.read_file(os.path.join(data_path,"ports","port.gpkg"),layer="nodes")
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
                                            "ne_10m_admin_0_countries",
                                            "ne_10m_admin_0_countries.shp"))[["ADM0_A3","ISO_A3","NAME","CONTINENT","geometry"]]
    global_country_info["ISO_A3"] = global_country_info.progress_apply(lambda x:correct_iso_code(x),axis=1)
    global_country_info = global_country_info.to_crs(epsg=4326)
    global_country_info = global_country_info[global_country_info["CONTINENT"].isin(["Africa"])]
    global_country_info = global_country_info.explode(ignore_index=True)
    global_country_info = global_country_info.sort_values(by="CONTINENT",ascending=True)
    # print (global_country_info)
    country_continent_codes = list(set(zip(
                                        global_country_info["ISO_A3"].values.tolist(),
                                        global_country_info["NAME"].values.tolist(),
                                        global_country_info["CONTINENT"].values.tolist()
                                        )
                                    )
                                )
    nodes, edges = match_nodes_edges_to_countries(nodes,edges,global_country_info)
    print (nodes)
    print (edges)

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
    # global_edges.rename(columns={"from_id":"from_node","to_id":"to_node"},inplace=True)
    # print (global_edges)

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

    africa_nodes.to_file(os.path.join(data_path,"africa/networks","africa_ports_modified.gpkg"),layer="nodes",driver="GPKG")
    africa_edges.to_file(os.path.join(data_path,"africa/networks","africa_ports_modified.gpkg"),layer="edges",driver="GPKG")


    nodes.to_file(os.path.join(data_path,"africa/networks","ports_modified.gpkg"),layer="nodes",driver="GPKG")
    edges.to_file(os.path.join(data_path,"africa/networks","ports_modified.gpkg"),layer="edges",driver="GPKG")

    """
    """

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
