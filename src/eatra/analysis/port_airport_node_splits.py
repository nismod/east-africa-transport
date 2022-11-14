"""Estimate direct damages to physical assets exposed to hazards

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


def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    """In 2015, Mombasa handled a total of 26.2m tonnes of cargo, more than double the volume handled in 2005. 
        Transit cargo to the hinterlands, which consist of Uganda, Rwanda, South Sudan, Burundi, Somalia, 
        northern Tanzania, and eastern parts of the Democratic Republic of Congo (DRC), 
        have also gone up at an annual rate of 8.2% between 2005 and 2015.
    """
    
    """Identify the countries by their continent first:
        We assume that there is no land transport between our East Africa countries 
        And any country not in Africa
        Even if the OD data says it is - which is probably an error in the OD data
    """
    trade_od = pd.read_csv(os.path.join(processed_data_path,"flow_od_data","africa_trade_2015_modified.csv"))
    print (trade_od)
    mombasa_dsm_od = pd.read_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "mombasa_dsm_2015_import_exports.csv"))
    countries = list(set(mombasa_dsm_od["iso3_O"].values.tolist() + mombasa_dsm_od["iso3_D"].values.tolist()))
    trade_columns = ["node_id","iso3_O","iso3_D","trade_type","q_sea_predict_road","v_sea_predict_road","q_sea_predict_rail","v_sea_predict_rail","total_share"]
    trade_node_od = []
    for iso_code in countries:
        sea_exports = trade_od[trade_od["iso3_O"] == iso_code].groupby(["iso3_O"])[["q_sea_predict","v_sea_predict"]].sum().reset_index()
        sea_imports = trade_od[trade_od["iso3_D"] == iso_code].groupby(["iso3_D"])[["q_sea_predict","v_sea_predict"]].sum().reset_index()
        if iso_code == "TZA":
            tanzania_port_shares = pd.read_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "tanzania_port_2015_shares.csv"))[["port_code","import_fraction","export_fraction"]]
            tanzania_port_shares["node_id"] = ["TZA_port_1","TZA_port_3","TZA_port_2"]
            port_imports = tanzania_port_shares[["node_id","import_fraction"]]
            port_imports["q_sea_predict_road"] = sea_imports["q_sea_predict"].values[0]*port_imports["import_fraction"]
            port_imports["v_sea_predict_road"] = sea_imports["v_sea_predict"].values[0]*port_imports["import_fraction"]
            port_imports["iso3_D"] = "TZA"
            port_imports["iso3_O"] = "TZA"
            port_imports["trade_type"] = "imports"
            port_imports["total_share"] = port_imports["import_fraction"]
            port_imports["q_sea_predict_rail"] = 0
            port_imports["v_sea_predict_rail"] = 0
            
            port_exports = tanzania_port_shares[["node_id","export_fraction"]]
            port_exports["q_sea_predict_road"] = sea_exports["q_sea_predict"].values[0]*port_exports["export_fraction"]
            port_exports["v_sea_predict_road"] = sea_exports["v_sea_predict"].values[0]*port_exports["export_fraction"]
            port_exports["iso3_O"] = "TZA"
            port_exports["iso3_D"] = "TZA"
            port_exports["trade_type"] = "exports"
            port_exports["total_share"] = port_exports["export_fraction"]
            port_exports["q_sea_predict_rail"] = 0
            port_exports["v_sea_predict_rail"] = 0
            trade_node_od.append(port_imports[trade_columns])
            trade_node_od.append(port_exports[trade_columns])

        elif iso_code == "KEN":
            port_imports = sea_imports.copy()
            port_imports["q_sea_predict_road"] = port_imports["q_sea_predict"]
            port_imports["v_sea_predict_road"] = port_imports["v_sea_predict"]
            port_imports["q_sea_predict_rail"] = 0
            port_imports["v_sea_predict_rail"] = 0
            port_imports["node_id"] = "KEN_port_17"
            port_imports["iso3_O"] = "KEN"
            port_imports["trade_type"] = "imports"
            port_imports["total_share"] = 1

            port_exports = sea_exports.copy()
            port_exports["q_sea_predict_road"] = port_exports["q_sea_predict"]
            port_exports["v_sea_predict_road"] = port_exports["v_sea_predict"]
            port_exports["node_id"] = "KEN_port_17"
            port_exports["iso3_D"] = "KEN" 
            port_exports["trade_type"] = "exports"  
            port_exports["total_share"] = 1      
            port_exports["q_sea_predict_rail"] = 0
            port_exports["v_sea_predict_rail"] = 0   

            trade_node_od.append(port_imports[trade_columns])
            trade_node_od.append(port_exports[trade_columns])
        else:
            mombasa_dsm_ports = pd.DataFrame([("KEN","KEN_port_17"),("TZA","TZA_port_1")],columns=["iso3_O","node_id"])
            country_imports = mombasa_dsm_od[mombasa_dsm_od["iso3_D"] == iso_code]
            country_imports = pd.merge(country_imports,mombasa_dsm_ports,how="left",on=["iso3_O"])
            country_imports["port_share"] = country_imports["tons"]/country_imports["tons"].sum()
            total_share = country_imports["tons"].sum()/sea_imports["q_sea_predict"].values[0]
            if total_share < 1:
                country_imports["total_share"] = total_share
                country_imports["q_sea_predict_road"] = total_share*sea_imports["q_sea_predict"].values[0]*country_imports["port_share"]*country_imports["road"]
                country_imports["v_sea_predict_road"] = total_share*sea_imports["v_sea_predict"].values[0]*country_imports["port_share"]*country_imports["road"]
                country_imports["q_sea_predict_rail"] = total_share*sea_imports["q_sea_predict"].values[0]*country_imports["port_share"]*country_imports["rail"]
                country_imports["v_sea_predict_rail"] = total_share*sea_imports["v_sea_predict"].values[0]*country_imports["port_share"]*country_imports["rail"]
            
            else:
                country_imports["total_share"] = country_imports["port_share"]
                # country_imports["q_sea_predict_road"] = sea_imports["q_sea_predict"].values[0]*country_imports["port_share"]*country_imports["road"]
                # country_imports["v_sea_predict_road"] = sea_imports["v_sea_predict"].values[0]*country_imports["port_share"]*country_imports["road"]
                # country_imports["q_sea_predict_rail"] = sea_imports["q_sea_predict"].values[0]*country_imports["port_share"]*country_imports["rail"]
                # country_imports["v_sea_predict_rail"] = sea_imports["v_sea_predict"].values[0]*country_imports["port_share"]*country_imports["rail"]
                
                country_imports["q_sea_predict_road"] = country_imports["tons"]*country_imports["port_share"]*country_imports["road"]
                country_imports["v_sea_predict_road"] = total_share*sea_imports["v_sea_predict"].values[0]*country_imports["port_share"]*country_imports["road"]
                country_imports["q_sea_predict_rail"] = country_imports["tons"]*country_imports["port_share"]*country_imports["rail"]
                country_imports["v_sea_predict_rail"] = total_share*sea_imports["v_sea_predict"].values[0]*country_imports["port_share"]*country_imports["rail"]

            country_imports["trade_type"] = "imports"
            trade_node_od.append(country_imports[trade_columns])

            mombasa_dsm_ports = pd.DataFrame([("KEN","KEN_port_17"),("TZA","TZA_port_1")],columns=["iso3_D","node_id"])
            country_exports = mombasa_dsm_od[mombasa_dsm_od["iso3_O"] == iso_code]
            country_exports = pd.merge(country_exports,mombasa_dsm_ports,how="left",on=["iso3_D"])
            country_exports["port_share"] = country_exports["tons"]/country_imports["tons"].sum()
            total_share = country_exports["tons"].sum()/sea_exports["q_sea_predict"].values[0]
            if total_share < 1:
                country_exports["total_share"] = total_share
                country_exports["q_sea_predict_road"] = total_share*sea_exports["q_sea_predict"].values[0]*country_exports["port_share"]*country_exports["road"]
                country_exports["v_sea_predict_road"] = total_share*sea_exports["v_sea_predict"].values[0]*country_exports["port_share"]*country_exports["road"]
                country_exports["q_sea_predict_rail"] = total_share*sea_exports["q_sea_predict"].values[0]*country_exports["port_share"]*country_exports["rail"]
                country_exports["v_sea_predict_rail"] = total_share*sea_exports["v_sea_predict"].values[0]*country_exports["port_share"]*country_exports["rail"]
            else:
                country_exports["total_share"] = country_exports["port_share"]
                # country_exports["q_sea_predict_road"] = sea_exports["q_sea_predict"].values[0]*country_exports["port_share"]*country_exports["road"]
                # country_exports["v_sea_predict_road"] = sea_exports["v_sea_predict"].values[0]*country_exports["port_share"]*country_exports["road"]
                # country_exports["q_sea_predict_rail"] = sea_exports["q_sea_predict"].values[0]*country_exports["port_share"]*country_exports["rail"]
                # country_exports["v_sea_predict_rail"] = sea_exports["v_sea_predict"].values[0]*country_exports["port_share"]*country_exports["rail"]
                
                country_exports["q_sea_predict_road"] = country_exports["tons"]*country_exports["port_share"]*country_exports["road"]
                country_exports["v_sea_predict_road"] = total_share*sea_exports["v_sea_predict"].values[0]*country_exports["port_share"]*country_exports["road"]
                country_exports["q_sea_predict_rail"] = country_exports["tons"]*country_exports["port_share"]*country_exports["rail"]
                country_exports["v_sea_predict_rail"] = total_share*sea_exports["v_sea_predict"].values[0]*country_exports["port_share"]*country_exports["rail"]
            
            country_exports["trade_type"] = "exports"
            trade_node_od.append(country_exports[trade_columns])

    trade_node_od = pd.concat(trade_node_od,axis=0,ignore_index=True)
    print (trade_node_od)
    trade_node_od.to_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "mombasa_dsm_2015_country_splits.csv"),index=False)

    trade_node_od = []
    airport_nodes = gpd.read_file(os.path.join(processed_data_path,
                                    "africa/networks",
                                    "airports_modified.gpkg"),layer="nodes")
    airport_nodes["Freight"] = airport_nodes.progress_apply(lambda x:float(str(x["Freight"]).replace(",",'')),axis=1)
    trade_columns = ["node_id","iso3_O","iso3_D","trade_type",
                "q_air_predict_road","v_air_predict_road","total_share"]
    airport_countries = list(set(airport_nodes["iso_code"].values.tolist()))
    for iso_code in airport_countries:
        air_exports = trade_od[trade_od["iso3_O"] == iso_code].groupby(["iso3_O"])[["q_air_predict","v_air_predict"]].sum().reset_index()
        air_imports = trade_od[trade_od["iso3_D"] == iso_code].groupby(["iso3_D"])[["q_air_predict","v_air_predict"]].sum().reset_index()
        airports = airport_nodes[airport_nodes["iso_code"] == iso_code][["node_id","iso_code","Freight"]]
        airports["freight_fraction"] = airports["Freight"]/airports["Freight"].sum()

        airport_imports = airports[["node_id","freight_fraction"]]
        airport_imports["q_air_predict_road"] = air_imports["q_air_predict"].values[0]*airport_imports["freight_fraction"]
        airport_imports["v_air_predict_road"] = air_imports["v_air_predict"].values[0]*airport_imports["freight_fraction"]
        airport_imports["iso3_D"] = iso_code
        airport_imports["iso3_O"] = iso_code
        airport_imports["trade_type"] = "imports"
        airport_imports["total_share"] = airport_imports["freight_fraction"]
        
        
        airport_exports = airports[["node_id","freight_fraction"]]
        airport_exports["q_air_predict_road"] = air_exports["q_air_predict"].values[0]*airport_exports["freight_fraction"]
        airport_exports["v_air_predict_road"] = air_exports["v_air_predict"].values[0]*airport_exports["freight_fraction"]
        airport_exports["iso3_O"] = iso_code
        airport_exports["iso3_D"] = iso_code
        airport_exports["trade_type"] = "exports"
        airport_exports["total_share"] = airport_exports["freight_fraction"]
        trade_node_od.append(airport_imports[trade_columns])
        trade_node_od.append(airport_exports[trade_columns])

    trade_node_od = pd.concat(trade_node_od,axis=0,ignore_index=True)
    print (trade_node_od)
    trade_node_od.to_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "airport_country_splits.csv"),index=False)
        




if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)