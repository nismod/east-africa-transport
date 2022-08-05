"""Dissagregate OD matrix for air flows to node pairs

"""
import sys
import os

import pandas as pd
import geopandas as gpd
import fiona
from collections import defaultdict
from shapely.geometry import shape, mapping
pd.options.mode.chained_assignment = None  # default='warn'
# import warnings
# warnings.simplefilter(action='ignore', category=SettingWithCopyWarning)
import numpy as np
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    tonnage_column = "total_tonnage"
    all_ods = pd.read_csv(os.path.join(results_data_path,
                                        "flow_paths",
                                        "od_matrix_nodes.csv"))
    assigned_flow_columns=['od_index','origin_id', 'destination_id', 'edge_path',
                    'gcost', tonnage_column]
    network_df = create_multi_modal_network_africa(return_network=False)
    network_df[tonnage_column] = 0
    # network_df["capacity"] = 1e10
    # print (network_df[network_df["capacity"] <= 0])
    # print (min(network_df["capacity"]))
    all_ods = all_ods.sort_values(by=[tonnage_column],ascending=False,ignore_index=True)
    all_ods['od_index'] = all_ods.index.values.tolist()
    assigned_output_path = os.path.join(results_data_path,"flow_paths",
                    'flow_paths_assignment_true.csv')
    unassigned_output_path = os.path.join(results_data_path,"flow_paths",
                    'flow_paths_assignment_false.csv')
    edge_flows_path = os.path.join(results_data_path,"flow_paths",
                    'edge_flows_capacity_constrained.csv')
    all_paths, no_paths, network_df = od_assignment_capacity_constrained(all_ods,network_df,
                                                                        'edge_id',
                                                                        'max_flow_cost',
                                                                        tonnage_column,
                                                                        'capacity',
                                                                        assigned_flow_columns=assigned_flow_columns)

    del all_ods
    # all_paths['edge_path'] = all_paths.progress_apply(lambda x:str(x['edge_path']),axis=1)
    # all_paths = all_paths.groupby(['origin', 'destination', 'edge_path',
    #         'distance', 'time', 'gcost'])['max_tons'].sum().reset_index()
    # all_paths['od_index'] = all_paths.index.values.tolist()
    # # all_paths, edges_in = flow_assignment_elco(all_ods,edges_in,
    # #                         'max_gcost','max_time',
    # #                         'max_tons','capacity')
    all_paths.to_csv(assigned_output_path,index=False)
    no_paths.to_csv(unassigned_output_path,index=False)
    network_df.to_csv(edge_flows_path,index=False)


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)