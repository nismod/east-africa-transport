#!/usr/bin/env python
# coding: utf-8
"""Process road data from OSM extracts and create road network topology 
"""
import os
from glob import glob

import fiona
import geopandas as gpd
import pandas as pd
from geopy import distance
import shapely.geometry
from shapely.geometry import Point
from pyproj import Geod
from boltons.iterutils import pairwise
import igraph as ig
#import networkx
from tqdm import tqdm
tqdm.pandas()
from utils import *

from pyproj import Geod

def components(edges,nodes):
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

def get_road_condition_surface(x):
    if not x.surface:
        if x.highway in ('motorway','trunk','primary'):
            return 'paved','asphalt'
        else:
            return 'unpaved','gravel'
    elif x.surface == 'paved':
        return x.surface, 'asphalt'
    elif x.surface == 'unpaved':
        return x.surface, 'gravel'
    elif x.surface in ('asphalt','concrete'):
        return 'paved',x.surface
    else:
        return 'unpaved',x.surface

def get_road_lanes(x):
    # if there is osm data available, use that and if not assign based on default value
    try:
        float(x.lanes)
        if x.lanes == 0:
            return 1.0
        else:
            return float(x.lanes)
    except (ValueError, TypeError):
        if x.highway in ('motorway','trunk','primary'):
            return 2.0
        else:
            return 1.0

def assign_road_speeds(x):
    if x.highway in ('motorway','trunk','primary'):
        return x["Highway_min"],x["Highway_max"]
    elif x.road_cond == "paved":
        return x["Urban_min"],x["Urban_max"]
    else:
        return x["Rural_min"],x["Rural_max"]

def get_rehab_costs(x, rehab_costs):
    if x.bridge not in ('0','no'): 
        highway = "bridge"
        condition = x.road_cond
    else:
        highway = x.highway
        condition = x.road_cond
    
    cost_min = rehab_costs.cost_min.loc[(rehab_costs.highway==highway)&(rehab_costs.road_cond==condition)].values
    cost_max = rehab_costs.cost_max.loc[(rehab_costs.highway==highway)&(rehab_costs.road_cond==condition)].values
    cost_unit = rehab_costs.cost_unit.loc[(rehab_costs.highway==highway)&(rehab_costs.road_cond==condition)].values
    
    return float(cost_min[0]) , float(cost_max[0]) , str(cost_unit[0])

def match_nodes_edges_to_countries(nodes,edges,countries):
    # assign iso code and continent name to each node
    nodes_matches = gpd.sjoin(nodes[["node_id","geometry"]],
                                countries, 
                                how="left", predicate='within').reset_index()
    nodes_matches = nodes_matches[~nodes_matches["ISO_A3"].isna()]
    nodes_matches = nodes_matches[["node_id","ISO_A3","CONTINENT","geometry"]]
    nodes_matches.rename(columns={"ISO_A3":"iso_code","CONTINENT":"continent"},inplace=True)
    nodes_matches = nodes_matches.drop_duplicates(subset=["node_id"],keep="first")
    
    nodes_unmatched = nodes[~nodes["node_id"].isin(nodes_matches["node_id"].values.tolist())]
    nodes_unmatched = gpd.sjoin_nearest(nodes_unmatched[["node_id","geometry"]],
                                countries, 
                                how="left").reset_index()
    nodes_unmatched = nodes_unmatched[["node_id","ISO_A3","CONTINENT","geometry"]]
    nodes_unmatched.rename(columns={"ISO_A3":"iso_code","CONTINENT":"continent"},inplace=True)
    nodes_unmatched = nodes_unmatched.drop_duplicates(subset=["node_id"],keep="first")

    nodes = pd.concat([nodes_matches,nodes_unmatched],axis=0,ignore_index=True)
    nodes = gpd.GeoDataFrame(nodes[["node_id","iso_code","continent","geometry"]],geometry="geometry",crs="EPSG:4326")
    
    # assign iso code and continent name to each edge
    edges = pd.merge(edges,nodes[["node_id","iso_code","continent"]],how="left",left_on=["from_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"from_iso","continent":"from_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)
    edges = pd.merge(edges,nodes[["node_id","iso_code","continent"]],how="left",left_on=["to_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"to_iso","continent":"to_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)

    nodes["old_node_id"] = nodes["node_id"]
    nodes["node_id"] = nodes.progress_apply(lambda x:f"{x.iso_code}_{x.node_id}",axis=1)
    edges["from_node"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.from_node}",axis=1)
    edges["to_node"] = edges.progress_apply(lambda x:f"{x.to_iso}_{x.to_node}",axis=1)
    edges["old_edge_id"] = edges["edge_id"]
    edges["edge_id"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.to_iso}_{x.edge_id}",axis=1)
    
    return nodes, edges

def main(config):
    data_path = config['paths']['data']
    scratch_path = config['paths']['scratch']

    edges = gpd.read_file((os.path.join(scratch_path,
                            "road_africa","africa-road.gpkg")),
                            layer="lines",
                            ignore_fields=["waterway","aerialway","barrier","man_made","z_order","other_tags"])
    
    print(edges)
    print("Done reading file")
    
    # From the geopackage file extract relevant roads
    highway_list = ['motorway','motorway_link',
               'trunk','trunk_link',
               'primary','primary_link',
               'secondary','secondary_link',
               'tertiary','tertiary_link']
    edges = edges[edges.highway.isin(highway_list)]
    edges['highway'] = edges.progress_apply(lambda x: x.highway.replace('_link',''),axis=1)

    # Create network topology
    network = create_network_from_nodes_and_edges(
        None,
        edges,
        "road",
        out_fname,
    )

    network.edges = network.edges.set_crs(epsg=4326)
    network.nodes = network.nodes.set_crs(epsg=4326)
    
    print (network.edges)
    print (network.nodes)
    print("Ready to export file")

    # Store the final road network in geopackage in the processed_path
    out_fname = os.path.join(data_path,"road/africa","africa-roads.gpkg")

    network.edges.to_file(out_fname, layer='edges', driver='GPKG')
    network.nodes.to_file(out_fname, layer='nodes', driver='GPKG')


    print("Done exporting, ready to add attributes")

    """Assign country info"""

    #Find the countries of the nodes and assign them to the node ID's, accordingly modify the edge ID's as well

    nodes = gpd.read_file(out_fname,layer='nodes')
    edges = gpd.read_file(out_fname,layer='edges')
    print("Done reading files")

    global_country_info = gpd.read_file(os.path.join(data_path,
                                                "Admin_boundaries",
                                                "gadm36_levels_gpkg",
                                                "gadm36_levels_continents.gpkg"))
    global_country_info = global_country_info.to_crs(epsg=4326)
    global_country_info = global_country_info.explode(ignore_index=True)
    global_country_info = global_country_info.sort_values(by="CONTINENT",ascending=True)
    # print (global_country_info)

    
    nodes["node_id"] = nodes.progress_apply(lambda x:"_".join(x["node_id"].split("_")[1:]),axis=1)
    nodes = nodes[["node_id","geometry"]]

    edges["edge_id"] = edges.progress_apply(lambda x:"_".join(x["edge_id"].split("_")[1:]),axis=1)
    edges["from_node"] = edges.progress_apply(lambda x:"_".join(x["from_node"].split("_")[1:]),axis=1)
    edges["to_node"] = edges.progress_apply(lambda x:"_".join(x["to_node"].split("_")[1:]),axis=1)
    edges = edges[["edge_id","from_node","to_node","highway","surface","maxspeed","lanes","bridge","length_km","geometry"]]

    # Set the crs
    edges = edges.set_crs(epsg=4326)
    nodes = nodes.set_crs(epsg=4326)
    
    nodes, edges = match_nodes_edges_to_countries(nodes,edges,global_country_info)

    print ("Done adding country info attributes")

    #edges.to_file(os.path.join(data_path,"road/africa","africa-roads.gpkg"), layer='edges', driver='GPKG')
    #nodes.to_file(os.path.join(data_path,"road/africa","africa-roads.gpkg"), layer='nodes', driver='GPKG')

    """Assign road attributes"""

    # Calculate and add length of line segments 
    geod = Geod(ellps="WGS84")
    edges['length_m'] = edges.progress_apply(lambda x:float(geod.geometry_length(x.geometry)),axis=1)
    edges = edges.drop(['length_km'],axis=1)

    # Drop geometry for faster processing times
    edges_simple = edges.drop(['geometry'],axis=1)

    # Add road condition and material 
    edges_simple['surface_material'] = edges_simple.progress_apply(lambda x:get_road_condition_surface(x),axis=1)
    edges_simple[['road_cond','material']] = edges_simple['surface_material'].progress_apply(pd.Series)
    edges_simple.drop('surface_material',axis=1,inplace=True)

    # Add number of lanes
    edges_simple['lanes'] = edges_simple.progress_apply(lambda x:get_road_lanes(x),axis=1)

    # Add road width
    width = 6.5 # Default carriageway width in meters for Africa, needs to be generalizable for global
    shoulder = 1.5 # Default shoulder width in meters for Africa, needs to be generalizable for global
    edges_simple['width_m'] = edges_simple.progress_apply(lambda x:float(x.lanes)*width + 2.0*shoulder,axis=1)

    # Assign min and max road speeds
    road_speeds = pd.read_excel(os.path.join(data_path,"road","global_road_speeds.xlsx"),sheet_name="global speeds")
    edges_simple = pd.merge(edges_simple,road_speeds,how="left",left_on=["from_iso"],right_on=["ISO_A3"])
    edges_simple["min_max_speed"] = edges_simple.progress_apply(lambda x:assign_road_speeds(x),axis=1)
    edges_simple[["min_speed","max_speed"]] = edges_simple["min_max_speed"].progress_apply(pd.Series)
    edges_simple.drop(["min_max_speed","maxspeed"]+road_speeds.columns.values.tolist(),axis=1,inplace=True)

    print("Done adding road attributes")

    """Assign cost attributes"""

    # Assign rehabilitation costs
    rehab_costs = pd.read_excel(os.path.join(data_path,"costs","rehabilitation_costs.xlsx"), sheet_name = "road_costs")
    edges_simple["rehab_costs"] = edges_simple.progress_apply(lambda x:get_rehab_costs(x,rehab_costs),axis=1)
    edges_simple[["cost_min","cost_max","cost_unit"]] = edges_simple["rehab_costs"].progress_apply(pd.Series)
    edges_simple.drop("rehab_costs",axis=1,inplace=True)

    # Assign tariff costs 
    cost_data = pd.read_csv(os.path.join(data_path,"costs","transport_costs.csv"))
    cost_data = cost_data.loc[cost_data['transport'] == "road"]
    cost_data.rename(columns = {'cost_km':'tariff_cost'}, inplace = True)

    edges_simple = pd.merge(edges_simple,cost_data[["from_iso3","tariff_cost"]],how="left",left_on=["from_iso"],right_on=["from_iso3"])

    edges_simple["min_tariff"] = edges_simple.progress_apply(lambda x:float(x.tariff_cost) - (float(x.tariff_cost)*0.2),axis=1)
    edges_simple["max_tariff"] = edges_simple.progress_apply(lambda x:float(x.tariff_cost) + (float(x.tariff_cost)*0.2),axis=1)
    edges_simple.drop(["tariff_cost","from_iso3"],axis=1,inplace=True)
    edges_simple["tariff_cost_unit"] = "USD/ton-km"

    # Assign flow costs    
    time_cost_factor = 0.49
    edges_simple["min_flow_cost"] = (time_cost_factor*edges["length_m"]/1000)/edges_simple["max_speed"] + (edges_simple["min_tariff"]*edges_simple["length_m"]/1000)
    edges_simple["max_flow_cost"] = (time_cost_factor*edges["length_m"]/1000)/edges_simple["min_speed"] + (edges_simple["max_tariff"]*edges_simple["length_m"]/1000)
    edges_simple["flow_cost_unit"] = "USD/ton"

    print("Done adding cost attributes")
    
    # Prepare for export and finish
    edges = edges_simple.merge(edges[["edge_id","geometry"]],how = "left", on = "edge_id")
    edges = gpd.GeoDataFrame(edges,geometry="geometry",crs="EPSG:4326")
    
    # Add the component column
    edges, nodes = components(edges,nodes)
    print("Done adding components")

    print("Ready to export")
    edges.to_file(os.path.join(data_path,"road/africa","africa-roads-modified.gpkg"), layer='edges', driver='GPKG')
    nodes.to_file(os.path.join(data_path,"road/africa","africa-roads-modified.gpkg"), layer='nodes', driver='GPKG')

    print("Done.")
    ############################################################################################################
    # edges = gpd.read_file(os.path.join(data_path,"africa/networks","africa_roads_modified.gpkg"), layer='edges')
    # countries = ["KEN","TZA","UGA","ZMB"]
    # border_countires = ["ETH","SSD","SOM","RWA","BDI","MWI","MOZ","COD","ZWE","AGO","NAM","BWA"]
    # eac_edges = edges[edges["from_iso"].isin(countries) | edges["to_iso"].isin(countries)]
    # rest_edges = edges[~edges["edge_id"].isin(eac_edges["edge_id"].values.tolist())]
    # border_edges = rest_edges[rest_edges["from_iso"].isin(border_countires) | rest_edges["to_iso"].isin(border_countires)]
    # rest_edges = rest_edges[~rest_edges["edge_id"].isin(border_edges["edge_id"].values.tolist())]
    # border_edges = border_edges[border_edges["highway"].isin(["trunk","motorway","primary","secondary"])]
    # rest_edges = rest_edges[rest_edges["highway"].isin(["trunk","motorway","primary"])]
    # edges = gpd.GeoDataFrame(pd.concat([eac_edges,border_edges,rest_edges],axis=0,ignore_index=True),geometry="geometry",crs="EPSG:4326")
    # print (edges)

    # nodes = gpd.read_file(os.path.join(data_path,"africa/networks","africa_roads_modified.gpkg"), layer='nodes', driver='GPKG')
    # print (nodes)
    # edges, nodes = components(edges,nodes)

    # # edges = edges[["from_node","to_node","edge_id","from_iso","to_iso","highway","min_flow_cost","max_flow_cost","geometry"]]
    # network_edges = edges[["from_node","to_node","edge_id"]]
    # G = ig.Graph.TupleList(network_edges.itertuples(index=False), edge_attrs=list(network_edges.columns)[2:])
    # A = sorted(G.clusters().subgraphs(),key=lambda l:len(l.es['edge_id']),reverse=True)
    # connected_edges = A[0].es["edge_id"]
    # edges[edges["edge_id"].isin(connected_edges)].to_file(os.path.join(data_path,"africa/networks",
    #                                                                 "africa_roads_connected.gpkg"), layer='edges', driver='GPKG')
    # connected_nodes = [x['name'] for x in A[0].vs]
    # nodes[nodes["node_id"].isin(connected_nodes)].to_file(os.path.join(data_path,"africa/networks",
    #                                                                 "africa_roads_connected.gpkg"), layer='nodes', driver='GPKG')


    # edges = gpd.read_file(os.path.join(data_path,"africa/networks",
    #                                 "africa_roads_connected.gpkg"), layer='edges')
    # time_cost_factor = 0.49
    # edges["min_flow_cost"] = time_cost_factor*edges["length_km"]/edges["max_speed"] + edges["min_tariff"]*edges["length_km"]
    # edges["max_flow_cost"] = time_cost_factor*edges["length_km"]/edges["min_speed"] + edges["max_tariff"]*edges["length_km"]
    # # edges["flow_cost_unit"] = "USD/ton"
    # edges.to_file(os.path.join(data_path,"africa/networks",
    #                            "africa_roads_connected.gpkg"), layer='edges', driver='GPKG')


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
