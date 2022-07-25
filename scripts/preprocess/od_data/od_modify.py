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

def compare_hvt_estimates(hvt_data,trade_od,trade_od_estimate,hvt_countires=["KEN","TZA","UGA","ZMB"]):
    hvt_export = trade_od[trade_od["iso3_O"].isin(hvt_countires)].groupby(["iso3_O"])[[trade_od_estimate]].sum().reset_index()
    hvt_export.rename(columns={trade_od_estimate:"export_estimate"},inplace=True)
    hvt_import = trade_od[trade_od["iso3_D"].isin(hvt_countires)].groupby(["iso3_D"])[[trade_od_estimate]].sum().reset_index()
    hvt_import.rename(columns={trade_od_estimate:"import_estimate"},inplace=True)

    hvt_data = pd.merge(hvt_data,hvt_export,how="left",left_on=["iso_code"],right_on=["iso3_O"])
    hvt_data = pd.merge(hvt_data,hvt_import,how="left",left_on=["iso_code"],right_on=["iso3_D"])
    hvt_data["import_factor"] = hvt_data["import"]/hvt_data["import_estimate"]
    hvt_data["export_factor"] = hvt_data["export"]/hvt_data["export_estimate"]
    hvt_data.drop(["iso3_O","iso3_D"],axis=1,inplace=True)

    return hvt_data

def modify_trade_od_values(hvt_data,trade_od,trade_od_estimate,value_od_estimate):
    for v in hvt_data.itertuples():
        trade_od.loc[trade_od["iso3_O"] == v.iso_code,trade_od_estimate] = v.export_factor*trade_od.loc[trade_od["iso3_O"] == v.iso_code,trade_od_estimate]
        trade_od.loc[trade_od["iso3_O"] == v.iso_code,value_od_estimate] = v.export_factor*trade_od.loc[trade_od["iso3_O"] == v.iso_code,value_od_estimate]
        trade_od.loc[trade_od["iso3_D"] == v.iso_code,trade_od_estimate] = v.import_factor*trade_od.loc[trade_od["iso3_D"] == v.iso_code,trade_od_estimate]
        trade_od.loc[trade_od["iso3_D"] == v.iso_code,value_od_estimate] = v.import_factor*trade_od.loc[trade_od["iso3_D"] == v.iso_code,value_od_estimate]

    return trade_od

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

    # africa_od_ports = pd.read_csv(os.path.join(incoming_data_path,
    #                                         "ports/port_usage",
    #                                         "OD_maritime_Africa.csv"))
    # africa_od_ports = list(set(zip(africa_od_ports["from_iso3"].values.tolist(),africa_od_ports["to_iso3"].values.tolist())))
    # trade_africa["port_connectivity"] = trade_africa.progress_apply(
    #                                     lambda x:1 if ((x["iso3_O"],x["iso3_D"]) in africa_od_ports) or ((x["iso3_D"],x["iso3_O"]) in africa_od_ports) else 0,
    #                                     axis=1)
    print (trade_africa)

    africa_ports = gpd.read_file(os.path.join(processed_data_path,"networks/ports","africa_ports.gpkg"),layer="nodes")
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

    trade_africa.drop(["iso3_O_port","iso3_D_port"],axis=1,inplace=True)

    trade_od = pd.concat([trade_africa,trade_rest_of_world],axis=0,ignore_index=True)

    trade_od.to_csv(os.path.join(processed_data_path,"flow_od_data","africa_trade_2015_modified.csv"),index=False)

    """Corrections for air imports and export for HVT countries
    """
    air_import_exports = pd.read_excel(os.path.join(processed_data_path,"flow_od_data","airport_stats.xlsx"),sheet_name="Summary")
    air_import_exports = air_import_exports.groupby(["iso_code"])["import","export"].sum().reset_index()
    
    air_import_exports = compare_hvt_estimates(air_import_exports,trade_od,"q_air_predict")
    print ("Air data")
    print (air_import_exports)

    """Corrections for ports imports and export for HVT countries
    """
    port_import_exports = pd.read_csv(os.path.join(processed_data_path,
                                    "flow_od_data",
                                    "hvt_ports_2015_import_exports.csv"))
    port_imports = port_import_exports[port_import_exports["trade_type"] == "import"].groupby(["iso3_D"])["tons"].sum().reset_index()
    port_imports.rename(columns={"tons":"import"},inplace=True)
    port_exports = port_import_exports[port_import_exports["trade_type"] == "export"].groupby(["iso3_O"])["tons"].sum().reset_index()
    port_exports.rename(columns={"tons":"export"},inplace=True)
    port_import_exports = pd.DataFrame()
    port_import_exports["iso_code"] = list(set(port_imports["iso3_D"].values.tolist() + port_exports["iso3_O"].values.tolist()))
    port_import_exports = pd.merge(port_import_exports,port_imports,how="left",left_on=["iso_code"],right_on=["iso3_D"]).fillna(0)
    port_import_exports = pd.merge(port_import_exports,port_exports,how="left",left_on=["iso_code"],right_on=["iso3_O"]).fillna(0)
    port_import_exports.drop(["iso3_O","iso3_D"],axis=1,inplace=True)

    port_import_exports = compare_hvt_estimates(port_import_exports,
                                            trade_od,"q_sea_predict",
                                            hvt_countires=port_import_exports["iso_code"].values.tolist())
    print ("Port data")
    print (port_import_exports)

    trade_od = modify_trade_od_values(air_import_exports,trade_od,"q_air_predict","v_air_predict")
    trade_od = modify_trade_od_values(port_import_exports,trade_od,"q_sea_predict","v_sea_predict")

    trade_od["v"] = trade_od["v_air_predict"] + trade_od["v_sea_predict"] + trade_od["v_land_predict"]
    trade_od["q"] = trade_od["q_air_predict"] + trade_od["q_sea_predict"] + trade_od["q_land_predict"]
    trade_od.to_csv(os.path.join(processed_data_path,"flow_od_data","hvt_trade_2015_modified.csv"),index=False)


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)