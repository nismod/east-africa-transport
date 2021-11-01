#!/usr/bin/env python
# coding: utf-8
"""Pocess road data from OSM extracts
"""
import os
from glob import glob

import fiona
import geopandas as gpd
import pandas as pd
from tqdm import tqdm
tqdm.pandas()
from utils import *

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


def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    output_path = config['paths']['output']
    
    networks = os.path.join(incoming_data_path,'SHP')

    # Extract date string
    date="211027"

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
                                'road_conditions_2.xlsx',
                                )
    output_wrtr = pd.ExcelWriter(output_excel)
    for country in countries:
        edges = gpd.read_file(os.path.join(networks,f"{country}-{date}_highway.shp"))

        edges['surface_material'] = edges.progress_apply(lambda x:get_road_condition_surface(x),axis=1)
        edges[['road_cond','material']] = edges['surface_material'].apply(pd.Series)
        edges.drop('surface_material',axis=1,inplace=True)
        edges['width_m'] = edges.progress_apply(lambda x:get_road_width(x,width,shoulder),axis=1)

        processed_path = os.path.join(data_path,'road',country)
        if os.path.exists(processed_path) == False:
            os.mkdir(processed_path)
        edges.to_file(os.path.join(processed_path,f"{country}-{date}_highway.shp"))

        edges['highway'] = edges.progress_apply(lambda x: x.highway.replace('_link',''),axis=1)
        edges = edges.groupby(['highway','road_cond'])[['length_km']].sum().reset_index()
        print (edges)
        edges = (edges.set_index(['highway']).pivot(
                                    columns='road_cond'
                                    )['length_km'].reset_index().rename_axis(None, axis=1)).fillna(0)

        edges.to_excel(output_wrtr,country, index=False)
        output_wrtr.save()


    
    


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
