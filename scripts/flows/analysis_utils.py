"""Functions for preprocessing data
"""
import sys
import os
import json

import pandas as pd
import geopandas as gpd
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, shape
from scipy.interpolate import interp1d
from collections import defaultdict
from itertools import chain
from scipy import integrate
from scipy.spatial import cKDTree
import igraph as ig
import fiona
import math
import numpy as np
from tqdm import tqdm
tqdm.pandas()

def load_config():
    """Read config.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    with open(config_path, "r") as config_fh:
        config = json.load(config_fh)
    return config


def gdf_geom_clip(gdf_in, clip_geom):
    """Filter a dataframe to contain only features within a clipping geometry

    Parameters
    ---------
    gdf_in
        geopandas dataframe to be clipped in
    province_geom
        shapely geometry of province for what we do the calculation

    Returns
    -------
    filtered dataframe
    """
    return gdf_in.loc[gdf_in['geometry'].apply(lambda x: x.within(clip_geom))].reset_index(drop=True)

def get_nearest_values(x,input_gdf,column_name):
    polygon_index = input_gdf.distance(x.geometry).sort_values().index[0]
    return input_gdf.loc[polygon_index,column_name]

def extract_gdf_values_containing_nodes(x, input_gdf, column_name):
    a = input_gdf.loc[list(input_gdf.geometry.contains(x.geometry))]
    if len(a.index) > 0:
        return a[column_name].values[0]
    else:
        polygon_index = input_gdf.distance(x.geometry).sort_values().index[0]
        return input_gdf.loc[polygon_index,column_name]

def nearest(geom, gdf):
    """Find the element of a GeoDataFrame nearest a shapely geometry
    """
    matches_idx = gdf.sindex.nearest(geom.bounds)
    nearest_geom = min(
        [gdf.iloc[match_idx] for match_idx in matches_idx],
        key=lambda match: geom.distance(match.geometry)
    )
    return nearest_geom

def get_nearest_node(x, sindex_input_nodes, input_nodes, id_column):
    """Get nearest node in a dataframe

    Parameters
    ----------
    x
        row of dataframe
    sindex_nodes
        spatial index of dataframe of nodes in the network
    nodes
        dataframe of nodes in the network
    id_column
        name of column of id of closest node

    Returns
    -------
    Nearest node to geometry of row
    """
    return input_nodes.loc[list(sindex_input_nodes.nearest(x.bounds[:2]))][id_column].values[0]


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

def assign_value_in_area_proportions(poly_1_gpd, poly_2_gpd, poly_attribute):
    poly_1_sindex = poly_1_gpd.sindex
    for p_2_index, polys_2 in poly_2_gpd.iterrows():
        poly2_attr = 0
        intersected_polys = poly_1_gpd.iloc[list(
            poly_1_sindex.intersection(polys_2.geometry.bounds))]
        for p_1_index, polys_1 in intersected_polys.iterrows():
            if (polys_2['geometry'].intersects(polys_1['geometry']) is True) and (polys_1.geometry.is_valid is True) and (polys_2.geometry.is_valid is True):
                poly2_attr += polys_1[poly_attribute]*polys_2['geometry'].intersection(
                    polys_1['geometry']).area/polys_1['geometry'].area

        poly_2_gpd.loc[p_2_index, poly_attribute] = poly2_attr

    return poly_2_gpd

def extract_nodes_within_gdf(x, input_nodes, column_name):
    a = input_nodes.loc[list(input_nodes.geometry.within(x.geometry))]
    # if len(a.index) > 1: # To check if there are multiple intersections
    #     print (x)
    if len(a.index) > 0:
        return a[column_name].values[0]
    else:
        return ''

def create_voronoi_polygons_from_nodes(nodes_dataframe,node_id_column,epsg=4326,**kwargs):
    # create Voronoi polygons for the nodes
    nodes_dataframe = nodes_dataframe.reset_index()
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
        poly = Polygon(polygon)
        poly = poly.intersection(box)
        poly_list.append(poly)

    poly_index = list(np.arange(0, len(poly_list), 1))
    poly_df = pd.DataFrame(list(zip(poly_index, poly_list)),
                                   columns=['gid', 'geometry'])
    gdf_voronoi = gpd.GeoDataFrame(poly_df, geometry = 'geometry',crs=f'epsg:{epsg}')
    gdf_voronoi['areas'] = gdf_voronoi.progress_apply(lambda x:x.geometry.area,axis=1)
    gdf_voronoi[node_id_column] = gdf_voronoi.progress_apply(
        lambda x: extract_nodes_within_gdf(x, nodes_dataframe, node_id_column), axis=1)
    if not kwargs.get('save',False):
        pass
    else:
        gdf_voronoi.to_file(kwargs.get('voronoi_path','voronoi-output.shp'))

    return gdf_voronoi

def assign_weights_by_area_intersections(gdf_voronoi,
                        population_dataframe,
                        node_id_column,population_value_column):
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
    sindex_population_dataframe = population_dataframe.sindex

    gdf_voronoi[population_value_column] = 0
    gdf_voronoi = assign_value_in_area_proportions(population_dataframe, gdf_voronoi, population_value_column)
    gdf_voronoi = gdf_voronoi[~(gdf_voronoi[node_id_column] == '')]

    return gdf_voronoi[[node_id_column, population_value_column]]
    

def spatial_scenario_selection(dataframe_1, 
                                dataframe_2, 
                                dataframe_1_columns, 
                                dataframe_2_columns,
                            ):
    """Intersect Polygons to collect attributes

    Parameters
        - dataframe_1 - First polygon dataframe
        - dataframe_2 - Second polygon dataframe
        - dataframe_1_columns - First polygon dataframe columns to collect
        - dataframe_2_columns - Second polygon dataframe columns to collect

    Outputs
        data_dictionary - Dictionary of intersection attributes:
    """

    intersection_dictionary = []

    # create spatial index
    dataframe_1_sindex = dataframe_1.sindex
    total_values = len(dataframe_2.index)
    for values in dataframe_2.itertuples():
        intersected_polys = dataframe_1.iloc[list(
            dataframe_1_sindex.intersection(values.geometry.bounds))]
        for intersected_values in intersected_polys.itertuples():
            if (
                intersected_values.geometry.intersects(values.geometry) is True
                ) and (
                    values.geometry.is_valid is True
                    ) and (
                        intersected_values.geometry.is_valid is True
                        ):
                dataframe_1_dictionary = dict([(v,getattr(intersected_values,v)) for v in dataframe_1_columns])
                dataframe_2_dictionary = dict([(v,getattr(values,v)) for v in dataframe_2_columns])
                geometry_dictionary = {"geometry":values.geometry.intersection(intersected_values.geometry)}

                intersection_dictionary.append({**dataframe_1_dictionary, **dataframe_2_dictionary,**geometry_dictionary})
        print (f"* Done with Index {values.Index} out of {total_values}")
    return intersection_dictionary

def ckdnearest(gdA, gdB):
    """Taken from https://gis.stackexchange.com/questions/222315/finding-nearest-point-in-other-geodataframe-using-geopandas
    """
    nA = np.array(list(gdA.geometry.apply(lambda x: (x.x, x.y))))
    nB = np.array(list(gdB.geometry.apply(lambda x: (x.x, x.y))))
    btree = cKDTree(nB)
    dist, idx = btree.query(nA, k=1)
    gdB_nearest = gdB.iloc[idx].drop(columns="geometry").reset_index(drop=True)
    gdf = pd.concat(
        [
            gdA.reset_index(drop=True),
            gdB_nearest,
            pd.Series(dist, name='dist')
        ], 
        axis=1)

    return gdf

def drop_duplicate_geometries(gdf, keep="first"):
    """Drop duplicate geometries from a dataframe"""
    # convert to wkb so drop_duplicates will work
    # discussed in https://github.com/geopandas/geopandas/issues/521
    mask = gdf.geometry.apply(lambda geom: geom.wkb)
    # use dropped duplicates index to drop from actual dataframe
    return gdf.iloc[mask.drop_duplicates(keep).index]

def split_multigeometry(dataframe,split_geometry_type="GeometryCollection"):
    """Create multiple geometries from any MultiGeomtery and GeometryCollection

    Ensures that edge geometries are all Points,LineStrings,Polygons, duplicates attributes over any
    created multi-geomteries.
    """
    simple_geom_attrs = []
    simple_geom_geoms = []
    for v in tqdm(dataframe.itertuples(index=False),
                     desc="split_multi",
                     total=len(dataframe)):
        if v.geometry.geom_type == split_geometry_type:
            geom_parts = list(v.geometry)
        else:
            geom_parts = [v.geometry]

        for part in geom_parts:
            simple_geom_geoms.append(part)

        attrs = gpd.GeoDataFrame([v] * len(geom_parts))
        simple_geom_attrs.append(attrs)

    simple_geom_geoms = gpd.GeoDataFrame(simple_geom_geoms, columns=["geometry"])
    dataframe = (pd.concat(simple_geom_attrs,
                           axis=0).reset_index(drop=True).drop("geometry",
                                                               axis=1))
    dataframe = pd.concat([dataframe, simple_geom_geoms], axis=1)

    return dataframe

def add_link_capacity(edges,road_future_usage=None,rail_future_usage=None,mode=None,capacity_upper_limit=1e10):
    if mode == "road":
        capacity_data = pd.read_csv(os.path.join(
                                        load_config()["paths"]["data"],
                                            "networks",
                                            "road",
                                            "roads_capacity_attributes.csv"))
        edges = pd.merge(edges,capacity_data[["highway",
                                        "lane_capacity_tons_per_day"]],
                            how="left",
                            on=["highway"])
        # No idea why some edges have lanes = 0
        edges["lanes"] = np.where(edges["lanes"] == 0,1,edges["lanes"])
        edges["capacity"] = edges["lanes"]*edges["lane_capacity_tons_per_day"]
        if road_future_usage is not None:
            edges["capacity"] = (1+road_future_usage)*edges["capacity"]

    elif mode == "rail":
        capacity_data = pd.read_csv(os.path.join(
                                        load_config()["paths"]["data"],
                                            "networks",
                                            "rail",
                                            "rail_capacity_attributes.csv"),encoding="latin1")
        edges = pd.merge(edges,capacity_data[["country","line","status","gauge",
                                        "design_capacity_tons_per_year",
                                        "usage_design_ratio"]],
                            how="left",
                            on=["country","line","status","gauge"])
        if rail_future_usage is not None:
            edges["capacity"] = 1.0/365*rail_future_usage*edges["design_capacity_tons_per_year"]
        else:
            edges["capacity"] = 1.0/365*edges["design_capacity_tons_per_year"]*edges["usage_design_ratio"]
    else:
        edges["capacity"] = capacity_upper_limit

    return edges

def create_multi_modal_network_africa(modes=["road","rail","port","multi"],
                                rail_status=["open"],
                                road_future_usage=None,
                                rail_future_usage=None,
                                return_network=True):
    network_columns = ["from_node","to_node","edge_id","min_flow_cost","max_flow_cost","capacity"]
    road_edges = gpd.read_file(os.path.join(
                        load_config()["paths"]["data"],
                        "networks",
                        "road",
                        "roads.gpkg"), layer='edges')
    road_edges["mode"] = "road"
    road_edges = add_link_capacity(road_edges,road_future_usage=road_future_usage,mode="road")
    rail_edges = gpd.read_file(os.path.join(
                        load_config()["paths"]["data"],
                        "networks",
                        "rail",
                        "rail.gpkg"),layer="edges")
    rail_edges = rail_edges[rail_edges["status"].isin(rail_status)]
    rail_edges["mode"] = "rail"
    rail_edges = add_link_capacity(rail_edges,rail_future_usage=rail_future_usage,mode="rail")
    port_edges = gpd.read_file(os.path.join(
                        load_config()["paths"]["data"],
                        "networks",
                        "ports",
                        "port.gpkg"),layer="edges")
    port_edges["mode"] = "port"
    port_edges = add_link_capacity(port_edges)
    multi_modal_edges = gpd.read_file(os.path.join(
                        load_config()["paths"]["data"],
                        "networks",
                        "multimodal",
                        "multi_modal.gpkg"),layer="edges")
    multi_modal_edges["mode"] = "multi"
    multi_modal_edges = add_link_capacity(multi_modal_edges)
    network_edges = pd.concat([road_edges,rail_edges,
                        port_edges,multi_modal_edges],
                        axis=0,ignore_index=True)
    network_edges = network_edges[network_edges["mode"].isin(modes)][network_columns]
    if return_network is True:
        G = ig.Graph.TupleList(network_edges.itertuples(index=False), edge_attrs=list(network_edges.columns)[2:])
        return G
    else:
        return network_edges

def get_flow_on_edges(save_paths_df,edge_id_column,edge_path_column,
    flow_column):
    """Write results to Shapefiles

    Outputs ``gdf_edges`` - a shapefile with minimum and maximum tonnage flows of all
    commodities/industries for each edge of network.

    Parameters
    ---------
    save_paths_df
        Pandas DataFrame of OD flow paths and their tonnages
    industry_columns
        List of string names of all OD commodities/industries indentified
    min_max_exist
        List of string names of commodity/industry columns for which min-max tonnage column names already exist
    gdf_edges
        GeoDataFrame of network edge set
    save_csv
        Boolean condition to tell code to save created edge csv file
    save_shapes
        Boolean condition to tell code to save created edge shapefile
    shape_output_path
        Path where the output shapefile will be stored
    csv_output_path
        Path where the output csv file will be stored

    """
    edge_flows = defaultdict(float)
    for row in save_paths_df.itertuples():
        for item in getattr(row,edge_path_column):
            edge_flows[item] += getattr(row,flow_column)

    return pd.DataFrame([(k,v) for k,v in edge_flows.items()],columns=[edge_id_column,flow_column])


# def get_flow_paths_indexes_of_edges(flow_dataframe,path_criteria):
#     edge_path_index = defaultdict(list)
#     for k,v in zip(chain.from_iterable(flow_dataframe[path_criteria].ravel()), flow_dataframe.index.repeat(flow_dataframe[path_criteria].str.len()).tolist()):
#         edge_path_index[k].append(v)

#     del flow_dataframe
#     return edge_path_index

def get_flow_paths_indexes_of_edges(flow_dataframe,path_criteria):
    edge_path_index = defaultdict(list)
    for v in flow_dataframe.itertuples():
        for k in getattr(v,path_criteria):
            edge_path_index[k].append(v.Index)

    del flow_dataframe
    return edge_path_index

def get_path_indexes_for_edges(edge_ids_with_paths,selected_edge_list):
    return list(
            set(
                list(
                    chain.from_iterable([
                        path_idx for path_key,path_idx in edge_ids_with_paths.items() if path_key in selected_edge_list
                                        ]
                                        )
                    )
                )
            )

def network_od_path_estimations(graph,
    source, target, cost_criteria):
    """Estimate the paths, distances, times, and costs for given OD pair

    Parameters
    ---------
    graph
        igraph network structure
    source
        String/Float/Integer name of Origin node ID
    source
        String/Float/Integer name of Destination node ID
    tonnage : float
        value of tonnage
    vehicle_weight : float
        unit weight of vehicle
    cost_criteria : str
        name of generalised cost criteria to be used: min_gcost or max_gcost
    time_criteria : str
        name of time criteria to be used: min_time or max_time
    fixed_cost : bool

    Returns
    -------
    edge_path_list : list[list]
        nested lists of Strings/Floats/Integers of edge ID's in routes
    path_dist_list : list[float]
        estimated distances of routes
    path_time_list : list[float]
        estimated times of routes
    path_gcost_list : list[float]
        estimated generalised costs of routes

    """
    paths = graph.get_shortest_paths(source, target, weights=cost_criteria, output="epath")


    edge_path_list = []
    path_gcost_list = []
    # for p in range(len(paths)):
    for path in paths:
        edge_path = []
        path_gcost = 0
        if path:
            for n in path:
                edge_path.append(graph.es[n]['edge_id'])
                path_gcost += graph.es[n][cost_criteria]

        edge_path_list.append(edge_path)
        path_gcost_list.append(path_gcost)

    
    return edge_path_list, path_gcost_list

def network_od_paths_assembly(points_dataframe, graph,
                                cost_criteria,store_edge_path=True):
    """Assemble estimates of OD paths, distances, times, costs and tonnages on networks

    Parameters
    ----------
    points_dataframe : pandas.DataFrame
        OD nodes and their tonnages
    graph
        igraph network structure
    region_name : str
        name of Province
    excel_writer
        Name of the excel writer to save Pandas dataframe to Excel file

    Returns
    -------
    save_paths_df : pandas.DataFrame
        - origin - String node ID of Origin
        - destination - String node ID of Destination
        - min_edge_path - List of string of edge ID's for paths with minimum generalised cost flows
        - max_edge_path - List of string of edge ID's for paths with maximum generalised cost flows
        - min_netrev - Float values of estimated netrevenue for paths with minimum generalised cost flows
        - max_netrev - Float values of estimated netrevenue for paths with maximum generalised cost flows
        - min_croptons - Float values of estimated crop tons for paths with minimum generalised cost flows
        - max_croptons - Float values of estimated crop tons for paths with maximum generalised cost flows
        - min_distance - Float values of estimated distance for paths with minimum generalised cost flows
        - max_distance - Float values of estimated distance for paths with maximum generalised cost flows
        - min_time - Float values of estimated time for paths with minimum generalised cost flows
        - max_time - Float values of estimated time for paths with maximum generalised cost flows
        - min_gcost - Float values of estimated generalised cost for paths with minimum generalised cost flows
        - max_gcost - Float values of estimated generalised cost for paths with maximum generalised cost flows

    """
    save_paths = []
    points_dataframe = points_dataframe.set_index('origin_id')
    origins = list(set(points_dataframe.index.values.tolist()))
    for origin in origins:
        try:
            destinations = list(set(points_dataframe.loc[[origin], 'destination_id'].values.tolist()))

            get_path, get_gcost = network_od_path_estimations(
                graph, origin, destinations, cost_criteria)

            # tons = points_dataframe.loc[[origin], tonnage_column].values
            save_paths += list(zip([origin]*len(destinations),
                                destinations, get_path,
                                get_gcost))

            # print(f"done with {origin}")
        except:
            print(f"* no path between {origin}-{destinations}")
    
    cols = [
        'origin_id', 'destination_id', 'edge_path','gcost'
    ]
    save_paths_df = pd.DataFrame(save_paths, columns=cols)
    if store_edge_path is False:
        save_paths_df.drop("edge_path",axis=1,inplace=True)

    points_dataframe = points_dataframe.reset_index()
    # save_paths_df = pd.merge(save_paths_df, points_dataframe, how='left', on=[
    #                          'origin_id', 'destination_id']).fillna(0)

    save_paths_df = pd.merge(points_dataframe,save_paths_df,how='left', on=[
                             'origin_id', 'destination_id']).fillna(0)

    # save_paths_df = save_paths_df[(save_paths_df[tonnage_column] > 0)
    #                               & (save_paths_df['origin_id'] != 0)]
    save_paths_df = save_paths_df[save_paths_df['origin_id'] != 0]

    return save_paths_df

def update_flow_and_overcapacity(od_dataframe,network_dataframe,flow_column,edge_id_column="edge_id",subtract=False):
    edge_flows = get_flow_on_edges(od_dataframe,edge_id_column,"edge_path",flow_column)
    edge_flows.rename(columns={flow_column:"added_flow"},inplace=True)
    network_dataframe = pd.merge(network_dataframe,edge_flows,how="left",on=[edge_id_column]).fillna(0)
    del edge_flows
    if subtract is True:
        network_dataframe[flow_column] = network_dataframe[flow_column] - network_dataframe["added_flow"]
    else:
        network_dataframe[flow_column] += network_dataframe["added_flow"]
    network_dataframe["over_capacity"] = network_dataframe["capacity"] - network_dataframe[flow_column]

    return network_dataframe

def find_minimal_flows_along_overcapacity_paths(over_capacity_ods,network_dataframe,over_capacity_edges,edge_id_paths,flow_column):
    over_capacity_edges_df = pd.DataFrame([
                                (
                                    path_key,path_idx
                                ) for path_key,path_idx in edge_id_paths.items() if path_key in over_capacity_edges
                            ],columns = ["edge_id","path_indexes"]
                                )
    over_capacity_edges_df = pd.merge(over_capacity_edges_df,
                                network_dataframe[["edge_id","residual_capacity","added_flow"]],
                                how="left",
                                on=["edge_id"])
    # print (over_capacity_edges_df)
    # print (over_capacity_ods)
    over_capacity_edges_df["edge_path_flow"] = over_capacity_edges_df.progress_apply(
                                        lambda x:over_capacity_ods[
                                            over_capacity_ods.path_indexes.isin(x.path_indexes)
                                            ][flow_column].values,
                                        axis=1
                                        )
    over_capacity_edges_df["edge_path_flow_cor"] = over_capacity_edges_df.progress_apply(
                                        lambda x:list(
                                            1.0*x.residual_capacity*x.edge_path_flow/x.added_flow),
                                        axis=1
                                        )
    over_capacity_edges_df["path_flow_tuples"] = over_capacity_edges_df.progress_apply(
                                        lambda x:list(zip(x.path_indexes,x.edge_path_flow_cor)),axis=1)

    min_flows = []
    for r in over_capacity_edges_df.itertuples():
        min_flows += r.path_flow_tuples

    min_flows = pd.DataFrame(min_flows,columns=["path_indexes","min_flows"])
    min_flows = min_flows.sort_values(by=["min_flows"],ascending=True)
    min_flows = min_flows.drop_duplicates(subset=["path_indexes"],keep="first")

    over_capacity_ods = pd.merge(over_capacity_ods,min_flows,how="left",on=["path_indexes"])
    del min_flows, over_capacity_edges_df
    over_capacity_ods["residual_flows"] = over_capacity_ods[flow_column] - over_capacity_ods["min_flows"]

    return over_capacity_ods

def od_flow_allocation_capacity_constrained(flow_ods,network_dataframe,flow_column,cost_column,store_edge_path=True):
    network_dataframe["over_capacity"] = network_dataframe["capacity"] - network_dataframe[flow_column]
    capacity_ods = []
    unassigned_paths = []
    while len(flow_ods.index) > 0:
        # print (flow_ods)
        graph = ig.Graph.TupleList(network_dataframe[network_dataframe["over_capacity"] > 1e-3].itertuples(index=False), 
                        edge_attrs=list(network_dataframe[network_dataframe["over_capacity"] > 1e-3].columns)[2:])
        graph_nodes = [x['name'] for x in graph.vs]
        unassigned_paths.append(flow_ods[~((flow_ods["origin_id"].isin(graph_nodes)) & (flow_ods["destination_id"].isin(graph_nodes)))])
        flow_ods = flow_ods[(flow_ods["origin_id"].isin(graph_nodes)) & (flow_ods["destination_id"].isin(graph_nodes))]
        if len(flow_ods.index) > 0:
            flow_ods = network_od_paths_assembly(flow_ods,graph,cost_column)
            unassigned_paths.append(flow_ods[flow_ods["gcost"] == 0])
            flow_ods = flow_ods[flow_ods["gcost"] > 0]
            if len(flow_ods.index) > 0:
                # print (flow_ods)
                network_dataframe["residual_capacity"] = network_dataframe["over_capacity"]
                network_dataframe = update_flow_and_overcapacity(flow_ods,network_dataframe,flow_column)
                over_capacity_edges = network_dataframe[network_dataframe["over_capacity"] < -1.0e-3]["edge_id"].values.tolist()
                if len(over_capacity_edges) > 0:
                    edge_id_paths = get_flow_paths_indexes_of_edges(flow_ods,"edge_path")
                    edge_paths_overcapacity = get_path_indexes_for_edges(edge_id_paths,over_capacity_edges)
                    if store_edge_path is False:
                        cap_ods = flow_ods[~flow_ods.index.isin(edge_paths_overcapacity)]
                        cap_ods.drop("edge_path",axis=1,inplace=True)
                        capacity_ods.append(cap_ods)
                        del cap_ods
                    else:
                        capacity_ods.append(flow_ods[~flow_ods.index.isin(edge_paths_overcapacity)])

                    over_capacity_ods = flow_ods[flow_ods.index.isin(edge_paths_overcapacity)]
                    over_capacity_ods["path_indexes"] = over_capacity_ods.index.values.tolist()
                    over_capacity_ods = find_minimal_flows_along_overcapacity_paths(over_capacity_ods,network_dataframe,
                                                                over_capacity_edges,edge_id_paths,flow_column)
                    cap_ods = over_capacity_ods.copy() 
                    cap_ods.drop(["path_indexes",flow_column,"residual_flows"],axis=1,inplace=True)
                    cap_ods.rename(columns={"min_flows":flow_column},inplace=True)
                    if store_edge_path is False:
                        cap_ods.drop("edge_path",axis=1,inplace=True)
                    
                    capacity_ods.append(cap_ods)
                    del cap_ods

                    over_capacity_ods["residual_ratio"] = over_capacity_ods["residual_flows"]/over_capacity_ods[flow_column]
                    over_capacity_ods.drop(["path_indexes",flow_column,"min_flows"],axis=1,inplace=True)
                    over_capacity_ods.rename(columns={"residual_flows":flow_column},inplace=True)

                    network_dataframe.drop("added_flow",axis=1,inplace=True)
                    network_dataframe = update_flow_and_overcapacity(over_capacity_ods,
                                                        network_dataframe,flow_column,subtract=True)
                    network_dataframe.drop("added_flow",axis=1,inplace=True)
                    flow_ods = over_capacity_ods[over_capacity_ods["residual_ratio"] > 0.01]
                    flow_ods.drop(["edge_path","gcost","residual_ratio"],axis=1,inplace=True)
                    del over_capacity_ods
                else:
                    if store_edge_path is False:
                        flow_ods.drop("edge_path",axis=1,inplace=True)
                    capacity_ods.append(flow_ods)
                    network_dataframe.drop(["residual_capacity","added_flow"],axis=1,inplace=True)
                    flow_ods = pd.DataFrame()

    return capacity_ods, unassigned_paths

def od_assignment_capacity_constrained_slow(od_dataframe,network_dataframe,
                network_id_column,
                cost_column,
                flow_column,capacity_column,
                assigned_flow_columns=['od_index','origin_id', 'destination_id', 'edge_path',
                    'distance', 'time', 'gcost', 'tons']):
    """
    Starting assumption is that we have an OD matrix and a network
    The network edge capacities are assigned to begin with
    """
    save_paths = []
    unassigned_paths = []
    od_len = len(od_dataframe.index)
    minimum_capacity = min(network_dataframe[capacity_column])
    for row in od_dataframe.itertuples():
        od_index = getattr(row,'od_index')
        origin = getattr(row,'origin_id')
        destination = getattr(row,'destination_id')
        tons = getattr(row,flow_column)
        a = min(tons,minimum_capacity)
        while a > 0:
            network_dataframe['over_cap'] = network_dataframe[flow_column] - network_dataframe[capacity_column]
            graph = ig.Graph.TupleList(network_dataframe[network_dataframe['over_cap'] < 0].itertuples(index=False), 
                                edge_attrs=list(network_dataframe[network_dataframe['over_cap'] < 0].columns)[2:])
            graph_nodes = [x['name'] for x in graph.vs]
            if (origin in graph_nodes) and (destination in graph_nodes): 
                path = graph.get_shortest_paths(origin, [destination], weights=cost_column, output="epath")[0]
                if path:
                    get_gcost = sum([x for x in graph.es[path][cost_column]])
                    get_path = [x for x in graph.es[path]['edge_id']]
                    save_paths.append((od_index,origin, destination,
                                    get_path, get_gcost,a))
                    get_flows = pd.DataFrame(list(zip(get_path,[a]*len(get_path))),columns=[network_id_column,'flows'])
                    network_dataframe = pd.merge(network_dataframe,get_flows,how='left',on=[network_id_column])
                    network_dataframe['flows'].fillna(0,inplace=True)
                    network_dataframe[flow_column] = network_dataframe[flow_column] + network_dataframe['flows']
                    network_dataframe.drop('flows',axis=1,inplace=True)
                else:
                    unassigned_paths.append((od_index,origin, destination,[],0,a))
            else:
                unassigned_paths.append((od_index,origin, destination,[],0,a))

            tons = tons - minimum_capacity
            cap = network_dataframe[capacity_column] - network_dataframe[flow_column]
            minimum_capacity = min(cap[cap > 1.0e-3])
            del cap
            a = min(tons,minimum_capacity)
        print("done with {} out of {}".format(row.Index,od_len))
        
    network_dataframe['over_cap'] = network_dataframe['over_cap'].mask(network_dataframe['over_cap'] >= 0, 1)
    network_dataframe['over_cap'] = network_dataframe['over_cap'].mask(network_dataframe['over_cap'] < 0, 0)

    save_paths_df = pd.DataFrame(save_paths, columns=assigned_flow_columns)
    del save_paths
    unassigned_df = pd.DataFrame(unassigned_paths,columns=assigned_flow_columns)


    return save_paths_df, unassigned_df, network_dataframe