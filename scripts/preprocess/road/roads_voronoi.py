#!/usr/bin/env python
# coding: utf-8
"""Process road data from OSM extracts and create road network topology 
"""
import os
from glob import glob

import sys
import os
import json
import fiona
import geopandas as gpd
import pandas as pd
from geopy import distance
from scipy.spatial import Voronoi
import shapely.geometry
from shapely.geometry import Point
from pyproj import Geod
from tqdm import tqdm
tqdm.pandas()
from utils import *

from pyproj import Geod

def create_voronoi_layer(nodes_dataframe,
                        node_id_column,epsg=4326,**kwargs):
    """Assign weights to nodes based on their nearest populations

        - By finding the population that intersect with the Voronoi extents of nodes

    Parameters
        - nodes_dataframe - Geodataframe of the nodes
        - population_dataframe - Geodataframe of the population
        - nodes_id_column - String name of node ID column
        - population_value_column - String name of column containing population values

    Outputs
        - nodes - Geopandas dataframe of nodes with new column called population
    """

    # load provinces and get geometry of the right population_dataframe
    
    # create Voronoi polygons for the nodes
    xy_list = []
    for iter_, values in nodes_dataframe.iterrows():
        xy = list(values.geometry.coords)
        xy_list += [list(xy[0])]

    vor = Voronoi(np.array(xy_list))
    regions, vertices = voronoi_finite_polygons_2d(vor)
    min_x = vor.min_bound[0] - 0.1
    max_x = vor.max_bound[0] + 0.1
    min_y = vor.min_bound[1] - 0.1
    max_y = vor.max_bound[1] + 0.1

    mins = np.tile((min_x, min_y), (vertices.shape[0], 1))
    bounded_vertices = np.max((vertices, mins), axis=0)
    maxs = np.tile((max_x, max_y), (vertices.shape[0], 1))
    bounded_vertices = np.min((bounded_vertices, maxs), axis=0)

    box = Polygon([[min_x, min_y], [min_x, max_y], [max_x, max_y], [max_x, min_y]])

    poly_list = []
    for region in regions:
        polygon = vertices[region]
        print (region)
        print (polygon)
        # Clipping polygon
        poly = Polygon(polygon)
        poly = poly.intersection(box)
        poly_list.append(poly)

    poly_index = list(np.arange(0, len(poly_list), 1))
    poly_df = pd.DataFrame(list(zip(poly_index, poly_list)),
                                   columns=['gid', 'geometry'])
    gdf_voronoi = gpd.GeoDataFrame(poly_df, geometry = 'geometry',crs=f'epsg:{epsg}')
    gdf_voronoi['area_m2'] = gdf_voronoi.geometry.area
    # gdf_voronoi[node_id_column] = gdf_voronoi.progress_apply(
    #     lambda x: extract_nodes_within_gdf(x, nodes_dataframe, node_id_column), axis=1)
    gdf_voronoi[node_id_column] = nodes_dataframe[node_id_column].values.tolist()
    if not kwargs.get('save',False):
        pass
    else:
        gdf_voronoi.to_file(kwargs.get('voronoi_path','voronoi-output.shp'))

    return gdf_voronoi

def main(config):
    data_path = config['paths']['data']
    scratch_path = config['paths']['scratch']

    nodes = gpd.read_file(os.path.join(data_path,"networks/road","roads.gpkg"), layer='nodes')
    nodes = nodes.to_crs(epsg=3857)
    iso_codes = list(set(nodes["iso_code"].values.tolist()))

    print("Done reading nodes")

    global_country_info = gpd.read_file(os.path.join(data_path,
                                                "Admin_boundaries",
                                                "gadm36_levels_gpkg",
                                                "gadm36_levels_continents.gpkg"))
    global_country_info = global_country_info[global_country_info["ISO_A3"].isin(iso_codes)]
    global_country_info = global_country_info.to_crs(epsg=3857)
    global_country_info = global_country_info.explode(ignore_index=True)

    africa_voronoi = []
    for iso_code in iso_codes:
        country_nodes = nodes[nodes["iso_code"] == iso_code]
        country_boundary = global_country_info[global_country_info["ISO_A3"] == iso_code]
        country_voronoi = create_voronoi_layer(country_nodes,
                                    "node_id",epsg=3857)
        country_voronoi = gpd.clip(country_voronoi, country_boundary)
        africa_voronoi.append(country_voronoi)
        print ("Done with country", iso_code)

    africa_voronoi = gpd.Geodataframe(pd.concat(africa_voronoi,axis=0,ignore_index=True),
                    geometry="geometry",crs="EPSG:3857")
    africa_voronoi.to_crs(epsg=4326).to_file(os.path.join(data_path,
                        "networks/road","roads_voronoi.gpkg"),
                        layer="areas",driver="GPKG")


    
    


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
