""" Assign commodities to network nodes
"""

import os
import fiona
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import nearest_points
from scipy.spatial import Voronoi, cKDTree
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()
import datetime

def main(config):
    # Start timer
    tic = datetime.datetime.now()

    # Set paths
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    nodes_voronoi = gpd.read_file(
        os.path.join(data_path,"networks","road","road_voronoi_clipped.gpkg"),
        layer = "nodes-voronoi")

    # Add MINING data

    print("Start mining sector")

    mines = gpd.read_file(
    	os.path.join(incoming_data_path,"mining","global_mining","global_mining_polygons_v1.gpkg"))

    assign_weights_by_area_intersections(nodes_voronoi,mines,"node_id","AREA")

    nodes_voronoi.rename(columns={"AREA":"mining_area_km2"},inplace=True)

    layername = "mining"

    # Export voronoi polygons
    print("Ready to export")

    nodes_voronoi.to_file(os.path.join(data_path,"networks","road","road_voronoi_modified.gpkg"), 
        layer = layername,
        driver = "GPKG")

    # Merge back with nodes point network and save
    nodes_voronoi = gpd.read_file(
        os.path.join(data_path,"networks","road","road_voronoi_modified.gpkg"),
        layer = layername,
        ignore_geometry=True)

    nodes = gpd.read_file(
        os.path.join(data_path,"networks","road","road_modified.gpkg"),
        layer = "nodes")

    nodes = pd.merge(nodes,nodes_voronoi[["node_id","mining_area_km2"]], 
        how = "left", 
        on = ["node_id"]).fillna(0)

    nodes.to_file(os.path.join(data_path,"networks","road","road_modified.gpkg"), 
            layer = "nodes",
            driver = "GPKG")

    toc1 = datetime.datetime.now()


    # Add AGRICULTURE data

    print ("Start agriculture sector")

    nodes_voronoi = gpd.read_file(
        os.path.join(data_path,"networks","road","road_voronoi_clipped.gpkg"),
        layer = "nodes-voronoi")

    ag_points = pd.read_csv(
    	os.path.join(incoming_data_path,"agriculture","spam2017v2r1_ssa.csv","spam2017V2r1_SSA_P_TA.csv"), 
    	index_col=None)

    cols = ['whea_a','rice_a','maiz_a','barl_a','pmil_a','smil_a','sorg_a',
    		'ocer_a','pota_a','swpo_a','yams_a','cass_a','orts_a','bean_a',
    		'chic_a','cowp_a','pige_a','lent_a','opul_a','soyb_a','grou_a',
    		'cnut_a','oilp_a','sunf_a','rape_a','sesa_a','ooil_a','sugc_a',
    		'sugb_a','cott_a','ofib_a','acof_a','rcof_a','coco_a','teas_a',
    		'toba_a','bana_a','plnt_a','trof_a','temf_a','vege_a','rest_a']

    ag_points["total_mt"] = ag_points[cols].sum(axis = 1)

    ag_points["geometry"] = [Point(xy) for xy in zip(ag_points.x, ag_points.y)]

    ag_points = gpd.GeoDataFrame(ag_points[["iso3","unit","total_mt","geometry"]], 
    	crs="EPSG:4326", 
    	geometry="geometry")

    ag_points.to_file(os.path.join(data_path,"agriculture","agriculture.gpkg"), 
    	layer = 'agriculture',
    	driver = "GPKG")

    joined = gpd.sjoin(left_df=ag_points, right_df=nodes_voronoi, how='left')

    joined = joined.groupby(["node_id"])["total_mt"].sum().reset_index()

    nodes_voronoi = pd.merge(nodes_voronoi,joined,how="left",on=["node_id"]).fillna(0)

    nodes_voronoi.rename(columns={"total_mt":"ag_prod_mt"},inplace=True)

    layername = "agriculture"

    # Export voronoi polygons
    print("Ready to export")

    nodes_voronoi.to_file(os.path.join(data_path,"networks","road","road_voronoi_modified.gpkg"), 
        layer = layername,
        driver = "GPKG")

    # Merge back with nodes point network and save
    nodes_voronoi = gpd.read_file(
        os.path.join(data_path,"networks","road","road_voronoi_modified.gpkg"),
        layer = layername,
        ignore_geometry=True)

    nodes = gpd.read_file(
        os.path.join(data_path,"networks","road","road_modified.gpkg"),
        layer = "nodes")

    nodes = pd.merge(nodes,nodes_voronoi[["node_id","ag_prod_mt"]], 
        how = "left", 
        on = ["node_id"]).fillna(0)

    nodes.to_file(os.path.join(data_path,"networks","road","road_modified.gpkg"), 
            layer = "nodes",
            driver = "GPKG")

    toc2 = datetime.datetime.now()

    print("Duration mining: ")
    print(toc1 - tic)
    print("Duration agriculture: ")
    print(toc2 - toc1)


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
