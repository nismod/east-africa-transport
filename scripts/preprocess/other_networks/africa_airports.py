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

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    
    nodes = pd.read_csv(os.path.join(data_path,"airports","airport_nodes.csv"))
    nodes["node_id"] = nodes.index.values.tolist()
    nodes["node_id"] = nodes.progress_apply(lambda x:f"{x.iso_code}_airport_{x.node_id}",axis=1)
    nodes["geometry"] = nodes.progress_apply(lambda x: Point(x.lon,x.lat),axis=1)
    nodes = gpd.GeoDataFrame(nodes,geometry="geometry",crs="EPSG:4326")
    print (nodes)

    nodes.to_file(os.path.join(data_path,"africa/networks","airports_modified.gpkg"),layer="nodes",driver="GPKG")

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
