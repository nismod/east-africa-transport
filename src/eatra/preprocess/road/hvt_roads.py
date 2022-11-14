#!/usr/bin/env python
# coding: utf-8
"""Process road data from OSM extracts and create road network topology 
"""

import os
import pandas as pd
import geopandas as gpd
import fiona
from .utils import *
from tqdm import tqdm
tqdm.pandas()

def main(config):

	data_path = config['paths']['data']

	admin = gpd.read_file(os.path.join(data_path,"admin_boundaries","gadm36_levels_gpkg","gadm36_levels_continents.gpkg"), layer = "level0")
	edges = gpd.read_file(os.path.join(data_path,"road/africa","africa-roads-modified.gpkg"), layer='edges')
	print ("Done reading files")

	countries = ["KEN","TZA","UGA","ZMB"]
	border_countires = ["RWA","BDI","ETH","SSD","SOM","COD","MWI","MOZ","ZWE","AGO","NAM","BWA","CAF"]
	eac_edges = edges[edges["from_iso"].isin(countries) | edges["to_iso"].isin(countries)]
	rest_edges = edges[~edges["edge_id"].isin(eac_edges["edge_id"].values.tolist())]
	border_edges = rest_edges[rest_edges["from_iso"].isin(border_countires) | rest_edges["to_iso"].isin(border_countires)]
	rest_edges = rest_edges[~rest_edges["edge_id"].isin(border_edges["edge_id"].values.tolist())]
	border_edges = border_edges[border_edges["highway"].isin(["trunk","motorway","primary","secondary"])]
	rest_edges = rest_edges[rest_edges["highway"].isin(["trunk","motorway","primary"])]
	hvt_edges = gpd.GeoDataFrame(pd.concat([eac_edges,border_edges,rest_edges],axis=0,ignore_index=True),geometry="geometry",crs="EPSG:4326")

	print ("Ready to export")
	hvt_edges.to_file(os.path.join(data_path,"road/africa","africa-roads-hvt.gpkg"), layer='edges', driver='GPKG')

	print ("Done with africa-roads-hvt.gpkg")

	hvt_countries = admin[admin["ISO_A3"].isin(countries)]
	hvt_edges = gpd.clip(eac_edges, hvt_countries)
	hvt_edges = hvt_edges.set_crs(epsg=4326)

	print ("Ready to export")
	hvt_edges.to_file(os.path.join(data_path,"road/africa","eastafrica-roads.gpkg"), layer='edges', driver='GPKG')

	print ("Done with eastafrica-roads.gpkg")

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)