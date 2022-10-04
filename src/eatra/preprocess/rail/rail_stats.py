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

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    output_path = config['paths']['output']
    
    networks = os.path.join(data_path,'rail')


    summary_path = os.path.join(output_path,'summary_stats')
    if os.path.exists(summary_path) == False:
            os.mkdir(summary_path)

    output_excel = os.path.join(summary_path,
                                'rail_conditions.xlsx',
                                )
    output_wrtr = pd.ExcelWriter(output_excel)
    edges = gpd.read_file(os.path.join(networks,'network.geojson'))

    edges['length'] = 0.001*edges['length']
    
    edges[edges['status'] == 'open'].groupby(['country',
                                            'status',
                                            'gauge'])['length'].sum().reset_index().to_excel(output_wrtr,
                                                                                            'current', 
                                                                                            index=False)
    output_wrtr.save()

    edges[edges['status'] != 'open'].groupby(['country',
                                            'status',
                                            'gauge'])['length'].sum().reset_index().to_excel(output_wrtr,
                                                                                            'future', 
                                                                                            index=False)

    output_wrtr.save()
    
    edges.groupby(['country',
                    'status',
                    'gauge'])['length'].sum().reset_index().to_excel(output_wrtr,
                                                                    'all', 
                                                                    index=False)

    output_wrtr.save()
    


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
