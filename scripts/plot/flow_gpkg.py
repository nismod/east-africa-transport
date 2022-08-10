""" Create gpkg of flows 
"""
import os
import sys
import warnings
import geopandas as gpd
import pandas as pd 
from plot_utils import *
from east_africa_plotting_attributes import *

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,"flow_maps")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    admin_boundaries = os.path.join(processed_data_path,
                                "admin_boundaries",
                                "east_africa_admin_levels",
                                "admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    road_edges = gpd.read_file(os.path.join(
                        processed_data_path,
                        "networks",
                        "road",
                        "roads.gpkg"), layer='edges')
    road_edges["mode"] = "road"
    road_edges = road_edges[["edge_id","mode","geometry"]]

    rail_edges = gpd.read_file(os.path.join(
                        processed_data_path,
                        "networks",
                        "rail",
                        "rail.gpkg"), layer='edges')
    rail_edges["mode"] = "rail"
    rail_edges = rail_edges[["edge_id","mode","geometry"]]

    port_edges = gpd.read_file(os.path.join(
                        processed_data_path,
                        "networks",
                        "ports",
                        "port.gpkg"),layer="edges")
    port_edges["mode"] = "port"
    port_edges = port_edges[["edge_id","mode","geometry"]]

    multi_edges = gpd.read_file(os.path.join(
                        processed_data_path,
                        "networks",
                        "multimodal",
                        "multi_modal.gpkg"),layer="edges")
    multi_edges["mode"] = "multi"
    multi_edges = multi_edges[["edge_id","mode","geometry"]]

    edges = road_edges.append(rail_edges).append(port_edges).append(multi_edges)

    years = ["2019","2030","2050","2080"]

    for year in years:
        filename = "edge_flows_capacity_constrained_" + year + ".csv"
        
        flow_data = pd.read_csv(os.path.join(output_data_path,
                                          "flow_paths",
                                          filename))
        
        flow_data_gpd = flow_data.merge(edges, on='edge_id').fillna(0)
        flow_data_gpd = gpd.GeoDataFrame(flow_data_gpd, geometry="geometry")
        
        flow_data_gpd.to_file(os.path.join(
            output_data_path,
            "flow_paths",
            "flows.gpkg"), driver="GPKG", layer=year)
        
        print("Done with " + year)
    

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

