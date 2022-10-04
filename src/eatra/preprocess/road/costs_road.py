import pandas as pd
import geopandas as gpd
import fiona
import os
import json

def load_config():
    """Read config.json"""
    config_path = os.path.join(os.path.dirname(__file__),"..","..","..","config.json")
    with open(config_path, "r") as config_fh:
        config = json.load(config_fh)
    return config

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']

    # Read road costs
    costs_path = os.path.join(incoming_data_path,"costs","road_and_rail_costs.xlsx")
    road_costs = pd.read_excel(costs_path, sheet_name = "road_costs")

    # Pull road values
    min_motorway_paved = road_costs.loc[(road_costs["highway"]=="motorway")&(road_costs["road_cond"]=="paved"),"cost_min"].values[0]
    min_motorway_unpaved = road_costs.loc[(road_costs["highway"]=="motorway")&(road_costs["road_cond"]=="unpaved"),"cost_min"].values[0]
    max_motorway_paved = road_costs.loc[(road_costs["highway"]=="motorway")&(road_costs["road_cond"]=="paved"),"cost_max"].values[0]
    max_motorway_unpaved = road_costs.loc[(road_costs["highway"]=="motorway")&(road_costs["road_cond"]=="unpaved"),"cost_max"].values[0]

    min_trunk_paved = road_costs.loc[(road_costs["highway"]=="trunk")&(road_costs["road_cond"]=="paved"),"cost_min"].values[0]
    min_trunk_unpaved = road_costs.loc[(road_costs["highway"]=="trunk")&(road_costs["road_cond"]=="unpaved"),"cost_min"].values[0]
    max_trunk_paved = road_costs.loc[(road_costs["highway"]=="trunk")&(road_costs["road_cond"]=="paved"),"cost_max"].values[0]
    max_trunk_unpaved = road_costs.loc[(road_costs["highway"]=="trunk")&(road_costs["road_cond"]=="unpaved"),"cost_max"].values[0]

    min_primary_paved = road_costs.loc[(road_costs["highway"]=="primary")&(road_costs["road_cond"]=="paved"),"cost_min"].values[0]
    min_primary_unpaved = road_costs.loc[(road_costs["highway"]=="primary")&(road_costs["road_cond"]=="unpaved"),"cost_min"].values[0]
    max_primary_paved = road_costs.loc[(road_costs["highway"]=="primary")&(road_costs["road_cond"]=="paved"),"cost_max"].values[0]
    max_primary_unpaved = road_costs.loc[(road_costs["highway"]=="primary")&(road_costs["road_cond"]=="unpaved"),"cost_max"].values[0]

    min_secondary_paved = road_costs.loc[(road_costs["highway"]=="secondary")&(road_costs["road_cond"]=="paved"),"cost_min"].values[0]
    min_secondary_unpaved = road_costs.loc[(road_costs["highway"]=="secondary")&(road_costs["road_cond"]=="unpaved"),"cost_min"].values[0]
    max_secondary_paved = road_costs.loc[(road_costs["highway"]=="secondary")&(road_costs["road_cond"]=="paved"),"cost_max"].values[0]
    max_secondary_unpaved = road_costs.loc[(road_costs["highway"]=="secondary")&(road_costs["road_cond"]=="unpaved"),"cost_max"].values[0]

    min_tertiary_paved = road_costs.loc[(road_costs["highway"]=="tertiary")&(road_costs["road_cond"]=="paved"),"cost_min"].values[0]
    min_tertiary_unpaved = road_costs.loc[(road_costs["highway"]=="tertiary")&(road_costs["road_cond"]=="unpaved"),"cost_min"].values[0]
    max_tertiary_paved = road_costs.loc[(road_costs["highway"]=="tertiary")&(road_costs["road_cond"]=="paved"),"cost_max"].values[0]
    max_tertiary_unpaved = road_costs.loc[(road_costs["highway"]=="tertiary")&(road_costs["road_cond"]=="unpaved"),"cost_max"].values[0]

    min_bridge_paved = road_costs.loc[(road_costs["highway"]=="bridge")&(road_costs["road_cond"]=="paved"),"cost_min"].values[0]
    min_bridge_unpaved = road_costs.loc[(road_costs["highway"]=="bridge")&(road_costs["road_cond"]=="unpaved"),"cost_min"].values[0]
    max_bridge_paved = road_costs.loc[(road_costs["highway"]=="bridge")&(road_costs["road_cond"]=="paved"),"cost_max"].values[0]
    max_bridge_unpaved = road_costs.loc[(road_costs["highway"]=="bridge")&(road_costs["road_cond"]=="unpaved"),"cost_max"].values[0]

    def road_cost_min(p):
	    if p["bridge"] != None:
	        if p["road_cond"] == "paved":
	            return min_bridge_paved * 0.001
	        else: 
	            return min_bridge_unpaved * 0.001
	    else:
	        if p["highway"] == "motorway":
	            if p["road_cond"] == "paved":
	                return min_motorway_paved * 0.001
	            else: 
	                return min_motorway_unpaved * 0.001
	        if p["highway"] == "trunk":
	            if p["road_cond"] == "paved":
	                return min_trunk_paved * 0.001
	            else: 
	                return min_trunk_unpaved * 0.001
	        if p["highway"] == "primary":
	            if p["road_cond"] == "paved":
	                return min_primary_paved * 0.001
	            else: 
	                return min_primary_unpaved * 0.001
	        if p["highway"] == "secondary":
	            if p["road_cond"] == "paved":
	                return min_secondary_paved * 0.001
	            else: 
	                return min_secondary_unpaved * 0.001
	        if p["highway"] == "tertiary":
	            if p["road_cond"] == "paved":
	                return min_tertiary_paved * 0.001
	            else: 
	                return min_tertiary_unpaved * 0.001

    def road_cost_max(p):
	    if p["bridge"] != None:
	        if p["road_cond"] == "paved":
	            return max_bridge_paved * 0.001
	        else: 
	            return max_bridge_unpaved * 0.001
	    else:
	        if p["highway"] == "motorway":
	            if p["road_cond"] == "paved":
	                return max_motorway_paved * 0.001
	            else: 
	                return max_motorway_unpaved * 0.001
	        if p["highway"] == "trunk":
	            if p["road_cond"] == "paved":
	                return max_trunk_paved * 0.001
	            else: 
	                return max_trunk_unpaved * 0.001
	        if p["highway"] == "primary":
	            if p["road_cond"] == "paved":
	                return max_primary_paved * 0.001
	            else: 
	                return max_primary_unpaved * 0.001
	        if p["highway"] == "secondary":
	            if p["road_cond"] == "paved":
	                return max_secondary_paved * 0.001
	            else: 
	                return max_secondary_unpaved * 0.001
	        if p["highway"] == "tertiary":
	            if p["road_cond"] == "paved":
	                return max_tertiary_paved * 0.001
	            else: 
	                return max_tertiary_unpaved * 0.001

    countries = ["kenya", "tanzania", "uganda", "zambia"]

    for country in countries: 
        print ("Starting ", country)
        
        # Add road costs
        road_path = os.path.join(data_path,country,"networks","road.gpkg")
        road_edges = gpd.read_file(road_path, layer = "edges",
                              ignore_fields = ["fid","osm_id","name","waterway","aerialway","barrier","man_made","z_order","surface","maxspeed","length_km","other_tags"])

        # Set cost_unit
        road_edges["cost_unit"] = "USD/m/lane"

        # Set cost_min
        road_edges["cost_min"] = None
        road_edges["cost_min"] = road_edges.apply(lambda p: road_cost_min(p), axis=1)

        # Set cost_max
        road_edges["cost_max"] = None
        road_edges["cost_max"] = road_edges.apply(lambda p: road_cost_max(p), axis=1)

        ### Export to file
        road_edges.to_file(road_path, layer='edges', driver='GPKG')

        print ("Finished with ", country)

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)