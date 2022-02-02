"""Estimate direct damages to physical assets exposed to hazards

"""
import sys
import os
import subprocess

from scipy.spatial import Voronoi
from shapely.geometry import Point, Polygon
import pandas as pd
import geopandas as gpd
import fiona
from shapely.geometry import shape, mapping
import numpy as np
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def extract_gdf_values_containing_nodes(x, input_gdf, column_name):
    a = input_gdf.loc[list(input_gdf.geometry.contains(x.geometry))]
    if len(a.index) > 0:
        return a[column_name].values[0]
    else:
        polygon_index = input_gdf.distance(x.geometry).sort_values().index[0]
        return input_gdf.loc[polygon_index,column_name]

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    # countries = gpd.read_file(os.path.join(data_path,
    #                                 "Admin_boundaries",
    #                                 "gadm36_levels_gpkg",
    #                                 "gadm36_levels_continents.gpkg"))[["GID_0","CONTINENT","geometry"]]
    # countries = countries.to_crs(epsg=4326)
    # countries = countries[countries["CONTINENT"].isin(["Africa"])]
    # countries = countries.explode(ignore_index=True)
    # print (countries)


    # # population_raster = os.path.join(data_path,"africa/Africa_1km_Population","AFR_PPP_2020_adj_v2.tif")
    # outCSVName = os.path.join(data_path,"africa/Africa_1km_Population", "population_points.csv")
    # # subprocess.run(["gdal2xyz.py", '-csv', population_raster, outCSVName])

    # # Load points and convert to geodataframe with coordinates
    # load_points = pd.read_csv(outCSVName, header=None, names=[
    #                           'x', 'y', 'population'], index_col=None)
    # load_points = load_points[load_points['population'] > 0]

    # load_points["geometry"] = [Point(xy) for xy in zip(load_points.x, load_points.y)]
    # # load_points = load_points.drop(['x', 'y'], axis=1)
    # population_points = gpd.GeoDataFrame(load_points, crs="EPSG:4326", geometry="geometry")
    # del load_points
    # print (population_points)

    # population_matches = gpd.sjoin(population_points,
    #                             countries, 
    #                             how="left", op='within').reset_index()
    # population_matches = population_matches[~population_matches["GID_0"].isna()]
    # population_matches.drop("geometry",axis=1,inplace=True)
    # outCSVName = os.path.join(data_path,"africa/Africa_1km_Population", "population_points_countries.csv")
    # population_matches.to_csv(outCSVName,index=False)
    # print (population_matches)

    # outCSVName = os.path.join(data_path,"africa/Africa_1km_Population", "population_points_countries.csv")
    # load_points = pd.read_csv(outCSVName)
    # load_points["geometry"] = [Point(xy) for xy in zip(load_points.x, load_points.y)]
    # population_points = gpd.GeoDataFrame(load_points, crs="EPSG:4326", geometry="geometry")
    # del load_points

    # countries = list(set(population_points["GID_0"].values.tolist()))
    # print (countries)
    # for country in countries:
    #     population_points[population_points["GID_0"] == country].to_file(os.path.join(data_path,
    #                                         "africa/Africa_1km_Population", 
    #                                         "population_points_countries.gpkg"),layer=country,driver="GPKG")
    #     population_points = population_points[population_points["GID_0"] != country]
    #     print ("* Done with",country)

    nodes = gpd.read_file(os.path.join(data_path,"africa/networks",
                                   "africa_roads_connected.gpkg"), layer='nodes')
    nodes = nodes.to_crs(epsg=4326)
    population_file = os.path.join(data_path,
                                "africa/Africa_1km_Population", 
                                "population_points_countries.gpkg")
    population_layers = fiona.listlayers(population_file)
    print (population_layers)
    assigned_population = []
    for layer in population_layers:
        population_points = gpd.read_file(population_file,layer=layer)
        population_points = population_points.to_crs(epsg=4326)
        country_nodes = nodes[nodes["iso_code"] == layer]
        if len(country_nodes.index) > 0:
            population_points = ckdnearest(population_points,country_nodes)
            population_points = population_points.groupby(["node_id"])["population"].sum().reset_index()
            # print (population_points)
            assigned_population.append(population_points)
        del population_points
        # if layer in ["KEN","TZA","UGA","ZMB"]:
        #     population_points = gpd.read_file(population_file,layer=layer)
        #     population_points = population_points.to_crs(epsg=4326)
        #     country_nodes = nodes[nodes["iso_code"] == layer].reset_index()
        #     country_nodes = drop_duplicate_geometries(country_nodes)
        #     country_voronoi = create_voronoi_polygons_from_nodes(country_nodes,"node_id")
        #     population_voronoi = create_voronoi_polygons_from_nodes(population_points,"population")
        #     population_points = assign_weights_by_area_intersections(country_voronoi,population_voronoi,"node_id","population")
        #     assigned_population.append(population_points.groupby(["node_id"])["population"].sum().reset_index())
        #     del country_nodes,country_voronoi, population_voronoi, population_points
        # else:
        #     population_points = ckdnearest(population_points,nodes[nodes["iso_code"] == layer])
        #     assigned_population.append(population_points.groupby(["node_id"])["population"].sum().reset_index())
        #     del population_points

        print ("* Done with",layer)

    assigned_population = pd.concat(assigned_population,axis=0,ignore_index=True)
    nodes = pd.merge(nodes,assigned_population,how="left",on=["node_id"]).fillna(0)

    nodes.to_file(os.path.join(data_path,"africa/networks",
                                   "africa_roads_connected.gpkg"), layer='nodes-population',driver="GPKG")

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)