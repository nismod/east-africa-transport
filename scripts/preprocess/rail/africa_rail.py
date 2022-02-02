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
from shapely.geometry import Point, shape, mapping
from boltons.iterutils import pairwise
from tqdm import tqdm
tqdm.pandas()
from utils import *

def match_edges(edge_dataframe,buffer_dataframe,buffer_id,
                geom_buffer=10,fraction_intersection=0.95,length_intersected=100,save_buffer_file=False):
    # print (nwa_edges)
    buffer_dataframe['geometry'] = buffer_dataframe.geometry.progress_apply(lambda x: x.buffer(geom_buffer))
    
    # Save the result to sense check by visual inspection on QGIS. Not a necessary step 
    if save_buffer_file is not False:
        buffer_dataframe.to_file(save_buffer_file,layer=f'buffer_{geom_buffer}',driver='GPKG')

    edges_matches = gpd.sjoin(edge_dataframe,buffer_dataframe, how="inner", op='intersects').reset_index()
    if len(edges_matches.index) > 0:
        buffer_dataframe.rename(columns={'geometry':'buffer_geometry'},inplace=True)
        edges_matches = pd.merge(edges_matches,buffer_dataframe[[buffer_id,"buffer_geometry"]],how='left',on=[buffer_id])
        
        # Find the length intersected and its percentage as the length of the road segment and the NWA road segment
        edges_matches['length_intersected'] = edges_matches.progress_apply(
                                lambda x: (x.geometry.intersection(x.buffer_geometry).length),
                                axis=1)
        edges_matches['fraction_intersection'] = edges_matches.progress_apply(
                                lambda x: (x.geometry.intersection(x.buffer_geometry).length)/x.geometry.length if x.geometry.length > 0 else 1.0,
                                axis=1)
        edges_matches['fraction_buffer'] = edges_matches.progress_apply(
                                lambda x: (x.geometry.intersection(x.buffer_geometry).length)/x['buffer_length'] if x['buffer_length'] > 0 else 0.0,
                                axis=1)

        edges_matches.drop(['buffer_geometry'],axis=1,inplace=True)
        
        # Filter out the roads whose 95%(0.95) or over 100-meters length intersects with the buffer  
        # return edges_matches[
        #                 (edges_matches['fraction_intersection']>=fraction_intersection
        #                 ) | (edges_matches['length_intersected']>=length_intersected)]
        return edges_matches
    else:
        return pd.DataFrame()

def line_length_km(line, ellipsoid='WGS-84'):
    """Length of a line in meters, given in geographic coordinates.

    Adapted from https://gis.stackexchange.com/questions/4022/looking-for-a-pythonic-way-to-calculate-the-length-of-a-wkt-linestring#answer-115285

    Args:
        line: a shapely LineString object with WGS-84 coordinates.

        ellipsoid: string name of an ellipsoid that `geopy` understands (see http://geopy.readthedocs.io/en/latest/#module-geopy.distance).

    Returns:
        Length of line in kilometers.
    """
    if line.geometryType() == 'MultiLineString':
        return sum(line_length_km(segment) for segment in line)

    return sum(
        distance.distance(tuple(reversed(a)), tuple(reversed(b)),ellipsoid=ellipsoid).km
        for a, b in pairwise(line.coords)
    )

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

        df.rename(columns=dict((g,f'{quant}_{g}') for g in grouped_columns),inplace=True)
        df_list.append(df)
    return pd.concat(df_list,axis=1).reset_index()

def get_road_condition_material(x):
    if x.material in [r"^\s+$",'','nan','None','none']:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 'paved','asphalt'
        else:
            return 'unpaved','gravel'
    elif x.material == 'paved':
        return x.material, 'asphalt'
    elif x.material == 'unpaved':
        return x.material, 'gravel'
    elif x.material in ('asphalt','concrete'):
        return 'paved',x.material
    else:
        return 'unpaved',x.material

def get_road_width(x,width,shoulder):
    if x.lanes == 0:
        if x.highway in ('motorway','motorway_link','trunk','trunk_link','primary','primary_link'):
            return 2.0*width + 2.0*shoulder
        else:
            return 1.0*width + 2.0*shoulder
    else:
        return float(x.lanes)*width + 2.0*shoulder

def get_road_lanes(x):
    if x.lanes == 0:
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

def match_nodes_edges_to_countries(nodes,edges,countries,epsg=4326):
    old_nodes = nodes.copy()
    old_nodes.drop("geometry",axis=1,inplace=True)
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
    nodes = pd.merge(nodes[["node_id","iso_code","CONTINENT","geometry"]],old_nodes,how="left",on=["node_id"])
    nodes["old_node_id"] = nodes["node_id"]
    nodes = gpd.GeoDataFrame(nodes,geometry="geometry",crs=f"EPSG:{epsg}")
    
    edges = pd.merge(edges,nodes[["node_id","iso_code","CONTINENT"]],how="left",left_on=["from_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"from_iso","CONTINENT":"from_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)
    edges = pd.merge(edges,nodes[["node_id","iso_code","CONTINENT"]],how="left",left_on=["to_node"],right_on=["node_id"])
    edges.rename(columns={"iso_code":"to_iso","CONTINENT":"to_continent"},inplace=True)
    edges.drop("node_id",axis=1,inplace=True)

    nodes["node_id"] = nodes.progress_apply(lambda x:f"{x.iso_code}_{x.node_id}",axis=1)
    edges["from_node"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.from_node}",axis=1)
    edges["to_node"] = edges.progress_apply(lambda x:f"{x.to_iso}_{x.to_node}",axis=1)
    edges["old_edge_id"] = edges["edge_id"]
    edges["edge_id"] = edges.progress_apply(lambda x:f"{x.from_iso}_{x.to_iso}_{x.edge_id}",axis=1)
    
    return nodes, edges

def correct_wrong_assigning(x):
    to_node = "_".join(x.to_node.split("_")[1:])
    return f"{x.to_iso}_{to_node}"

def correct_iso_code(x):
    if str(x["ISO_A3"]) == "-99":
        return x["ADM0_A3"]
    else:
        return x["ISO_A3"]    

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
    if str(tariff).replace(".","").isdigit():
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

def main(config):
    data_path = config['paths']['data']
    
    # nodes = json.load(open(os.path.join(data_path,
    #                         "rail",
    #                         "nodes.geojson")))
    # nodes = convert_json_geopandas(nodes)
    
    # edges = json.load(open(os.path.join(data_path,
    #                         "rail",
    #                         "network.geojson")))
    # edges = convert_json_geopandas(edges)
    
    # # Create network topology
    # network = create_network_from_nodes_and_edges(
    #     nodes,
    #     edges,
    #     "rail"
    # )
    # nodes = network.nodes.copy()
    # edges = network.edges.copy()
    
    # edges["speed_freight"] = edges.progress_apply(lambda x:round(0.001*x["length"]/(x["time_freight"]/60.0),2) if x["time_freight"] > 0 else 30.0,axis=1)
    # edges = edges.set_crs(epsg=4326)
    # nodes = nodes.set_crs(epsg=4326)
        
    # # Store the final road network in geopackage in the processed_path
    # # out_fname = os.path.join(data_path,"rail/africa","africa-rails.gpkg")
    # # network.edges.to_file(out_fname, layer='edges', driver='GPKG')
    # # network.nodes.to_file(out_fname, layer='nodes', driver='GPKG')

    # # print (network.edges)
    # # print (network.nodes)

    """Find the countries of the nodes and assign them to the node ID's
        Accordingly modify the edge ID's as well
    """
    global_country_info = gpd.read_file(os.path.join(data_path,
                                            "Admin_boundaries",
                                            "ne_10m_admin_0_countries",
                                            "ne_10m_admin_0_countries.shp"))[["ADM0_A3","ISO_A3","NAME","CONTINENT","geometry"]]
    global_country_info["ISO_A3"] = global_country_info.progress_apply(lambda x:correct_iso_code(x),axis=1)
    global_country_info = global_country_info.to_crs(epsg=4326)
    global_country_info = global_country_info[global_country_info["CONTINENT"].isin(["Africa"])]
    global_country_info = global_country_info.explode(ignore_index=True)
    global_country_info = global_country_info.sort_values(by="CONTINENT",ascending=True)
    # print (global_country_info)
    country_continent_codes = list(set(zip(
                                        global_country_info["ISO_A3"].values.tolist(),
                                        global_country_info["NAME"].values.tolist(),
                                        global_country_info["CONTINENT"].values.tolist()
                                        )
                                    )
                                )
    # # nodes = gpd.read_file(out_fname,layer='nodes')
    # # nodes = nodes[["node_id","geometry"]]

    # # edges = gpd.read_file(out_fname,layer='edges')

    # # We did not set the crs when we created the network
    # # edges = edges.set_crs(epsg=4326)
    # # nodes = nodes.set_crs(epsg=4326)
    
    # nodes, edges = match_nodes_edges_to_countries(nodes,edges,global_country_info) 
    # edges["length_km"] = edges.progress_apply(lambda x:line_length_km(x.geometry),axis=1)
    # speed_uncertainty = 0.1
    # edges["min_speed"] = (1 - speed_uncertainty)*edges["speed_freight"]
    # edges["max_speed"] = (1 + speed_uncertainty)*edges["speed_freight"]
    out_fname = os.path.join(data_path,"africa/networks","africa_rails_modified.gpkg")
    edges = gpd.read_file(out_fname,layer='edges')
    for c in ["min_tariff","max_tariff","mean_tariff"]:
        if c in edges.columns.values.tolist():
            edges.drop(c,axis=1,inplace=True)
    print (edges)
    cost_data = pd.read_excel(os.path.join(data_path,"costs","Transport_costs.xlsx"),sheet_name="Sheet1",header=[0,1])
    cost_data = cost_data[[('Country','Country'),
                            ('Transport costs (USD/ton-km)','Rail')]]
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
    all_tariffs.to_csv(os.path.join(data_path,"costs","rail_tariffs.csv"),index=False)
    
    edges = pd.merge(edges,all_tariffs,how="left",left_on=["from_iso"],right_on=["iso_code"]).fillna(0.0)
    # edges.drop(["iso_code","mean_tariff"],axis=1,inplace=True)
    edges.drop("iso_code",axis=1,inplace=True)
    # edges = edges.drop_duplicates(subset=["edge_id","from_node","to_node"],keep="first")
    # print (edges)
    edges = gpd.GeoDataFrame(edges,geometry="geometry",crs="EPSG:4326")
    # edges["length_km"] = edges.progress_apply(lambda x:line_length_km(x.geometry),axis=1)
    time_cost_factor = 0.49
    edges["min_flow_cost"] = time_cost_factor*edges["length_km"]/edges["max_speed"] + edges["min_tariff"]*edges["length_km"]
    # edges["max_flow_cost"] = time_cost_factor*edges["length_km"]/edges["min_speed"] + edges["max_tariff"]*edges["length_km"]
    edges["max_flow_cost"] = time_cost_factor*edges["length_km"]/edges["min_speed"] + edges["mean_tariff"]*edges["length_km"]
    edges["flow_cost_unit"] = "USD/ton"


    edges.to_file(out_fname, layer='edges', driver='GPKG')
    # nodes.to_file(out_fname, layer='nodes', driver='GPKG')

    # out_fname = os.path.join(data_path,"africa/networks","africa_rails_modified.gpkg")
    # edges = gpd.read_file(out_fname,layer="edges")
    # time_cost_factor = 0.49
    # edges["min_flow_cost"] = time_cost_factor*edges["length_km"]/edges["max_speed"] + edges["min_tariff"]*edges["length_km"]
    # edges["max_flow_cost"] = time_cost_factor*edges["length_km"]/edges["min_speed"] + edges["max_tariff"]*edges["length_km"]
    # edges.to_file(out_fname, layer='edges', driver='GPKG')


    # east_africa_countries=[
    #     "kenya",
    #     "tanzania",
    #     "uganda",
    #     "zambia"
    # ]
    # country_iso_codes = ["KEN","TZA","UGA","ZMB"]
    # country_iso_list = list(zip(east_africa_countries,country_iso_codes))
    
    # edges = edges.to_crs(epsg=32736)
    # edges["buffer_length"] = edges.progress_apply(lambda x:x.geometry.length,axis=1)
    # edges = edges[["edge_id","buffer_length","geometry"]]
    # country_edges = []
    # for i,(country_i,iso_code_i) in enumerate(country_iso_list):
    #     edges_i = gpd.read_file(os.path.join(data_path,f"{country_i}","networks","rail.gpkg"), layer='edges')
    #     print (edges_i.crs)
    #     if edges_i.crs is None:
    #         edges_i = edges_i.set_crs(epsg=4326)
    #         edges_i = edges_i.to_crs(epsg=32736)
    #     else:
    #         edges_i = edges_i.to_crs(epsg=32736)
    #     edges_i["edge_length"] = edges_i.progress_apply(lambda x:x.geometry.length,axis=1)

    #     country_edges.append(edges_i[["id","edge_length","geometry"]])
        

    # country_edges = gpd.GeoDataFrame(pd.concat(country_edges,
    #                                             axis=0,ignore_index=True),
    #                             geometry="geometry",crs="EPSG:32736")
    # all_edges = country_edges["id"].values.tolist()   
    # edge_matches = match_edges(country_edges,edges,"edge_id")
    # edge_matches = edge_matches.sort_values(by=["fraction_intersection","fraction_buffer"],ascending=[False,False])
    # edge_matches.to_file(os.path.join(data_path,"africa/networks","country-rails-matches.gpkg"), layer='mapped-edges', driver='GPKG')
    # edge_matches = edge_matches.drop_duplicates(subset=["id"],keep="first")
    # edge_matches.to_file(os.path.join(data_path,"africa/networks","country-rails-matches.gpkg"), layer='mapped-edges-unique', driver='GPKG')
    # no_matches = [e for e in all_edges if e not in edge_matches["id"].values.tolist()]
    # country_edges[country_edges["id"].isin(no_matches)].to_file(os.path.join(data_path,
    #                                         "africa/networks","country-rails-matches.gpkg"), 
    #                                         layer='no-matches', driver='GPKG')

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
