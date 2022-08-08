#!/usr/bin/env python
# coding: utf-8
"""Process road data from OSM extracts and create road network topology 
"""
import os
from glob import glob
import json
import fiona
import geopandas as gpd
import pandas as pd
from geopy import distance
import shapely.geometry
import igraph as ig
import networkx
from shapely.geometry import Point, shape, mapping
from boltons.iterutils import pairwise
from tqdm import tqdm
tqdm.pandas()
from utils import *
from pyproj import Geod

def components(edges,nodes,node_id_col):
    G = networkx.Graph()
    G.add_nodes_from(
        (getattr(n, node_id_col), {"geometry": n.geometry}) for n in nodes.itertuples()
    )
    G.add_edges_from(
        (e.from_node, e.to_node, {"edge_id": e.edge_id, "geometry": e.geometry})
        for e in edges.itertuples()
    )
    components = networkx.connected_components(G)
    for num, c in enumerate(components):
        print(f"Component {num} has {len(c)} nodes")
        edges.loc[(edges.from_node.isin(c) | edges.to_node.isin(c)), "component"] = num
        nodes.loc[nodes[node_id_col].isin(c), "component"] = num

    return edges, nodes

def convert_json_geopandas(df,epsg=4326):
    layer_dict = []    
    for key, value in df.items():
        if key == "features":
            for feature in value:
                if any(feature["geometry"]["coordinates"]):
                    d1 = {"geometry":shape(feature["geometry"])}
                    d1.update(feature["properties"])
                    layer_dict.append(d1)

    return gpd.GeoDataFrame(pd.DataFrame(layer_dict),geometry="geometry", crs=f"EPSG:{epsg}")


def match_nodes_edges_to_countries(nodes,edges,countries):
    # assign iso code and continent name to each node
    nodes_matches = gpd.sjoin(nodes[["node_id","type","name","facility","gauge","geometry"]],
                                countries[["ISO_A3","CONTINENT","geometry"]], 
                                how="left", predicate='within').reset_index()
    nodes_matches = nodes_matches[~nodes_matches["ISO_A3"].isna()]
    #nodes_matches = nodes_matches[["node_id","ISO_A3","CONTINENT","geometry"]]
    nodes_matches.rename(columns={"ISO_A3":"iso_code","CONTINENT":"continent"},inplace=True)
    nodes_matches = nodes_matches.drop_duplicates(subset=["node_id"],keep="first")
    
    nodes_unmatched = nodes[~nodes["node_id"].isin(nodes_matches["node_id"].values.tolist())]
    nodes_unmatched = gpd.sjoin_nearest(nodes_unmatched[["node_id","type","name","facility","gauge","geometry"]],
                                countries[["ISO_A3","CONTINENT","geometry"]], 
                                how="left").reset_index()
    #nodes_unmatched = nodes_unmatched[["node_id","ISO_A3","CONTINENT","geometry"]]
    nodes_unmatched.rename(columns={"ISO_A3":"iso_code","CONTINENT":"continent"},inplace=True)
    nodes_unmatched = nodes_unmatched.drop_duplicates(subset=["node_id"],keep="first")

    nodes = pd.concat([nodes_matches,nodes_unmatched],axis=0,ignore_index=True)
    #nodes = gpd.GeoDataFrame(nodes[["node_id","iso_code","continent","geometry"]],geometry="geometry",crs="EPSG:4326")
    nodes = gpd.GeoDataFrame(nodes,geometry="geometry",crs="EPSG:4326")
    
    # assign iso code and continent name to each edge
    edges = pd.merge(edges,nodes[["node_id","iso_code","continent"]],how="left",left_on=["from_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"from_iso","continent":"from_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)
    edges = pd.merge(edges,nodes[["node_id","iso_code","continent"]],how="left",left_on=["to_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"to_iso","continent":"to_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)

    # nodes["old_node_id"] = nodes["node_id"]
    nodes["node_id"] = nodes.progress_apply(lambda x:f"{x.iso_code}_{x.node_id}",axis=1)
    edges["from_node"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.from_node}",axis=1)
    edges["to_node"] = edges.progress_apply(lambda x:f"{x.to_iso}_{x.to_node}",axis=1)
    # edges["old_edge_id"] = edges["edge_id"]
    edges["edge_id"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.to_iso}_{x.edge_id}",axis=1)
    
    return nodes, edges

def assign_rail_speeds(x):
    if x.status in ["proposed","construction","rehabilitation"]:
        return 120
    elif x.time_freight > 0:
        return max(round(0.001*x["length"]/(x["time_freight"]/60.0),0),30)
    else:
        return 30

def main(config):
    data_path = config['paths']['data']
    scratch_path = config['paths']['scratch']

    # Read in raw network geojson files
    nodes = json.load(open(os.path.join(scratch_path,
                            "rail",
                            "nodes.geojson")))
    nodes = convert_json_geopandas(nodes)
    
    edges = json.load(open(os.path.join(scratch_path,
                            "rail",
                            "network.geojson")))
    edges = convert_json_geopandas(edges)
    
    # Create network topology
    network = create_network_from_nodes_and_edges(
        nodes,
        edges,
        "rail"
    )

    network.edges = network.edges.set_crs(epsg=4326)
    network.nodes = network.nodes.set_crs(epsg=4326)
        
    # Store the final road network in geopackage in the processed_path
    out_fname = os.path.join(data_path,
        "networks",
        "rail",
        "rail.gpkg")
    

    print("Done exporting, ready to add attributes")


    """Assign country info"""
    edges = network.edges
    nodes = network.nodes

    global_country_info = gpd.read_file(os.path.join(data_path,
        "Admin_boundaries",
        "gadm36_levels_gpkg",
        "gadm36_levels_continents.gpkg"))
    global_country_info = global_country_info.to_crs(epsg=4326)
    global_country_info = global_country_info.explode(ignore_index=True)
    global_country_info = global_country_info.sort_values(by="CONTINENT",ascending=True)
    
    nodes, edges = match_nodes_edges_to_countries(nodes,edges,global_country_info)
    print ("Done adding country info attributes")

    """Assign rail attributes"""

    # Calculate and add length of line segments 
    geod = Geod(ellps="WGS84")
    edges['length_m'] = edges.progress_apply(lambda x:float(geod.geometry_length(x.geometry)),axis=1)
    
    # Add speeds
    edges["speed_freight"] = edges.progress_apply(lambda x:assign_rail_speeds(x),axis=1)
    speed_uncertainty = 0.1
    edges["min_speed"] = (1 - speed_uncertainty)*edges["speed_freight"]
    edges["max_speed"] = (1 + speed_uncertainty)*edges["speed_freight"]

    # add a boolean "is_current" column
    # to mark any past/future lines as not current
    edges['is_current'] = ~edges['status'].isin((
        'abandoned',
        'disused',
        'construction',
        'proposed',
        'rehabilitation'))

    print("Done adding rail attributes")

    """Assign cost attributes"""

    # Assign rehabilitation costs
    rehab_costs = pd.read_excel(os.path.join(data_path,"costs","rehabilitation_costs.xlsx"), sheet_name = "rail_costs")
    edges["cost_min"] = float(rehab_costs.cost_min.values[0])
    edges["cost_max"] = float(rehab_costs.cost_max.values[0])
    edges["cost_unit"] = str(rehab_costs.cost_unit.values[0])

    # Assign tariff costs 
    cost_data = pd.read_csv(os.path.join(data_path,"costs","transport_costs.csv"))
    cost_data = cost_data.loc[cost_data['transport'] == "rail"]
    cost_data.rename(columns = {'cost_km':'tariff_cost'}, inplace = True)

    edges = pd.merge(edges,cost_data[["from_iso3","tariff_cost"]],how="left",left_on=["from_iso"],right_on=["from_iso3"])

    edges["min_tariff"] = edges.progress_apply(lambda x:float(x.tariff_cost) - (float(x.tariff_cost)*0.2),axis=1)
    edges["max_tariff"] = edges.progress_apply(lambda x:float(x.tariff_cost) + (float(x.tariff_cost)*0.2),axis=1)
    edges.drop(["tariff_cost","from_iso3"],axis=1,inplace=True)
    edges["tariff_cost_unit"] = "USD/ton-km"

    # Assign flow costs    
    time_cost_factor = 0.49
    edges["min_flow_cost"] = (time_cost_factor*edges["length_m"]/1000)/edges["max_speed"] + (edges["min_tariff"]*edges["length_m"]/1000)
    edges["max_flow_cost"] = (time_cost_factor*edges["length_m"]/1000)/edges["min_speed"] + (edges["max_tariff"]*edges["length_m"]/1000)
    edges["flow_cost_unit"] = "USD/ton"

    print("Done adding cost attributes")

    # Prepare for export and finish
    edges = gpd.GeoDataFrame(edges,geometry="geometry",crs="EPSG:4326")
    edges, nodes = components(edges,nodes,"node_id")
    print("Ready to export")
    edges.to_file(out_fname, layer='edges', driver='GPKG')
    nodes.to_file(out_fname, layer='nodes', driver='GPKG')
    
    print("Done.")

    # pd.DataFrame(list(set(zip(edges["country"].values.tolist(),
    #                     edges["line"].values.tolist(),
    #                     edges["status"].values.tolist(),
    #                     edges["gauge"].values.tolist()))),
    #                     columns=["country","line","status","gauge"]).to_csv(os.path.join(data_path,
    #                                     "networks","rail",
    #                                     "rail_line_attributes.csv"),index=False)

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
