""" Assign different weights to road nodes in Africa, including HVT countries
    These weights include:
        Population to whole of Africa 
        Mining areas to whole of Africa
        Sector specific GDP allocations to HVT countries only
"""

import os
import fiona
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import nearest_points
from scipy.spatial import Voronoi, cKDTree
import subprocess
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def main(config):
    # Set global paths
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    """We run the intersections of Road Voronoi polygons with the Worldpop 1-km raster grid layer
        This done by calling the script road_raster_intersections.py, which is adapted from:
            https://github.com/nismod/east-africa-transport/blob/main/scripts/exposure/split_networks.py
        The result of this script will give us a geoparquet file with population counts over geometries of Voronoi polygons   
    """

    road_details_csv = os.path.join(data_path,"road_layer.csv")
    population_details_csv = os.path.join(data_path,"pop_layer.csv")
    road_pop_intersections_path = os.path.join(data_path,"networks","road","road_raster_intersections")
    if os.path.exists(road_pop_intersections_path) == False:
        os.mkdir(road_pop_intersections_path)

    run_road_pop_intersections = False  # Set to True is you want to run this process
    # Did a run earlier and it takes ~ 224 minutes (nearly 4 hours) to run for the whole of Africa!
    # And generated a geoparquet with > 24 million rows! 
    if run_road_pop_intersections is True:
        args = [
                "python",
                "road_raster_intersections.py",
                f"{road_details_csv}",
                f"{population_details_csv}",
                f"{road_pop_intersections_path}"
                ]
        print ("* Start the processing of Roads voronoi and population raster intersections")
        print (args)
        subprocess.run(args)

    print ("* Done with the processing of Roads voronoi and population raster intersections")

    """Post-processing the road population intersection result
        The Worldpop raster layer gives the population-per-pixel (PPP) values
        Assuming each pixel is 1km2, the population denisty in PPP/m2 per pixel is PPP/1.0e6
        The population assigned to the Road Voronoi is (Intersection Area)*PPP/1.0e6
    """
    road_pop_column = "pop_2020" # Name of the Worldpop population column in geoparquet
    road_id_column = "node_id" # Road ID column
    # Read in intersection geoparquet
    road_pop_intersections = gpd.read_parquet(os.path.join(road_pop_intersections_path, 
                                "roads_voronoi_splits__pop_layer__areas.geoparquet"))
    road_pop_intersections = road_pop_intersections[road_pop_intersections[road_pop_column] > 0]
    road_pop_intersections = road_pop_intersections.to_crs(epsg=3857)
    road_pop_intersections['pop_areas'] = road_pop_intersections.geometry.area
    road_pop_intersections.drop("geometry",axis=1,inplace=True)
    road_pop_intersections[road_pop_column] = road_pop_intersections['pop_areas']*road_pop_intersections[road_pop_column]/1.0e6
    road_pop_intersections = road_pop_intersections.groupby(road_id_column)[road_pop_column].sum().reset_index()

    print (road_pop_intersections)
    roads_voronoi = gpd.read_file(os.path.join(data_path,"networks","road","roads_voronoi.gpkg"))
    roads_voronoi = pd.merge(roads_voronoi,road_pop_intersections,how="left",on=[road_id_column]).fillna(0)
    print("* Done with estimating Worldpop population assinged to each voronoi area in road network")

    # Add MINING data

    print("* Start mining sector")

    roads_voronoi = gpd.GeoDataFrame(roads_voronoi,geometry="geometry",crs="EPSG:3857")
    mines = gpd.read_file(
        os.path.join(incoming_data_path,"mining","global_mining","global_mining_polygons_v1.gpkg"))
    mines = mines.to_crs(epsg=3857)

    assign_weights_by_area_intersections(roads_voronoi,mines,road_id_column,"AREA")
    roads_voronoi.rename(columns={"AREA":"mining_area_m2"},inplace=True)

    print("* Done with mining sector")
    # Add AGRICULTURE data
    print("* Start agriculture sector")
    ag_points.to_file(os.path.join(data_path,"agriculture","agriculture.gpkg"), 
        layer = 'agriculture',
        driver = "GPKG")
    ag_points = ag_points.to_crs(epsg=3857)
    joined = gpd.sjoin(left_df=ag_points, right_df=roads_voronoi, how='left')
    joined = joined.groupby([road_id_column])["total_mt"].sum().reset_index()

    roads_voronoi = pd.merge(roads_voronoi,joined,how="left",on=[road_id_column]).fillna(0)
    roads_voronoi.rename(columns={"total_mt":"ag_prod_mt"},inplace=True)

    print("* Done with agriculture sector")

    print (roads_voronoi)


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
