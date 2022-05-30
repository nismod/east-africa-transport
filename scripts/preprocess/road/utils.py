"""Functions for preprocessing data
"""
import sys
import os
import json
import snkit
import pandas as pd
import geopandas as gpd
import fiona
from shapely.geometry import shape, mapping

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

def load_config():
    """Read config.json
    """
    config_path = os.path.join(os.path.dirname(__file__),'..', '..','..', 'config.json')
    with open(config_path, 'r') as config_fh:
        config = json.load(config_fh)
    return config

def create_network_from_nodes_and_edges(nodes,edges,node_edge_prefix,out_fname,by=None):
    edges.columns = map(str.lower, edges.columns)
    if "id" in edges.columns.values.tolist():
        edges.rename(columns={"id": "e_id"}, inplace=True)

    # Deal with empty edges (drop)
    empty_idx = edges.geometry.apply(lambda e: e is None or e.is_empty)
    if empty_idx.sum():
        empty_edges = edges[empty_idx]
        print(f"Found {len(empty_edges)} empty edges.")
        print(empty_edges)
        edges = edges[~empty_idx].copy()

    network = snkit.Network(nodes, edges)
    print("* Done with network creation")

    network = snkit.network.split_multilinestrings(network)
    print("* Done with splitting multilines")

    if nodes is not None:
        network = snkit.network.snap_nodes(network)
        print ('* Done with snapping nodes to edges')

        network.nodes = snkit.network.drop_duplicate_geometries(network.nodes)
        print ('* Done with dropping same geometries')

        network = snkit.network.split_edges_at_nodes(network)
        print ('* Done with splitting edges at nodes')

    network = snkit.network.add_endpoints(network)   
    print ('* Done with adding endpoints')

    network = snkit.network.split_edges_at_nodes(network)
    print ('* Done with splitting edges at nodes')
    
    network = snkit.network.add_ids(network, 
                            edge_prefix=f"{node_edge_prefix}e", 
                            node_prefix=f"{node_edge_prefix}n")
    network = snkit.network.add_topology(network, id_col='id')
    print ('* Done with network topology')

    if by is not None:
        network = snkit.network.merge_edges(network,by=by)
        print ('* Done with merging network')

    network.edges.rename(columns={'from_id':'from_node',
                                'to_id':'to_node',
                                'id':'edge_id'},
                                inplace=True)
    network.nodes.rename(columns={'id':'node_id'},inplace=True)
    
    # network.edges.to_file(out_fname, layer='edges', driver='GPKG')
    # network.nodes.to_file(out_fname, layer='nodes', driver='GPKG')

    return network