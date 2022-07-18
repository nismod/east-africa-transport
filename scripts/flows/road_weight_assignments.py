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


    """Post-processing the road population intersection result
        The Worldpop raster layer gives the population-per-pixel (PPP) values
        Assuming each pixel is 1km2, the population denisty in PPP/m2 per pixel is PPP/1.0e6
        The population assigned to the Road Voronoi is (Intersection Area)*PPP/1.0e6
    """
    road_pop_column = "pop_2020" # Name of the Worldpop population column in geoparquet
    road_id_column = "node_id" # Road ID column
    # Read in intersection geoparquet
    road_pop_intersections = gpd.read_parquet(road_pop_intersections_path, 
                                "roads_voronoi_splits__pop_layer__areas.geoparquet")
    road_pop_intersections = road_pop_intersections.to_crs(epsg=3857)
    road_pop_intersections['pop_areas'] = road_pop_intersections.geometry.area
    road_pop_intersections.drop("geometry",axis=1,inplace=True)
    road_pop_intersections[road_pop_column] = road_pop_intersections['pop_areas']*road_pop_intersections[road_pop_column]/1.0e6
    road_pop_intersections = road_pop_intersections.groupby(road_id_column)[road_pop_column].sum().reset_index()

    print (road_pop_intersections)
    print("* Done with estimating Worldpop population assinged to each voronoi area in road network")



if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
