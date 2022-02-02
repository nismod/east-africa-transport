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

def get_wait_times(x):
    if x.from_mode == "port" or x.to_mode == "port":
        return 132.0
    elif x.from_mode == "rail" or x.to_mode == "rail":
        return 36.0
    else:
        return 12.0

def get_handling_charges(x):
    if x.from_mode == "port" or x.to_mode == "port":
        return 6,11
    else:
        return 6,8


def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    
    """
    """
    port_nodes = gpd.read_file(os.path.join(data_path,"africa/networks","ports_modified.gpkg"),layer="nodes")
    airport_nodes = gpd.read_file(os.path.join(data_path,"africa/networks","airports_modified.gpkg"),layer="nodes")
    rail_nodes = gpd.read_file(os.path.join(data_path,"africa/networks","africa_rails_modified.gpkg"),layer="nodes")
    rail_nodes = rail_nodes[~rail_nodes["facility"].isna()]
    road_nodes = gpd.read_file(os.path.join(data_path,"africa/networks","africa_roads_modified.gpkg"),layer="nodes")
    # road_nodes = road_nodes[road_nodes["iso_code"].isin(["KEN","TZA","UGA","ZMB"])]

    port_nodes = port_nodes.to_crs(epsg=4326)
    rail_nodes = rail_nodes.to_crs(epsg=4326)
    airport_nodes = airport_nodes.to_crs(epsg=4326)
    road_nodes = road_nodes.to_crs(epsg=4326)

    connecting_pairs = [(rail_nodes,port_nodes,"rail","port"),
                    (port_nodes,road_nodes,"port","road"),
                    (airport_nodes,road_nodes,"airport","road"),
                    (rail_nodes,road_nodes,"rail","road")]
    edges = []
    distance_threshold = 100.0
    for i, (df_0,df_2,from_mode,to_mode) in enumerate(connecting_pairs):
        df_1 = df_0.copy()
        df_1["from_node"] = df_1["node_id"]
        df_1["from_mode"] = from_mode
        df_1["to_mode"] = to_mode
        df_1["to_node"] = df_1.progress_apply(
                                    lambda x:get_nearest_values(x,
                                            df_2,
                                            "node_id"),
                                    axis=1)
        df_1["to_geometry"] = df_1.progress_apply(
                                    lambda x:get_nearest_values(x,
                                                            df_2,
                                                            "geometry"),
                                    axis=1)
        df_1.rename(columns={"geometry":"from_geometry"},inplace=True)
        df_1["distance"] = df_1.progress_apply(
                                        lambda x:distance.distance(
                                        (x.from_geometry.y,x.from_geometry.x),(x.to_geometry.y,x.to_geometry.x)
                                        ).km,
                                axis=1)
        df_1["geometry"] = df_1.progress_apply(lambda x: LineString([x.from_geometry,x.to_geometry]),axis=1)
        df_1 = df_1[df_1["distance"] <= distance_threshold]
        edges.append(df_1[["from_node","to_node","from_mode","to_mode","distance","geometry"]])

    edges = pd.concat(edges,axis=0,ignore_index=True)
    edges["edge_id"] = edges.index.values.tolist()
    edges["edge_id"] = edges.progress_apply(lambda x:f"multie_{x.edge_id}",axis=1)
    edges["wait_time"] = edges.progress_apply(lambda x:get_wait_times(x),axis=1)

    # edges = gpd.read_file(os.path.join(data_path,"africa/networks","africa_multi_modal.gpkg"),layer="edges")
    edges["handling_charges"] = edges.progress_apply(lambda x:get_handling_charges(x),axis=1)
    edges[["min_handling_costs","max_handling_costs"]] = edges["handling_charges"].apply(pd.Series)
    edges.drop("handling_charges",axis=1,inplace=True)
    wait_factor = 0.57/40.0
    uncertainty_factor = 0.45
    edges["min_flow_cost"] = wait_factor*(1 - uncertainty_factor)*edges["wait_time"] + edges["min_handling_costs"]
    edges["max_flow_cost"] = wait_factor*(1 + uncertainty_factor)*edges["wait_time"] + edges["max_handling_costs"]
    edges = gpd.GeoDataFrame(edges,geometry="geometry",crs="EPSG:4326")
    edges.to_file(os.path.join(data_path,"africa/networks","africa_multi_modal.gpkg"),layer="edges",driver="GPKG")



if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
