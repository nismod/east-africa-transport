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
from boltons.iterutils import pairwise
import igraph as ig
import networkx
from tqdm import tqdm
tqdm.pandas()
from utils import *

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

def mean_min_max(dataframe,grouping_by_columns,grouped_columns):
    quantiles_list = ['mean','min','max']
    df_list = []
    for quant in quantiles_list:
        if quant == 'mean':
            # print (dataframe)
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].mean()
        elif quant == 'min':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].min()
        elif quant == 'max':
            df = dataframe.groupby(grouping_by_columns,dropna=False)[grouped_columns].max()

        df.rename(columns=dict((g,'{}_{}'.format(g,quant)) for g in grouped_columns),inplace=True)
        df_list.append(df)
    return pd.concat(df_list,axis=1).reset_index()

def get_road_condition_surface(x):
    if not x.surface:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
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

def get_road_width(x,width,shoulder):
    if not x.lanes:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 2.0*width + 2.0*shoulder
        else:
            return 1.0*width + 2.0*shoulder
    else:
        return float(x.lanes)*width + 2.0*shoulder

def get_road_lanes(x):
    if not x.lanes:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 2
        else:
            return 1
    else:
        return x.lanes

def assign_road_speeds(x):
    if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
        return x["Highway_min"],x["Highway_max"]
    elif x.road_cond == "unpaved":
        return x["Urban_min"],x["Urban_max"]
    else:
        return x["Rural_min"],x["Rural_max"]

def match_nodes_edges_to_countries(nodes,edges,countries):
    nodes_matches = gpd.sjoin(nodes[["node_id","geometry"]],
                                countries, 
                                how="left", op='within').reset_index()
    nodes_matches = nodes_matches[~nodes_matches["ISO_A3"].isna()]
    nodes_matches = nodes_matches[["node_id","ISO_A3","CONTINENT","geometry"]]
    nodes_matches.rename(columns={"ISO_A3":"iso_code"},inplace=True)
    nodes_matches = nodes_matches.drop_duplicates(subset=["node_id"],keep="first")
    
    nodes_unmatched = nodes[~nodes["node_id"].isin(nodes_matches["node_id"].values.tolist())]
    if len(nodes_unmatched.index) > 0:
        nodes_unmatched["iso_code"] = nodes_unmatched.progress_apply(
                                        lambda x:extract_gdf_values_containing_nodes(x,
                                                                countries,
                                                                "ISO_A3"),
                                        axis=1)
        nodes_unmatched["CONTINENT"] = nodes_unmatched.progress_apply(
                                        lambda x:extract_gdf_values_containing_nodes(x,
                                                                countries,
                                                                "CONTINENT"),
                                        axis=1)
        nodes = pd.concat([nodes_matches,nodes_unmatched],axis=0,ignore_index=True)
    else:
        nodes = nodes_matches.copy()
    del nodes_matches,nodes_unmatched
    nodes = gpd.GeoDataFrame(nodes[["node_id","iso_code","CONTINENT","geometry"]],geometry="geometry",crs="EPSG:4326")
    
    edges = pd.merge(edges,nodes[["node_id","iso_code","CONTINENT"]],how="left",left_on=["from_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"from_iso","CONTINENT":"from_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)
    edges = pd.merge(edges,nodes[["node_id","iso_code","CONTINENT"]],how="left",left_on=["to_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"to_iso","CONTINENT":"to_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)

    nodes["old_node_id"] = nodes["node_id"]
    nodes["node_id"] = nodes.progress_apply(lambda x:f"{x.iso_code}_{x.node_id}",axis=1)
    edges["from_node"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.from_node}",axis=1)
    edges["to_node"] = edges.progress_apply(lambda x:f"{x.to_iso}_{x.to_node}",axis=1)
    edges["old_edge_id"] = edges["edge_id"]
    edges["edge_id"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.to_iso}_{x.edge_id}",axis=1)
    
    return nodes, edges

# def correct_iso_code(x):
#     if str(x["ISO_A3"]) == "-99":
#         return x["ADM0_A3"]
#     else:
#         return x["ISO_A3"]    

def match_country_code(x,country_codes):
    country = str(x["Country"]).strip().lower()
    match = [c[0] for c in country_codes if str(c[1]).strip().lower() == country]
    if match:
        return match[0]
    else:
        return "XYZ"

def clean_speeds(speed,speed_unit):
    if str(speed_unit).lower() == "mph":
        speed_factor = 1.61
    else:
        speed_factor = 1.0

    if str(speed).isdigit():
        return speed_factor*float(speed),speed_factor*float(speed)
    elif "-" in str(speed):
        return speed_factor*float(str(speed).split("-")[0].strip()),speed_factor*float(str(speed).split("-")[1].strip())
    else:
        return 0.0,0.0 

def add_country_code_to_costs(x,country_codes):
    country = str(x["Country"]).strip().lower()
    match = [c[0] for c in country_codes if str(c[1]).strip().lower() == country]
    if match:
        return match
    else:
        match = [c[0] for c in country_codes if str(c[1]).strip().lower() in country]
        if match:
            return match
        else:
            match = [c[0] for c in country_codes if str(c[2]).strip().lower() in country]
            if match:
                return match
            else:
                return ["XYZ"]

def add_tariff_min_max(x):
    tariff = x["Tariff"]
    if str(tariff).replace('.','').isdigit():
        return float(tariff),float(tariff)
    elif "-" in str(tariff):
        return float(str(tariff).split("-")[0].strip()),float(str(tariff).split("-")[1].strip())
    else:
        return 0.0,0.0 

def add_road_tariff_costs(x):
    if x.road_cond == "paved":
        return x.tariff_min, x.tariff_mean
    else:
        return x.tariff_mean, x.tariff_max


def main(config):
    incoming_data_path = config['paths']['incoming_data']
    data_path = config['paths']['data']
    
    # africa_roads = gpd.read_parquet(os.path.join(data_path,"road/africa","africa-latest-highway-core.geoparquet"))
    # print (africa_roads)
    # africa_roads["road_id"] = africa_roads.index.values.tolist()
    # africa_roads[["road_id","highway","geometry"]].to_file(os.path.join(data_path,
    #                                                 "road/africa","africa-latest-highway-core.gpkg"),driver="GPKG")
    edges = gpd.read_file((os.path.join(data_path,
                            "road/africa","africa-latest-highway-core.gpkg")))
        
    # From the geopackage file extract relevant roads
    highway_list = ['motorway','motorway_link',
               'trunk','trunk_link',
               'primary','primary_link',
               'secondary','secondary_link',
               'tertiary','tertiary_link']
    edges = edges[edges.highway.isin(highway_list)]
    edges['highway'] = edges.progress_apply(lambda x: x.highway.replace('_link',''),axis=1)

    out_fname = os.path.join(data_path,"road/africa","africa-roads.gpkg")
    
    # Create network topology
    network = create_network_from_nodes_and_edges(
        None,
        edges,
        "road",
        out_fname,
    )

    network.edges = network.edges.set_crs(epsg=4326)
    network.nodes = network.nodes.set_crs(epsg=4326)
        
    # Store the final road network in geopackage in the processed_path
    network.edges.to_file(out_fname, layer='edges', driver='GPKG')
    network.nodes.to_file(out_fname, layer='nodes', driver='GPKG')

    print (network.edges)
    print (network.nodes)

    """Find the countries of the nodes and assign them to the node ID's
        Accordingly modify the edge ID's as well
    """
    #global_country_info = gpd.read_file(os.path.join(data_path,
    #                                        "Admin_boundaries",
    #                                        "ne_10m_admin_0_countries",
    #                                        "ne_10m_admin_0_countries.shp"))[["ADM0_A3","ISO_A3","CONTINENT","geometry"]]
    #global_country_info["ISO_A3"] = global_country_info.progress_apply(lambda x:correct_iso_code(x),axis=1)
    #global_country_info = global_country_info.to_crs(epsg=4326)
    #global_country_info = global_country_info[global_country_info["CONTINENT"].isin(["Africa","Europe","Seven seas (open ocean)"])]
    #global_country_info = global_country_info.explode(ignore_index=True)
    #global_country_info = global_country_info.sort_values(by="CONTINENT",ascending=True)
    ## print (global_country_info)

    global_country_info = gdp.read_file(os.path.join(data_path,
                                                "Admin_boundaries",
                                                "gadm36_levels_gpkg",
                                                "gadm36_levels_continents.gpkg"))
    global_country_info = global_country_info.to_crs(epsg=4326)
    global_country_info = global_country_info.explode(ignore_index=True)
    global_country_info = global_country_info.sort_values(by="CONTINENT",ascending=True)
    # print (global_country_info)

    out_fname = os.path.join(data_path,"road/africa","africa-roads.gpkg")
    nodes = gpd.read_file(out_fname,layer='nodes')
    nodes["node_id"] = nodes.progress_apply(lambda x:"_".join(x["node_id"].split("_")[1:]),axis=1)
    nodes = nodes[["node_id","geometry"]]

    edges = gpd.read_file(out_fname,layer='edges')
    edges["edge_id"] = edges.progress_apply(lambda x:"_".join(x["edge_id"].split("_")[2:]),axis=1)
    edges["from_node"] = edges.progress_apply(lambda x:"_".join(x["from_node"].split("_")[1:]),axis=1)
    edges["to_node"] = edges.progress_apply(lambda x:"_".join(x["to_node"].split("_")[1:]),axis=1)
    edges = edges[["edge_id","from_node","to_node","highway","surface","maxspeed","lanes","bridge","length_km","geometry"]]

    # We did not set the crs when we created the network
    edges = edges.set_crs(epsg=4326)
    nodes = nodes.set_crs(epsg=4326)
    
    nodes, edges = match_nodes_edges_to_countries(nodes,edges,global_country_info)

    edges.to_file(os.path.join(data_path,"road/africa","africa-roads.gpkg"), layer='edges', driver='GPKG')
    nodes.to_file(os.path.join(data_path,"road/africa","africa-roads.gpkg"), layer='nodes', driver='GPKG')
    

    """Road speed assignments
    """
    road_speeds = pd.read_csv(os.path.join(data_path,"road/africa","road_speeds.csv"))
    print (road_speeds)


    global_country_info = gpd.read_file(os.path.join(data_path,
                                            "Admin_boundaries",
                                            "ne_10m_admin_0_countries",
                                            "ne_10m_admin_0_countries.shp"))[["ADM0_A3","ISO_A3","NAME","CONTINENT","geometry"]]
    global_country_info["ISO_A3"] = global_country_info.progress_apply(lambda x:correct_iso_code(x),axis=1)
    # country_codes = list(set(zip(global_country_info["ISO_A3"].values.tolist(),global_country_info["NAME"].values.tolist())))
    country_continent_codes = list(set(zip(
                                        global_country_info["ISO_A3"].values.tolist(),
                                        global_country_info["NAME"].values.tolist(),
                                        global_country_info["CONTINENT"].values.tolist()
                                        )
                                    )
                                )
    road_speeds["ISO_A3"] = road_speeds.progress_apply(lambda x:match_country_code(x,country_continent_codes),axis=1)
    for column in ["Highway","Rural","Urban"]:
        road_speeds["min_max_speed"] = road_speeds.progress_apply(lambda x:clean_speeds(x[column],x["SpeedUnit"]),axis=1)
        road_speeds[[f"{column}_min",f"{column}_max"]] = road_speeds["min_max_speed"].apply(pd.Series)
        road_speeds.drop("min_max_speed",axis=1,inplace=True)

    road_speeds.to_csv('test.csv',index=False)

    mean_speed_continents = []
    for column in ["Highway","Rural","Urban"]:
        for speed_type in ["min","max"]:
            mean_speed = road_speeds[road_speeds[f"{column}_{speed_type}"] > 0]
            mean_speed = mean_speed.groupby("Region")[f"{column}_{speed_type}"].mean().reset_index()
            if len(mean_speed_continents)>0:
                mean_speed_continents = pd.merge(mean_speed_continents,mean_speed,how="left",on=["Region"])
            else:
                mean_speed_continents = mean_speed.copy()
            for i,row in mean_speed.iterrows():
                road_speeds.loc[(
                                (
                                    road_speeds["Region"] == row["Region"]
                                    ) & (
                                    road_speeds[f"{column}_{speed_type}"]==0)
                                    ),f"{column}_{speed_type}"] = round(row[f"{column}_{speed_type}"],2)


    global_speeds = pd.merge(global_country_info[["ISO_A3","CONTINENT"]],road_speeds,how="left",on=["ISO_A3"]).fillna(0)
    no_speeds = global_speeds[global_speeds["Highway_min"] == 0][["ISO_A3","CONTINENT"]]
    no_speeds = pd.merge(no_speeds,mean_speed_continents,how="left",left_on=["CONTINENT"],right_on=["Region"])

    global_speeds = global_speeds[global_speeds["Highway_min"] > 0]
    global_speeds = pd.concat([global_speeds,no_speeds],axis=0,ignore_index=True)

    edges = pd.merge(edges,global_speeds,how="left",left_on=["from_iso"],right_on=["ISO_A3"])
    edges["min_max_speed"] = edges.progress_apply(lambda x:assign_road_speeds(x),axis=1)
    edges[["min_speed","max_speed"]] = edges["min_max_speed"].apply(pd.Series)
    edges.drop(["min_max_speed"]+global_speeds.columns.values.tolist(),axis=1,inplace=True)
    edges = edges.drop_duplicates(subset=["edge_id","from_node","to_node"],keep="first")
    print (edges)

    """Add attributes
    """
    width = 6.5 # Default carriageway width in meters
    shoulder = 1.5

    edges['surface_material'] = edges.progress_apply(lambda x:get_road_condition_surface(x),axis=1)
    edges[['road_cond','material']] = edges['surface_material'].apply(pd.Series)
    edges.drop('surface_material',axis=1,inplace=True)
    edges['width_m'] = edges.progress_apply(lambda x:get_road_width(x,width,shoulder),axis=1)
    edges['lanes'] = edges.progress_apply(lambda x:get_road_lanes(x),axis=1)

    # Set projection systems find the actual road lengths in meters
    # Length may be invalid for a geographic CRS using degrees as units; must project geometries to a planar CRS
    # EPSG 32736 works for Burundi, Eswatini, Kenya, Malawi, Mozambique, Rwanda, South Africa, Tanzania, Uganda, Zambia, Zimbabwe
    # Use https://epsg.io/ to find for other areas 
    
    edges = edges.to_crs(epsg=32736)
    edges['road_length_m'] = edges.progress_apply(lambda x:x.geometry.length,axis=1)
    edges = edges.to_crs(epsg=4326)

    """Assign rehabilitation costs
    """

    ### replace costs_road.py script 

    """Assign tarriff and flow costs
    """
    edges = gpd.read_file(os.path.join(data_path,"africa/networks",
                                    "africa_roads_connected.gpkg"), layer='edges')
    cost_data = pd.read_excel(os.path.join(data_path,"costs","Transport_costs.xlsx"),sheet_name="Sheet1",header=[0,1])
    cost_data = cost_data[[('Country','Country'),
                            ('Transport costs (USD/ton-km)','Road')]]
    cost_data.columns = ["Country","Tariff"]
    cost_data["ISO_A3"] = cost_data.progress_apply(lambda x:add_country_code_to_costs(x,country_continent_codes),axis=1)
    cost_data["tariff_min_max"] = cost_data.progress_apply(lambda x:add_tariff_min_max(x),axis=1)
    cost_data[["tariff_min","tariff_max"]] = cost_data["tariff_min_max"].apply(pd.Series)
    
    all_tariffs = []
    for row in cost_data.itertuples():
        if row.tariff_max > 0:
            all_tariffs += list(zip(row.ISO_A3,
                                    [row.tariff_min]*len(row.ISO_A3)
                                    )
                            )
            all_tariffs += list(zip(row.ISO_A3,
                                    [row.tariff_max]*len(row.ISO_A3)
                                    )
                            )
    all_iso_codes = list(set(edges["from_iso"].values.tolist()))
    all_tariffs_codes = list(set([t[0] for t in all_tariffs]))
    tariff_xyz = [t[1] for t in all_tariffs if t[0] == "XYZ"]
    for iso in all_iso_codes:
        if iso not in all_iso_codes:
            all_tariffs += list(zip([iso]*len(tariff_xyz),
                                    tariff_xyz
                                    )
                            )
    all_tariffs = pd.DataFrame(all_tariffs,columns=["iso_code","tariff"])
    all_tariffs = mean_min_max(all_tariffs,["iso_code"],["tariff"])
    all_tariffs.to_csv(os.path.join(data_path,"costs","road_tariffs.csv"),index=False)

    edges = pd.merge(edges,all_tariffs,how="left",left_on=["from_iso"],right_on=["iso_code"]).fillna(0.0)
    edges["tariff_costs"] = edges.progress_apply(lambda x:add_road_tariff_costs(x),axis=1)
    edges.drop(all_tariffs.columns.values.tolist(),axis=1,inplace=True)
    edges[["min_tariff","max_tariff"]] = edges["tariff_costs"].apply(pd.Series)
    edges.drop("tariff_costs",axis=1,inplace=True)
    edges = edges.drop_duplicates(subset=["edge_id","from_node","to_node"],keep="first")
    # print (edges)
    # edges["min_tariff"] = edges.progress_apply(lambda x:min(x.min_tariff,0.08),axis=1)
    # edges["max_tariff"] = edges.progress_apply(lambda x:min(x.max_tariff,0.10),axis=1)
    edges = gpd.GeoDataFrame(edges,geometry="geometry",crs="EPSG:4326")
    
    time_cost_factor = 0.49
    edges["min_flow_cost"] = time_cost_factor*edges["length_km"]/edges["max_speed"] + edges["min_tariff"]*edges["length_km"]
    edges["max_flow_cost"] = time_cost_factor*edges["length_km"]/edges["min_speed"] + edges["max_tariff"]*edges["length_km"]
    edges["flow_cost_unit"] = "USD/ton"

    edges, nodes = components(edges,nodes)

    edges = gpd.GeoDataFrame(edges,geometry="geometry",crs="EPSG:4326")
    edges.to_file(os.path.join(data_path,"africa/networks","africa_roads_connected.gpkg"), layer='edges', driver='GPKG')

    nodes = gpd.read_file(os.path.join(data_path,"road/africa","africa-roads-modified.gpkg"), layer='nodes-v2')
    nodes.to_file(os.path.join(data_path,"africa/networks","africa_roads_modified.gpkg"), layer='nodes', driver='GPKG')

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
