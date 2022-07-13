"""Dissagregate OD matrix for air flows to node pairs

"""
import sys
import os

import pandas as pd
import geopandas as gpd
import fiona
from shapely.geometry import shape, mapping
import numpy as np
from analysis_utils import *
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
    
    trade_node_od = []
    for iso_code in airport_countries:
        airports = airport_nodes[airport_nodes["iso_code"] == iso_code][["node_id","iso_code","Freight"]]
        airports["freight_fraction"] = airports["Freight"]/airports["Freight"].sum()

        # imports
        air_imports = trade_od[trade_od["iso3_D"] == iso_code].groupby(["iso3_D","Industries"])[["q_air_predict","v_air_predict"]].sum().reset_index()
        airport_imports = airports[["node_id","iso_code","freight_fraction"]]

        airport_imports = pd.merge(air_imports, 
                          airport_imports, 
                          left_on='iso3_D', 
                          right_on='iso_code')

        airport_imports["q_air_predict_road"] = airport_imports["q_air_predict"] * airport_imports["freight_fraction"]
        airport_imports["v_air_predict_road"] = airport_imports["v_air_predict"] * airport_imports["freight_fraction"]

        airport_imports.drop(columns=["q_air_predict","v_air_predict","iso_code"],inplace=True)
        #airport_imports.rename(columns = {"Industries":"sector","freight_fraction":"total_share"},inplace=True)
        airport_imports["iso3_O"] = iso_code
        airport_imports["trade_type"] = "imports"

        # exports
        air_exports = trade_od[trade_od["iso3_O"] == iso_code].groupby(["iso3_O","Industries"])[["q_air_predict","v_air_predict"]].sum().reset_index()
        airport_exports = airports[["node_id","iso_code","freight_fraction"]]

        airport_exports = pd.merge(air_exports, 
                          airport_exports, 
                          left_on='iso3_O', 
                          right_on='iso_code')

        airport_exports["q_air_predict_road"] = airport_exports["q_air_predict"] * airport_exports["freight_fraction"]
        airport_exports["v_air_predict_road"] = airport_exports["v_air_predict"] * airport_exports["freight_fraction"]

        airport_exports.drop(columns=["q_air_predict","v_air_predict","iso_code"],inplace=True)
        #airport_exports.rename(columns = {"Industries":"sector","freight_fraction":"total_share"},inplace=True)
        airport_exports["iso3_D"] = iso_code
        airport_exports["trade_type"] = "exports"

        trade_node_od.append(airport_imports[trade_columns])
        trade_node_od.append(airport_exports[trade_columns])

    trade_node_od = pd.concat(trade_node_od,axis=0,ignore_index=True)
    trade_node_od.to_csv(os.path.join(results_data_path,
                            "flow_paths",
                            "airport_splits.csv"),index=False)
        

    # Distribute air freight through road network based on weighted nodes

    road_nodes = gpd.read_file(
        os.path.join(processed_data_path,"networks","road","road_weighted.gpkg"),
        layer = "nodes")
    sector_attributes = pd.read_csv(
        os.path.join(processed_data_path,"flow_od_data","sector_description.csv"),
        header=0,
        index_col=False)

    od_pairs = []
    for i in sector_attributes.itertuples():
        od_pairs_sector = make_od_pairs(road_nodes,trade_node_od,i.weight_col,i.industry_code,i.min_value)
        od_pairs.extend(od_pairs_sector)
        del od_pairs_sector

    od_pairs = pd.DataFrame(od_pairs,columns=["origin_id","destination_id","iso3_O","iso3_D","industry","tonnage","value_usd"]) 

    od_pairs.to_csv(os.path.join(results_data_path,"flow_paths","air_od_pairs.csv"), index=False)



if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)