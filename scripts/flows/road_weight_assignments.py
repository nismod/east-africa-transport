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

def find_areas_of_intersections(polygon_1,polygon_2,polygon_1_id,polygon_2_id,column_values_per_area=None):
    # Intersect two area dataframe and find the common area of intersection
    # Add up all the area of intersection to first area dataframe
    matches = gpd.sjoin(polygon_1,
                        polygon_2, 
                        how="inner", predicate='intersects').reset_index()
    matches.rename(columns={"geometry":"polygon_1_geometry"},inplace=True)
    matches = pd.merge(matches, 
                    polygon_2[[polygon_2_id,'geometry']],
                    how="left",on=[polygon_2_id])
    # print (matches)
    matches["areas_m2"] = matches.progress_apply(lambda x:x["polygon_1_geometry"].intersection(x["geometry"].buffer(0)).area,
                            axis=1)
    if column_values_per_area is not None:
        # matches[values_per_area] = matches["areas_m2"]*matches[column_values_per_area]
        matches[column_values_per_area] = matches[column_values_per_area].multiply(matches["areas_m2"],axis="index")
        return matches.groupby([polygon_1_id])[column_values_per_area].sum().reset_index()
    else:
        return matches.groupby([polygon_1_id])["areas_m2"].sum().reset_index()
    

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

    # print (road_pop_intersections)
    roads_voronoi = gpd.read_file(os.path.join(data_path,"networks","road","roads_voronoi.gpkg"),layer="areas")
    roads_voronoi = roads_voronoi.to_crs(epsg=3857)
    roads_voronoi = pd.merge(roads_voronoi,road_pop_intersections,how="left",on=[road_id_column]).fillna(0)
    print("* Done with estimating Worldpop population assinged to each voronoi area in road network")


    roads_voronoi = gpd.GeoDataFrame(roads_voronoi,geometry="geometry",crs="EPSG:3857")
    roads_iso_codes = list(set(roads_voronoi["iso_code"].values.tolist()))

    # Add MINING data

    print("* Start mining sector")
    mines = gpd.read_file(
        os.path.join(incoming_data_path,"mining","global_mining","global_mining_polygons_v1.gpkg"))
    # Extract only the mines for the countries with the road voronoi areas
    mines["mine_id"] = mines.index.values.tolist()   # Not sure if the mines layer has an ID column, so created one
    mines = mines[mines["ISO3_CODE"].isin(roads_iso_codes)]
    mines = mines.to_crs(epsg=3857)

    # Extract only the countries that have mines inorder to reduce the size of computation
    roads_reduced =  roads_voronoi[roads_voronoi["iso_code"].isin(list(set(mines["ISO3_CODE"].values.tolist())))] 

    roads_reduced = find_areas_of_intersections(roads_reduced,mines,road_id_column,"mine_id")
    roads_reduced.rename(columns={"areas_m2":"mining_area_m2"},inplace=True)

    del mines
    roads_voronoi = pd.merge(roads_voronoi,
                            roads_reduced[[road_id_column,"mining_area_m2"]],
                            how="left",on=[road_id_column]).fillna(0)
    roads_voronoi = gpd.GeoDataFrame(roads_voronoi,geometry="geometry",crs="EPSG:3857")
    print("* Done with mining sector")

    # Add AGRICULTURE data
    print("* Start agriculture sector")
    ag_points = gpd.read_file(os.path.join(data_path,"agriculture","agriculture.gpkg"), 
        layer = 'agriculture',
        driver = "GPKG")
    # Extract only the agriculture points for the countries with the road voronoi areas
    ag_points = ag_points[ag_points["iso3"].isin(roads_iso_codes)]
    ag_points = ag_points.to_crs(epsg=3857)
    joined = gpd.sjoin(left_df=ag_points, right_df=roads_voronoi, how='left')
    joined = joined.groupby([road_id_column])["total_mt"].sum().reset_index()
    del ag_points

    roads_voronoi = pd.merge(roads_voronoi,joined,how="left",on=[road_id_column]).fillna(0)
    roads_voronoi.rename(columns={"total_mt":"ag_prod_mt"},inplace=True)

    roads_voronoi = gpd.GeoDataFrame(roads_voronoi,geometry="geometry",crs="EPSG:3857")

    print("* Done with agriculture sector")

    """Add sector GDP fractions to areas for select HVT countries
        Assume that the GDP over an ADMIN 1 level is uniform over area
        Find area of ADMIN 1 levels intersecting with Road Voronoi areas
        Assign GDP over Road Voronoi area by summing all (Intersection Areas)*GDP/areas of ADMIN 1 areas intersectinng with it 
    """
    print("* Start with sector GDP assignments")
    sector_gdps = gpd.read_file(os.path.join(data_path,
                            "macroeconomic_data/weight_factors",
                            "admin_weighted.gpkg"),
                        layer="level1")
    sector_gdps = sector_gdps.to_crs(epsg=3857)
    gdp_assign = ["A","B","C","G"] # The sectors for which we want to disaggreagte GDP fraction values
    sector_gdps["gdp_areas_m2"] = sector_gdps.geometry.area
    roads_gdp = find_areas_of_intersections(roads_voronoi,
                                        sector_gdps,
                                        road_id_column,
                                        "GID_1",
                                        column_values_per_area=gdp_assign)
    
    roads_voronoi = pd.merge(roads_voronoi,
                            roads_gdp[[road_id_column] + gdp_assign],
                            how="left",on=[road_id_column]).fillna(0)
    roads_voronoi = gpd.GeoDataFrame(roads_voronoi,geometry="geometry",crs="EPSG:3857")
    roads_voronoi = roads_voronoi.to_crs(epsg=4326) # Do not need to do this, but still did it
    roads_voronoi.to_file(os.path.join(data_path,
                            "networks","road",
                            "roads_voronoi.gpkg"),
                        layer="weights",driver="GPKG")
    print (roads_voronoi)
    print("* Done with GDP sectors")




if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
