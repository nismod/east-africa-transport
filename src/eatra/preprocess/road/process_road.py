#!/usr/bin/env python
# coding: utf-8
"""Process road data from OSM extracts and create road network topology 
"""
import os
from glob import glob

import fiona
import geopandas as gpd
import pandas as pd
from tqdm import tqdm
tqdm.pandas()
from .utils import *

def get_road_condition_surface(x):
    if not x.surface:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 'paved','asphalt'
        else:
            return 'unpaved','gravel'
    elif x.surface == 'paved':
        return x.surface, 'asphalt'
    elif x.surface == 'unpaved':
        return x.surface, 'gravel'
    elif x.surface in ('asphalt','concrete'):
        return 'paved',x.surface
    else:
        return 'unpaved',x.surface

def get_road_width(x,width,shoulder):
    if not x.lanes:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 2.0*width + 2.0*shoulder
        else:
            return 1.0*width + 2.0*shoulder
    else:
        return float(x.lanes)*width + 2.0*shoulder

def get_road_lanes(x):
    if not x.lanes:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 2
        else:
            return 1
    else:
        return x.lanes

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    output_path = config['paths']['output']
    scratch_path = config['paths']['scratch']

    networks = os.path.join(scratch_path,'road')

    # Extract date string
    date="211101"

    width = 6.5 # Default carriageway width in meters
    shoulder = 1.5

    # Extract rail features from .osm.pbf to .gpkg
    countries=[
        "kenya",
        "tanzania",
        "uganda",
        "zambia"
    ]

    summary_path = os.path.join(output_path,'summary_stats')
    if os.path.exists(summary_path) == False:
            os.mkdir(summary_path)

    output_excel = os.path.join(summary_path,
                                'road_conditions_summary.xlsx',
                                )
    output_wrtr = pd.ExcelWriter(output_excel)
    for country in countries:
        # Read the geopackage file that was converted from osm.pdf 
        edges = gpd.read_file(os.path.join(networks,f"{country}-road.gpkg"), layer = "lines")
        
        # From the geopackage file extract relevant roads
        highway_list = ['motorway','motorway_link',
                   'trunk','trunk_link',
                   'primary','primary_link',
                   'secondary','secondary_link',
                   'tertiary','tertiary_link']
        edges = edges[edges.highway.isin(highway_list)]

        # Add attributes
        edges['surface_material'] = edges.progress_apply(lambda x:get_road_condition_surface(x),axis=1)
        edges[['road_cond','material']] = edges['surface_material'].apply(pd.Series)
        edges.drop('surface_material',axis=1,inplace=True)
        edges['width_m'] = edges.progress_apply(lambda x:get_road_width(x,width,shoulder),axis=1)
        edges['lanes'] = edges.progress_apply(lambda x:get_road_lanes(x),axis=1)
        edges['highway'] = edges.progress_apply(lambda x: x.highway.replace('_link',''),axis=1)

        processed_path = os.path.join(data_path,country,'networks')

        if os.path.exists(processed_path) == False:
            os.mkdir(processed_path)

        out_fname = os.path.join(data_path,country,"networks","road.gpkg")
        
        # Create network topology
        network = create_network_from_nodes_and_edges(
            None,
            edges,
            "road",
            out_fname,
        )
        
        # Set projection systems find the actual road lengths in meters
        # Length may be invalid for a geographic CRS using degrees as units; must project geometries to a planar CRS
        # EPSG 32736 works for Burundi, Eswatini, Kenya, Malawi, Mozambique, Rwanda, South Africa, Tanzania, Uganda, Zambia, Zimbabwe
        # Use https://epsg.io/ to find for other areas 
        network.edges = network.edges.set_crs(epsg=4326)
        network.nodes = network.nodes.set_crs(epsg=4326)
        network.edges = network.edges.to_crs(epsg=32736)
        network.nodes = network.nodes.to_crs(epsg=32736)

        network.edges['road_length_m'] = network.edges.progress_apply(lambda x:x.geometry.length,axis=1)

        # Store the final road network in geopackage in the processed_path
        network.edges.to_file(out_fname, layer='edges', driver='GPKG')
        network.nodes.to_file(out_fname, layer='nodes', driver='GPKG')
        
        # Generate summary statistics
        sum_network = network.edges.groupby(['highway','road_cond'])[['road_length_m']].sum().reset_index()
        print (sum_network) # length in m

        sum_network2 = (sum_network.set_index(['highway']).pivot(
                                    columns='road_cond'
                                    )['road_length_m'].div(1000).reset_index().rename_axis(None, axis=1)).fillna(0)
        print(sum_network2) # length converted to km

        sum_network2.to_excel(output_wrtr,country, index=False)
        output_wrtr.save()


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
