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

def assign_sectors_from_industries(x):
    if x.Industries in (1,2):
        return 'A'
    elif x.Industries == 3:
        return 'B'
    else:
        return 'C'  

def partition_import_export_flows_to_nodes(trade_node_od,node_dataframe,flow_dataframe,iso_countries,flow_type,mode_type):
    for iso_code in iso_countries:
        if flow_type == "import":
            node_df = node_dataframe[node_dataframe["iso_code"] == iso_code][["node_id","iso_code","import"]]
            node_df["import_fraction"] = node_df["import"]/node_df["import"].sum()
            iso_flow = "iso3_D"
            trade_fraction = "import_fraction"
            iso_node = "iso3_O"
        else:
            node_df = node_dataframe[node_dataframe["iso_code"] == iso_code][["node_id","iso_code","export"]] 
            node_df["export_fraction"] = node_df["export"]/node_df["export"].sum()
            iso_flow = "iso3_O"
            trade_fraction = "export_fraction"
            iso_node = "iso3_D"

        if mode_type == "air":
            flow_values = ["q_air_predict","v_air_predict"]
        else:
            flow_values = ["q_sea_predict","v_sea_predict"]


        # imports and exports
        trade_flows = flow_dataframe[
                            flow_dataframe[iso_flow] == iso_code
                            ].groupby([iso_flow,"sector"])[flow_values].sum().reset_index()
        node_df = pd.merge(trade_flows, 
                          node_df[["node_id","iso_code",trade_fraction]], 
                          left_on=iso_flow, 
                          right_on="iso_code")

        # node_df["q_air_predict_road"] = node_df["q_air_predict"]*node_df["import_fraction"]
        # node_df["v_air_predict_road"] = node_df["v_air_predict"]*node_df["import_fraction"]

        node_df[["tonnage","value_usd"]] = node_df[flow_values].multiply(node_df[trade_fraction],axis="index")

        node_df.drop(columns=flow_values + ["iso_code",trade_fraction],inplace=True)
        node_df[iso_node] = node_df.apply(lambda x: str(x.node_id).split("_")[0],axis=1)
        node_df["trade_type"] = flow_type
        node_df["mode_type"] = mode_type

        trade_node_od.append(node_df)

    return trade_node_od

def route_roads_to_nearest_ports(origins_destinations,network_graph,sort_by="origin_id",cost_function="max_flow_cost"):
    # network_graph = create_multi_modal_network_africa(modes=["road","multi"])
    # destinations = list(set(destinations["node_id"].values.tolist()))
    # origins = list(set(origins["node_id"].values.tolist()))
    flow_paths = network_od_paths_assembly(origins_destinations,
                                network_graph,
                                cost_function)
    flow_paths = flow_paths.sort_values(by="gcost")
    flow_paths = flow_paths.drop_duplicates(subset=[sort_by],keep="first")

    return flow_paths

# def make_od_pairs(nodes, trade_od, weight_col, industry_code, min_value):
#     nodes = nodes[nodes[weight_col] > min_value][["node_id","iso_code",weight_col]]
#     trade_od = trade_od[trade_od["Industries"] == industry_code]
    
#     od_pairs = []
#     for row in trade_od.itertuples():
#         od_nodes = nodes[nodes["iso_code"] == row.iso3_O][["node_id",weight_col]]
#         od_nodes["weight"] = od_nodes[weight_col]/od_nodes[weight_col].sum()
#         od_nodes["tonnage"] = (1.0*row.q_air_predict_road/365.0)*od_nodes["weight"]
#         od_nodes["value_usd"] = (1.0*row.v_air_predict_road/365.0)*od_nodes["weight"]

#         for od in od_nodes.itertuples():
#             if row.trade_type == "imports":
#                 od_pairs.append((row.node_id,od.node_id,row.iso3_O,row.iso3_D,industry_code,od.tonnage,od.value_usd))
#             else:
#                 od_pairs.append((od.node_id,row.node_id,row.iso3_O,row.iso3_D,industry_code,od.tonnage,od.value_usd))

#         print (f"* Done with {row.iso3_O}-{row.iso3_D}")
#     return od_pairs

def estimate_od_values(od_values,flow_columns,weight_columns):
    for i,(fl,wt) in enumerate(list(zip(flow_columns,weight_columns))):
        od_values[
                [f"{fl}_value_usd",f"{fl}_tonnage"
                ]] = od_values[[f"{fl}_value_usd",f"{fl}_tonnage"]].multiply((1.0*od_values[wt])/365.0,axis="index")

    return od_values

def make_od_pairs(od_nodes,
                flow_columns,
                import_weight_columns,
                export_weight_columns,
                sector_countries,
                default_import_columns,default_export_columns,trade_type="import"):
    
    if trade_type == "import":
        od_nodes_sector_countries = od_nodes[od_nodes["iso3_D"].isin(sector_countries)]
        weight_columns_sector_countries = import_weight_columns
        od_nodes_rest = od_nodes[~od_nodes["iso3_D"].isin(sector_countries)]
        weight_columns_rest = default_import_columns
    else:
        od_nodes_sector_countries = od_nodes[od_nodes["iso3_O"].isin(sector_countries)]
        weight_columns_sector_countries = export_weight_columns
        od_nodes_rest = od_nodes[~od_nodes["iso3_O"].isin(sector_countries)]
        weight_columns_rest = default_export_columns

    od_nodes_sector_countries = estimate_od_values(od_nodes_sector_countries,flow_columns,weight_columns_sector_countries)
    od_nodes_rest = estimate_od_values(od_nodes_rest,flow_columns,weight_columns_rest)

    return pd.concat([od_nodes_sector_countries,od_nodes_rest],axis=0,ignore_index=True)

def transform_rows_to_columns(dataframe,index_columns,pivot_column,value_column,pivot_values):
    df = (dataframe.set_index(index_columns).pivot(
                                    columns=pivot_column
                                    )[value_column].reset_index().rename_axis(None, axis=1)).fillna(0)
    df.rename(columns=dict([(p,f"{p}_{value_column}") for p in pivot_values]),inplace=True)
    return df

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    od_pairs = pd.read_csv(os.path.join(results_data_path,
                                        "flow_paths",
                                        "od_matrix_nodes.csv"))


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)