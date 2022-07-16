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
import numpy as np
import pandas as pd
from geopy import distance
from scipy.spatial import Voronoi
import shapely.geometry
from shapely.geometry import Polygon, shape, LineString
from pyproj import Geod
from tqdm import tqdm
tqdm.pandas()
from utils import *

from pyproj import Geod

def voronoi_finite_polygons_2d(vor, radius=None):
    """Reconstruct infinite voronoi regions in a 2D diagram to finite regions.

    Source: https://stackoverflow.com/questions/36063533/clipping-a-voronoi-diagram-python

    Parameters
    ----------
    vor : Voronoi
        Input diagram
    radius : float, optional
        Distance to 'points at infinity'

    Returns
    -------
    regions : list of tuples
        Indices of vertices in each revised Voronoi regions.
    vertices : list of tuples
        Coordinates for revised Voronoi vertices. Same as coordinates
        of input vertices, with 'points at infinity' appended to the
        end
    """
    if vor.points.shape[1] != 2:
        raise ValueError("Requires 2D input")

    new_regions = []
    new_vertices = vor.vertices.tolist()

    center = vor.points.mean(axis=0)
    if radius is None:
        radius = vor.points.ptp().max()*2

    # Construct a map containing all ridges for a given point
    all_ridges = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    # Reconstruct infinite regions
    for p1, region in enumerate(vor.point_region):
        vertices = vor.regions[region]

        if all(v >= 0 for v in vertices):
            # finite region
            new_regions.append(vertices)
            continue

        # reconstruct a non-finite region
        ridges = all_ridges[p1]
        new_region = [v for v in vertices if v >= 0]

        for p2, v1, v2 in ridges:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                # finite ridge: already in the region
                continue

            # Compute the missing endpoint of an infinite ridge

            t = vor.points[p2] - vor.points[p1]  # tangent
            t /= np.linalg.norm(t)
            n = np.array([-t[1], t[0]])  # normal

            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, n)) * n
            far_point = vor.vertices[v2] + direction * radius

            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())

        # sort region counterclockwise
        vs = np.asarray([new_vertices[v] for v in new_region])
        c = vs.mean(axis=0)
        angles = np.arctan2(vs[:, 1] - c[1], vs[:, 0] - c[0])
        new_region = np.array(new_region)[np.argsort(angles)]

        # finish
        new_regions.append(new_region.tolist())

    return new_regions, np.asarray(new_vertices)

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
        # Clipping polygon
        poly = Polygon(polygon).buffer(0)
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
    nodes = nodes[nodes["continent"] == "Africa"]
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
        print ("Starting with country", iso_code)
        country_nodes = nodes[nodes["iso_code"] == iso_code]
        country_boundary = global_country_info[global_country_info["ISO_A3"] == iso_code]
        print (country_nodes)
        country_voronoi = create_voronoi_layer(country_nodes,
                                    "node_id",epsg=3857)
        country_voronoi = gpd.clip(country_voronoi, country_boundary)
        africa_voronoi.append(country_voronoi)
        print ("Done with country", iso_code)

    africa_voronoi = gpd.GeoDataFrame(pd.concat(africa_voronoi,axis=0,ignore_index=True),
                    geometry="geometry",crs="EPSG:3857")
    africa_voronoi.to_crs(epsg=4326).to_file(os.path.join(data_path,
                        "networks/road","roads_voronoi.gpkg"),
                        layer="areas",driver="GPKG")


    
    


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
