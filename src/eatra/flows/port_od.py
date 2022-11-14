"""Dissagregate OD matrix for air flows to node pairs

"""
import sys
import os

import pandas as pd
import geopandas as gpd
import fiona
from shapely.geometry import shape, mapping
import numpy as np
from .analysis_utils import *
from tqdm import tqdm
tqdm.pandas()


def make_od_pairs(nodes, trade_od, weight_col, industry_code, min_value):
    nodes = nodes[nodes[weight_col] > min_value][["node_id","iso_code",weight_col]]
    trade_od = trade_od[trade_od["Industries"] == industry_code]
    
    od_pairs = []
    for row in trade_od.itertuples():
        od_nodes = nodes[nodes["iso_code"] == row.iso3_O][["node_id",weight_col]]
        od_nodes["weight"] = od_nodes[weight_col]/od_nodes[weight_col].sum()
        od_nodes["tonnage"] = (1.0*row.q_air_predict_road/365.0)*od_nodes["weight"]
        od_nodes["value_usd"] = (1.0*row.v_air_predict_road/365.0)*od_nodes["weight"]

        for od in od_nodes.itertuples():
            if row.trade_type == "imports":
                od_pairs.append((row.node_id,od.node_id,row.iso3_O,row.iso3_D,industry_code,od.tonnage,od.value_usd))
            else:
                od_pairs.append((od.node_id,row.node_id,row.iso3_O,row.iso3_D,industry_code,od.tonnage,od.value_usd))

        print (f"* Done with {row.iso3_O}-{row.iso3_D}")
    return od_pairs

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    trade_od = pd.read_csv(os.path.join(processed_data_path,"flow_od_data","africa_trade_2015_modified.csv"))
    trade_node_od = []
    airport_nodes = gpd.read_file(os.path.join(processed_data_path,
                                    "networks",
                                    "airports",
                                    "airports_modified.gpkg"),layer="nodes")
    airport_nodes["Freight"] = airport_nodes.progress_apply(lambda x:float(str(x["Freight"]).replace(",",'')),axis=1)
    trade_columns = ["node_id","iso3_O","iso3_D","Industries","trade_type",
                "q_air_predict_road","v_air_predict_road","freight_fraction"]
    airport_countries = list(set(airport_nodes["iso_code"].values.tolist()))
    
    """Port assignments
    """
    od_pairs = []
    port_nodes = gpd.read_file(os.path.join(processed_data_path,"africa/networks","ports_modified.gpkg"),layer="nodes")
    rail_nodes = gpd.read_file(os.path.join(processed_data_path,"africa/networks","africa_rails_modified.gpkg"),layer="nodes")
    rail_nodes = rail_nodes[~rail_nodes["facility"].isna()]
    port_node_od = pd.read_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "mombasa_dsm_2015_country_splits.csv"))
    for row in port_node_od.itertuples():
        # iso_code = [i for i in [row.iso3_O,row.iso3_D]]
        if row.trade_type == "imports":
            iso_code = row.iso3_D
        else:
            iso_code = row.iso3_O
        if row.q_sea_predict_rail > 0:
            if iso_code in ["COD","UGA","BDI"]:
                od_nodes = port_nodes[port_nodes["iso_code"] == iso_code][["node_id"]]
            elif iso_code == "ZMB":
                od_nodes = rail_nodes[rail_nodes["iso_code"] == iso_code][["node_id"]]
            od_nodes["weight"] = 1.0/len(od_nodes.index)
            od_nodes["tonnage"] = (1.0*row.q_sea_predict_rail/365)*od_nodes["weight"]
            od_nodes["value_usd"] = (1.0*row.v_sea_predict_rail/365)*od_nodes["weight"]
        else:
            od_nodes = road_nodes[road_nodes["iso_code"] == iso_code][["node_id","population"]]
            od_nodes["weight"] = od_nodes["population"]/od_nodes["population"].sum()
            od_nodes["tonnage"] = (1.0*row.q_sea_predict_road/365)*od_nodes["weight"]
            od_nodes["value_usd"] = (1.0*row.v_sea_predict_road/365)*od_nodes["weight"]

        for od in od_nodes.itertuples():
            if row.trade_type == "imports":
                od_pairs.append((row.node_id,od.node_id,row.iso3_O,row.iso3_D,od.tonnage,od.value_usd))
            else:
                od_pairs.append((od.node_id,row.node_id,row.iso3_O,row.iso3_D,od.tonnage,od.value_usd))

        print (f"* Done with {row.iso3_O}-{row.iso3_D}")
    od_pairs = pd.DataFrame(od_pairs,columns=["origin_id","destination_id","iso3_O","iso3_D","tonnage","value_usd"])
    print (od_pairs)
    od_pairs.to_csv(os.path.join(results_data_path,"flow_paths","all_port_od_pairs.csv"), index=False)



if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)