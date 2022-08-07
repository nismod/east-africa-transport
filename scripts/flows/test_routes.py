"""Estimate direct damages to physical assets exposed to hazards

"""
import sys
import os

import pandas as pd
import geopandas as gpd
import numpy as np
import igraph as ig
import ast
from collections import defaultdict
from shapely.geometry import Point,LineString
from itertools import chain
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']                                    

    # # network_withoutrail = create_multi_modal_network_africa(modes=["road","port","multi"])
    # network_withrail = create_multi_modal_network_africa()
    
    # cost_criteria = "max_flow_cost"
    # # cost_criteria = "min_flow_cost"
    # source = "TZA_port_1"
    # # source = "TZA_roadn_61407"
    # # source = "KEN_port_17"
    # # target = "UGA_port_14"
    # # target = "BDI_port_10"
    # # target = "BDI_roadn_607109"
    # # target = "BDI_roadn_37463"
    # target = "UGA_roadn_412369"
    # # target = "BDI_roadn_106275"
    # # target = "KEN_railn_105"
    # # target = "KEN_roadn_3220"
    # # target = "ZMB_railn_397"
    # mf = network_withrail.maxflow(source, 
    #                             target, 
    #                             capacity=network_withrail.es["capacity"])
    # print (mf)
    # get_path, get_gcost_withrail = network_od_path_estimations(network_withrail,source, target, cost_criteria)
    # print (get_path)
    # print ("* Costs with rail",get_gcost_withrail[0])

    # get_path, get_gcostwithoutrail = network_od_path_estimations(network_withoutrail,source, target, cost_criteria)
    # # print (get_path)
    # print ("* Costs without rail",get_gcostwithoutrail[0])
    # print ("* Cost difference",get_gcost_withrail[0] - get_gcostwithoutrail[0])

    g = ig.Graph(6,[(3, 2), (3, 4), (2, 1), (4,1), (4, 5), (1, 0), (5, 0)],directed=True)
    g.es["capacity"] = [7, 8, 1, 2, 3, 4, 5] # capacity of each edge

    paths  = g.get_shortest_paths(3, [0,5],output="epath")
    print (paths)
    # Run the max flow
    flow = g.maxflow(3, [0,5], capacity=g.es["capacity"])
    print("Max flow:", flow.value)
    print("Edge assignments:", flow.flow)

    


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)