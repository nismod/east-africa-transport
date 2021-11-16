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

    # Read rail costs
    costs_path = os.path.join(incoming_data_path,"costs","road_and_rail_costs.xlsx")
    rail_costs = pd.read_excel(costs_path, sheet_name = "rail_costs")

    countries = ["kenya", "tanzania", "uganda", "zambia"]

    for country in countries: 
        print ("Starting ", country)
        
        rail_path = os.path.join(data_path,country,"networks","rail.gpkg")
        rail_edges = gpd.read_file(rail_path, layer = "edges",
                          ignore_fields = ["fid","osm_id","name","bridge"])
        
        ### Add rail length

        # Set projection systems and find the actual rail lengths in meters
        # Length may be invalid for a geographic CRS using degrees as units; must project geometries to a planar CRS
        # EPSG 32736 works for Burundi, Eswatini, Kenya, Malawi, Mozambique, Rwanda, South Africa, Tanzania, Uganda, Zambia, Zimbabwe
        # Use https://epsg.io/ to find for other areas

        rail_edges = rail_edges.to_crs(epsg=4326)
        rail_edges = rail_edges.to_crs(epsg=32736)

        rail_edges['rail_length_m'] = rail_edges.apply(lambda x:x.geometry.length,axis=1)

        ### Add rail costs 

        # Set cost_unit
        rail_edges["cost_unit"] = "USD/m"
        # Set cost_min
        rail_edges["cost_min"] = rail_costs.cost_min[0] * 0.001
        # Set cost_max
        rail_edges["cost_max"] = rail_costs.cost_max[0] * 0.001

        ### Export to file
        rail_edges.to_file(rail_path, layer='edges', driver='GPKG')

        print ("Finished with ", country)

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)