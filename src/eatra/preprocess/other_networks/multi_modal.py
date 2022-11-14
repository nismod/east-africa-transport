#!/usr/bin/env python
# coding: utf-8
"""Process road data from OSM extracts and create road network topology 
"""
import os
#from glob import glob
import json
import fiona
import geopandas as gpd
import pandas as pd
#import igraph as ig
from geopy import distance
import shapely.geometry
from shapely.geometry import Point,LineString
from boltons.iterutils import pairwise
from tqdm import tqdm
tqdm.pandas()
from .utils import *

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
    countries = ["KEN","TZA","UGA","ZMB"]
    border_countires = ["ETH","SSD","SOM","RWA","BDI","MWI","MOZ","COD","ZWE","AGO","NAM","BWA"]
    port_nodes = gpd.read_file(os.path.join(data_path,"networks","ports","port.gpkg"),layer="nodes")
    airport_nodes = gpd.read_file(os.path.join(data_path,"networks","airports","air.gpkg"),layer="nodes")
    rail_nodes = gpd.read_file(os.path.join(data_path,"networks","rail","rail.gpkg"),layer="nodes")
    rail_nodes = rail_nodes[~rail_nodes["facility"].isna()]
    road_nodes = gpd.read_file(os.path.join(data_path,"networks","road","roads.gpkg"),layer="nodes")
    road_nodes = road_nodes[road_nodes["iso_code"].isin(countries + border_countires)]

    port_nodes = port_nodes.to_crs(epsg=4326)
    rail_nodes = rail_nodes.to_crs(epsg=4326)
    airport_nodes = airport_nodes.to_crs(epsg=4326)
    road_nodes = road_nodes.to_crs(epsg=4326)

    connecting_pairs = [(rail_nodes,port_nodes,"rail","port"),
                    (port_nodes,road_nodes,"port","road"),
                    (airport_nodes,road_nodes,"airport","road"),
                    (rail_nodes[~rail_nodes["facility"].isna()],road_nodes,"rail","road")]

    edges = []
    distance_threshold = 20  # This is 20 km which is very big. Unfortunately we have to take such a big limit as the locations of assets are not exact
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


    # edges = gpd.GeoDataFrame(edges,geometry="geometry",crs="EPSG:4326")
    # edges.to_file(os.path.join(data_path,"networks","africa_multi_modal.gpkg"),layer="edges",driver="GPKG")

    edges["wait_time"] = edges.progress_apply(lambda x:get_wait_times(x),axis=1)
    edges["handling_charges"] = edges.progress_apply(lambda x:get_handling_charges(x),axis=1)
    edges[["min_handling_costs","max_handling_costs"]] = edges["handling_charges"].apply(pd.Series)
    edges.drop("handling_charges",axis=1,inplace=True)
    wait_factor = 0.57/40.0
    uncertainty_factor = 0.45
    edges["min_flow_cost"] = wait_factor*(1 - uncertainty_factor)*edges["wait_time"] + edges["min_handling_costs"]
    edges["max_flow_cost"] = wait_factor*(1 + uncertainty_factor)*edges["wait_time"] + edges["max_handling_costs"]
    edges = gpd.GeoDataFrame(edges,geometry="geometry",crs="EPSG:4326")
    edges.to_file(os.path.join(data_path,"networks","multimodal","multi_modal.gpkg"),layer="edges",driver="GPKG")

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
