""" Assign population to network nodes
"""

import os
import fiona
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import nearest_points
from scipy.spatial import Voronoi, cKDTree
from .analysis_utils import *
from tqdm import tqdm
tqdm.pandas()
import datetime

def main(config):
    # Start timer
    tic = datetime.datetime.now()

    africa = True  # Set this 
    
    # Set global paths
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    # Set specific paths 
    if africa == True:
        path_nodes = os.path.join(data_path,"networks","road","africa","afr_road.gpkg")
        path_cluster = os.path.join(data_path,"population","clusters","afr-clusters.gpkg")
        path_worldpop = os.path.join(data_path,"population","worldpop","afr-worldpop.gpkg")
        outfile_nodes = os.path.join(data_path,"networks","road","africa","afr_road_weighted.gpkg")
        # outfile_polygons = os.path.join(data_path,"networks","road","africa","afr_road_voronoi.gpkg")
        outfile_polygons = os.path.join(data_path,"networks","road","africa","afr_road_voronoi_qgis.gpkg")
        outfile_polygons_weighted = os.path.join(data_path,"networks","road","africa","afr_road_voronoi_weighted.gpkg")
    else:
        path_nodes = os.path.join(data_path,"networks","road","road.gpkg")
        path_cluster = os.path.join(data_path,"population","clusters","hvt-clusters.gpkg")
        outfile_nodes = os.path.join(data_path,"networks","road","road_weighted.gpkg")
        outfile_polygons = os.path.join(data_path,"networks","road","road_voronoi.gpkg")
        outfile_polygons_weighted = os.path.join(data_path,"networks","road","road_voronoi_weighted.gpkg")


    # Read in network nodes
    nodes = gpd.read_file(path_nodes, layer = "nodes")

    print("Done reading network file")



    # ### Option 1: Finding the shortest distance between the centroid of population clusters and road nodes 
    # pop_clusters = gpd.read_file(path_cluster)
    
    # print("Done reading population file")

    # pop_clusters = pop_clusters.to_crs(3857)
    # nodes = nodes.to_crs(3857)

    # pop_clusters['centroid'] = pop_clusters.centroid
    # pop_clusters = pop_clusters.set_geometry("centroid")

    # print("Done preparing clusters")

    # pop_points = ckdnearest(pop_clusters,nodes)

    # print("Done finding nearest points")

    # pop_points = pop_points.groupby(["node_id"])["Population"].sum().reset_index()
    # pop_points.rename(columns={"Population":"population"},inplace=True)

    # nodes = pd.merge(nodes,pop_points, how = "left", on = ["node_id"]).fillna(0)

    # # Export network nodes
    # print("Ready to export")

    # nodes.to_file(os.path.join(outfile_nodes, 
    #     layer = nodes,
    #     driver = "GPKG")

    # toc1 = datetime.datetime.now()


    # ### Option 2: Intersecting with voronoi polygons of road nodes ...

    # nodes_voronoi = create_voronoi_polygons_from_nodes(nodes,"node_id")

    # print("Done creating voronoi polygons") 

    # ## Note: creating the voronoi polygons took 1.5 hrs for the hvt countries 

    # # Write file and read file for sanity check: 
    # nodes_voronoi.to_file(outfile_polygons, 
    #     layer = 'nodes-voronoi',
    #     driver = "GPKG")

    nodes_voronoi = gpd.read_file(
        outfile_polygons,
        layer = "nodes-voronoi")

    print("Done reading voronoi file")

    
    # # [HVT only] Clip polygons to admin edges
    # admin = gpd.read_file(
    #     os.path.join(data_path,"admin_boundaries","gadm36_levels_gpkg","gadm36_levels_continents.gpkg"), 
    #     layer = "level0")

    # hvt_countries = ["KEN","TZA","UGA","ZMB"]
    
    # hvt_admin = admin[admin["ISO_A3"].isin(hvt_countries)]

    # print ("Ready to begin clip")
    # nodes_voronoi_clipped = gpd.clip(nodes_voronoi, hvt_admin)

    # nodes_voronoi_clipped.to_file(os.path.join(data_path,"networks","road","road_voronoi_clipped.gpkg"), 
    #     layer = 'nodes-voronoi',
    #     driver = "GPKG")



    # # # Option 2a: ... with population cluster polygons
    # print("Starting option 2a: "+ str(datetime.datetime.now()))

    # # nodes_voronoi = gpd.read_file(
    # #     os.path.join(data_path,"networks","road","road_voronoi_clipped.gpkg"),
    # #     layer = "nodes-voronoi")

    # population = gpd.read_file(path_cluster)
    
    # print("Done reading files")

    # pop_points = assign_weights_by_area_intersections(nodes_voronoi,population,"node_id","Population")

    # nodes_voronoi.rename(columns={"Population":"population"},inplace=True)

    # nodes_voronoi["population_density"] =  nodes_voronoi["population"]/(nodes_voronoi["areas"]*1000)

    # layername = "pop_clusters"

    # # Export voronoi polygons
    # print("Ready to export")

    # nodes_voronoi.to_file(outfile_polygons_weighted, 
    #     layer = layername,
    #     driver = "GPKG")

    # # Merge back with nodes point network and save
    # nodes_voronoi = gpd.read_file(outfile_polygons_weighted,
    #     layer = layername,
    #     ignore_geometry=True)

    # nodes = gpd.read_file(outfile_nodes,
    #     layer = "nodes")

    # nodes = pd.merge(nodes,nodes_voronoi[["node_id","population","population_density"]], 
    #     how = "left", 
    #     on = ["node_id"]).fillna(0)

    # nodes.rename(columns={"population":"pop_clusters","population_density":"pop_density_clusters"},inplace=True)

    # nodes.to_file(outfile_nodes,
    #         layer = "nodes",
    #         driver = "GPKG")

    # toc2a = datetime.datetime.now()



    ### Option 2b: ... with worldpop raster file 
    print("Starting option 2b: "+ str(datetime.datetime.now()))

    # nodes_voronoi = gpd.read_file(outfile_polygons,
    #     layer = "nodes-voronoi")

    # # Read population raster and convert to csv
    # population_raster = os.path.join(incoming_data_path,"population/Africa_1km_Population","AFR_PPP_2020_adj_v2.tif")
    # outCSVName = os.path.join(data_path,"population","worldpop","population_points.csv")
    # subprocess.run(["gdal2xyz.py", '-csv', population_raster, outCSVName])

    # # Load points and convert to geodataframe with coordinates
    # load_points = pd.read_csv(outCSVName, header=None, names=[
    #                           'x', 'y', 'population'], index_col=None)
    # load_points = load_points[load_points['population'] > 0]

    # load_points["geometry"] = [Point(xy) for xy in zip(load_points.x, load_points.y)]
    # load_points = load_points.drop(['x', 'y'], axis=1)
    # population_points = gpd.GeoDataFrame(load_points, crs="EPSG:4326", geometry="geometry")
    # del load_points

    # population_points.to_file(os.path.join(data_path,"population","worldpop","afr-worldpop.gpkg"), 
    #     layer = 'population',
    #     driver = "GPKG")

    population_points = gpd.read_file(path_worldpop, 
        layer = "population")

    print("Done reading files")

    joined = gpd.sjoin(left_df=population_points, right_df=nodes_voronoi, how='left')
    
    joined = joined.groupby(["node_id"])["population"].sum().reset_index()

    nodes_voronoi = pd.merge(nodes_voronoi,joined,how="left",on=["node_id"]).fillna(0)

    nodes_voronoi["population_density"] =  nodes_voronoi["population"]/(nodes_voronoi["areas"]*1000)

    layername = "pop_worldpop"

    # Export voronoi polygons
    print("Ready to export")

    nodes_voronoi.to_file(outfile_polygons_weighted, 
        layer = layername,
        driver = "GPKG")

    # Merge back with nodes point network and save
    nodes_voronoi_simple = nodes_voronoi.drop(['geometry'], axis=1)

    # nodes_voronoi = gpd.read_file(outfile_polygons_weighted,
    #     layer = layername,
    #     ignore_geometry=True)

    # nodes = gpd.read_file(outfile_nodes,
    #     layer = "nodes")

    nodes = pd.merge(nodes,nodes_voronoi_simple[["node_id","population","population_density"]], 
        how = "left", 
        on = ["node_id"]).fillna(0)

    # nodes.rename(columns={"population":"pop_worldpop","population_density":"pop_density_worldpop"},inplace=True)

    nodes.to_file(outfile_nodes, 
            layer = "nodes",
            driver = "GPKG")

    toc2b = datetime.datetime.now()

    # print("Duration option 2a: ")
    # print(toc2a - tic)
    # print("Duration option 2b: ")
    # print(toc2b - toc2a)

    print(toc2b - tic)

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
