"""Estimate direct damages to physical assets exposed to hazards

"""
import sys
import os
import json

import pandas as pd
import geopandas as gpd
import fiona
from shapely.geometry import shape, mapping
import numpy as np
from tqdm import tqdm
tqdm.pandas()

def load_config():
    """Read config.json
    """
    config_path = os.path.join(os.path.dirname(__file__),'..', '..','..', 'config.json')
    with open(config_path, 'r') as config_fh:
        config = json.load(config_fh)
    return config

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
    countries = gpd.read_file(os.path.join(processed_data_path,
                                            "Admin_boundaries",
                                            "gadm36_levels_gpkg",
                                            "gadm36_levels_continents.gpkg"),
                            layer="level0")[["ISO_A3","NAME","CONTINENT"]]
    print (countries)

    global_od_data = pd.read_csv(os.path.join(processed_data_path,"flow_od_data","baci_mode_prediction_2015_EORA.csv"))
    print (global_od_data)

    flow_columns = ["v","q",
                    "v_air_predict","q_air_predict",
                    "v_sea_predict","q_sea_predict",
                    "v_land_predict","q_land_predict"]
    global_od_data = pd.merge(global_od_data,countries,how="left",left_on=["iso3_O"],right_on=["ISO_A3"])
    global_od_data.drop("ISO_A3",axis=1,inplace=True)
    global_od_data.rename(columns={"NAME":"NAME_O","CONTINENT":"CONTINENT_O"},inplace=True)
    global_od_data = pd.merge(global_od_data,countries,how="left",left_on=["iso3_D"],right_on=["ISO_A3"])
    global_od_data.drop("ISO_A3",axis=1,inplace=True)
    global_od_data.rename(columns={"NAME":"NAME_D","CONTINENT":"CONTINENT_D"},inplace=True)

    global_od_data = global_od_data.groupby(["iso3_O","iso3_D",
                                            "Industries",
                                            "NAME_O","NAME_D",
                                            "CONTINENT_O","CONTINENT_D"])[flow_columns].sum().reset_index()
    global_od_data = global_od_data[(global_od_data["CONTINENT_O"] == "Africa") | (global_od_data["CONTINENT_D"] == "Africa")]
    print (global_od_data)


    trade_rest_of_world = global_od_data[global_od_data["CONTINENT_O"] != global_od_data["CONTINENT_D"]]
    column_changes = [("iso3_O","ROW","CONTINENT_O"),
                        ("NAME_O","Rest","CONTINENT_O"),
                        ("CONTINENT_O","Rest of the World","CONTINENT_O"),
                        ("iso3_D","ROW","CONTINENT_D"),
                        ("NAME_D","Rest","CONTINENT_D"),
                        ("CONTINENT_D","Rest of the World","CONTINENT_D")
                    ]
    for i, (column_name,column_value,continent) in enumerate(column_changes):
        trade_rest_of_world[column_name] = trade_rest_of_world.progress_apply(
                                            lambda x:column_value if x[continent] != "Africa" else x[column_name],axis=1)
    trade_rest_of_world["v_land_predict"] = 0
    trade_rest_of_world["q_land_predict"] = 0
    trade_rest_of_world = trade_rest_of_world.groupby(["iso3_O","iso3_D",
                                            "Industries",
                                            "NAME_O","NAME_D",
                                            "CONTINENT_O","CONTINENT_D"])[flow_columns].sum().reset_index()
    print (trade_rest_of_world)

    trade_africa = global_od_data[global_od_data["CONTINENT_O"] == global_od_data["CONTINENT_D"]]

    africa_od_ports = pd.read_csv(os.path.join(incoming_data_path,
                                            "ports/port_usage",
                                            "OD_maritime_Africa.csv"))
    africa_od_ports = list(set(zip(africa_od_ports["from_iso3"].values.tolist(),africa_od_ports["to_iso3"].values.tolist())))
    trade_africa["port_connectivity"] = trade_africa.progress_apply(
                                        lambda x:1 if ((x["iso3_O"],x["iso3_D"]) in africa_od_ports) or ((x["iso3_D"],x["iso3_O"]) in africa_od_ports) else 0,
                                        axis=1)
    print (trade_africa)

    africa_ports = gpd.read_file(os.path.join(processed_data_path,"africa/networks","africa_ports_modified.gpkg"),layer="nodes")
    africa_ports = list(set(africa_ports[africa_ports["infra"] == "port"]["iso3"].values.tolist()))
    trade_africa["iso3_O_port"] = trade_africa.progress_apply(lambda x:1 if x["iso3_O"] in africa_ports else 0, axis=1)
    trade_africa["iso3_D_port"] = trade_africa.progress_apply(lambda x:1 if x["iso3_D"] in africa_ports else 0, axis=1)

    trade_africa["v_land_predict"] = trade_africa.progress_apply(
                                        lambda x:x["v_land_predict"] + x["v_sea_predict"] if x["iso3_O_port"]*x["iso3_D_port"] == 0 else x["v_land_predict"],
                                        axis=1)
    trade_africa["q_land_predict"] = trade_africa.progress_apply(
                                        lambda x:x["q_land_predict"] + x["q_sea_predict"] if x["iso3_O_port"]*x["iso3_D_port"] == 0 else x["q_land_predict"],
                                        axis=1)

    trade_africa["v_sea_predict"] = trade_africa.progress_apply(
                                    lambda x:0 if x["iso3_O_port"]*x["iso3_D_port"] == 0 else x["v_sea_predict"],
                                    axis=1)
    trade_africa["q_sea_predict"] = trade_africa.progress_apply(
                                    lambda x:0 if x["iso3_O_port"]*x["iso3_D_port"] == 0 else x["q_sea_predict"],
                                    axis=1)

    trade_africa.drop(["port_connectivity","iso3_O_port","iso3_D_port"],axis=1,inplace=True)

    trade_od = pd.concat([trade_africa,trade_rest_of_world],axis=0,ignore_index=True)

    trade_od.to_csv(os.path.join(processed_data_path,"flow_od_data","africa_trade_2015_modified.csv"),index=False)

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)