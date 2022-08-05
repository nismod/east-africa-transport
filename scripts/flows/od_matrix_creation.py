"""Dissagregate OD matrix for air flows to node pairs

"""
import sys
import os

import pandas as pd
import geopandas as gpd
import fiona
from collections import defaultdict
from shapely.geometry import shape, mapping
pd.options.mode.chained_assignment = None  # default='warn'
# import warnings
# warnings.simplefilter(action='ignore', category=SettingWithCopyWarning)
import numpy as np
from analysis_utils import *
from tqdm import tqdm
tqdm.pandas()

def assign_sectors_from_industries(x):
    if x.Industries in (1,2):
        return 'A'
    elif x.Industries == 3:
        return 'B'
    else:
        return 'C'  

def partition_import_export_flows_to_nodes(trade_node_od,node_dataframe,flow_dataframe,iso_countries,flow_type,mode_type):
    for iso_code in iso_countries:
        if flow_type == "import":
            node_df = node_dataframe[node_dataframe["iso_code"] == iso_code][["node_id","iso_code","import"]]
            node_df["import_fraction"] = node_df["import"]/node_df["import"].sum()
            iso_flow = "iso3_D"
            trade_fraction = "import_fraction"
            iso_node = "iso3_O"
        else:
            node_df = node_dataframe[node_dataframe["iso_code"] == iso_code][["node_id","iso_code","export"]] 
            node_df["export_fraction"] = node_df["export"]/node_df["export"].sum()
            iso_flow = "iso3_O"
            trade_fraction = "export_fraction"
            iso_node = "iso3_D"

        if mode_type == "air":
            flow_values = ["q_air_predict","v_air_predict"]
        else:
            flow_values = ["q_sea_predict","v_sea_predict"]


        # imports and exports
        trade_flows = flow_dataframe[
                            flow_dataframe[iso_flow] == iso_code
                            ].groupby([iso_flow,"sector"])[flow_values].sum().reset_index()
        node_df = pd.merge(trade_flows, 
                          node_df[["node_id","iso_code",trade_fraction]], 
                          left_on=iso_flow, 
                          right_on="iso_code")

        # node_df["q_air_predict_road"] = node_df["q_air_predict"]*node_df["import_fraction"]
        # node_df["v_air_predict_road"] = node_df["v_air_predict"]*node_df["import_fraction"]

        node_df[["tonnage","value_usd"]] = node_df[flow_values].multiply(node_df[trade_fraction],axis="index")

        node_df.drop(columns=flow_values + ["iso_code",trade_fraction],inplace=True)
        node_df[iso_node] = node_df.apply(lambda x: str(x.node_id).split("_")[0],axis=1)
        node_df["trade_type"] = flow_type
        node_df["mode_type"] = mode_type

        trade_node_od.append(node_df)

    return trade_node_od

def route_roads_to_nearest_ports(origins_destinations,network_graph,sort_by="origin_id",cost_function="max_flow_cost"):
    # network_graph = create_multi_modal_network_africa(modes=["road","multi"])
    # destinations = list(set(destinations["node_id"].values.tolist()))
    # origins = list(set(origins["node_id"].values.tolist()))
    flow_paths = network_od_paths_assembly(origins_destinations,
                                network_graph,
                                cost_function)
    flow_paths = flow_paths.sort_values(by="gcost")
    flow_paths = flow_paths.drop_duplicates(subset=[sort_by],keep="first")

    return flow_paths

# def make_od_pairs(nodes, trade_od, weight_col, industry_code, min_value):
#     nodes = nodes[nodes[weight_col] > min_value][["node_id","iso_code",weight_col]]
#     trade_od = trade_od[trade_od["Industries"] == industry_code]
    
#     od_pairs = []
#     for row in trade_od.itertuples():
#         od_nodes = nodes[nodes["iso_code"] == row.iso3_O][["node_id",weight_col]]
#         od_nodes["weight"] = od_nodes[weight_col]/od_nodes[weight_col].sum()
#         od_nodes["tonnage"] = (1.0*row.q_air_predict_road/365.0)*od_nodes["weight"]
#         od_nodes["value_usd"] = (1.0*row.v_air_predict_road/365.0)*od_nodes["weight"]

#         for od in od_nodes.itertuples():
#             if row.trade_type == "imports":
#                 od_pairs.append((row.node_id,od.node_id,row.iso3_O,row.iso3_D,industry_code,od.tonnage,od.value_usd))
#             else:
#                 od_pairs.append((od.node_id,row.node_id,row.iso3_O,row.iso3_D,industry_code,od.tonnage,od.value_usd))

#         print (f"* Done with {row.iso3_O}-{row.iso3_D}")
#     return od_pairs

def estimate_od_values(od_values,flow_columns,weight_columns):
    for i,(fl,wt) in enumerate(list(zip(flow_columns,weight_columns))):
        od_values[
                [f"{fl}_value_usd",f"{fl}_tonnage"
                ]] = od_values[[f"{fl}_value_usd",f"{fl}_tonnage"]].multiply((1.0*od_values[wt])/365.0,axis="index")

    return od_values

def make_od_pairs(od_nodes,
                flow_columns,
                import_weight_columns,
                export_weight_columns,
                sector_countries,
                default_import_columns,default_export_columns,trade_type="import"):
    
    if trade_type == "import":
        od_nodes_sector_countries = od_nodes[od_nodes["iso3_D"].isin(sector_countries)]
        weight_columns_sector_countries = import_weight_columns
        od_nodes_rest = od_nodes[~od_nodes["iso3_D"].isin(sector_countries)]
        weight_columns_rest = default_import_columns
    else:
        od_nodes_sector_countries = od_nodes[od_nodes["iso3_O"].isin(sector_countries)]
        weight_columns_sector_countries = export_weight_columns
        od_nodes_rest = od_nodes[~od_nodes["iso3_O"].isin(sector_countries)]
        weight_columns_rest = default_export_columns

    od_nodes_sector_countries = estimate_od_values(od_nodes_sector_countries,flow_columns,weight_columns_sector_countries)
    od_nodes_rest = estimate_od_values(od_nodes_rest,flow_columns,weight_columns_rest)

    return pd.concat([od_nodes_sector_countries,od_nodes_rest],axis=0,ignore_index=True)

def transform_rows_to_columns(dataframe,index_columns,pivot_column,value_column,pivot_values):
    df = (dataframe.set_index(index_columns).pivot(
                                    columns=pivot_column
                                    )[value_column].reset_index().rename_axis(None, axis=1)).fillna(0)
    df.rename(columns=dict([(p,f"{p}_{value_column}") for p in pivot_values]),inplace=True)
    return df

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    tonnage_threshold = 0.1
    trade_od = pd.read_csv(os.path.join(processed_data_path,
                                        "flow_od_data",
                                        "hvt_trade_2015_modified.csv"))  
    trade_od["sector"] = trade_od.progress_apply(lambda x: assign_sectors_from_industries(x),axis=1)
    trade_od = trade_od.groupby(["iso3_O","iso3_D","sector",
                    "NAME_O","NAME_D","CONTINENT_O",
                    "CONTINENT_D"])["v","q",
                    "v_air_predict","q_air_predict",
                    "v_sea_predict","q_sea_predict",
                    "v_land_predict","q_land_predict"].sum().reset_index()


    hvt_countries = ["KEN","TZA","UGA","ZMB"]
    roads_edges = gpd.read_file(os.path.join(
                        processed_data_path,
                        "networks",
                        "road",
                        "roads.gpkg"), layer='edges')
    hvt_network = roads_edges[
                        (
                            roads_edges["from_iso"].isin(hvt_countries)
                            ) | (
                            roads_edges["to_iso"].isin(hvt_countries)
                        )
                    ][["edge_id","from_iso","to_iso"]]
    del roads_edges
    """Step 1: Partition the flows to the airports in HVT countries 
    """
    air_import_exports = pd.read_excel(os.path.join(processed_data_path,
                                        "flow_od_data",
                                        "airport_stats.xlsx"),
                                sheet_name="Summary")

    od_pairs = []
    airport_countries = list(set(air_import_exports["iso_code"].values.tolist()))
    
    trade_node_od = []
    trade_node_od = partition_import_export_flows_to_nodes(trade_node_od,
                                                            air_import_exports,
                                                            trade_od,
                                                            airport_countries,
                                                            "import","air")
    trade_node_od = partition_import_export_flows_to_nodes(trade_node_od,
                                                            air_import_exports,
                                                            trade_od,
                                                            airport_countries,
                                                            "export","air")
    del air_import_exports
    """Step 2: Partition the flows to the maritime ports in HVT countries 
    """
    port_import_exports = pd.read_excel(os.path.join(processed_data_path,
                                    "flow_od_data",
                                    "hvt_port_import_export_stats.xlsx"),
                                    sheet_name="Sheet1")
    port_import_exports["import"] = port_import_exports["import"] + port_import_exports["transhipment_in"]
    port_import_exports["export"] = port_import_exports["export"] + port_import_exports["transhipment_out"]
    port_countries = list(set(port_import_exports["iso_code"].values.tolist()))

    trade_node_od = partition_import_export_flows_to_nodes(trade_node_od,
                                                            port_import_exports,
                                                            trade_od,
                                                            port_countries,
                                                            "import","port")

    trade_node_od = partition_import_export_flows_to_nodes(trade_node_od,
                                                            port_import_exports,
                                                            trade_od,
                                                            port_countries,
                                                            "export","port")
    del port_import_exports
    trade_node_od = pd.concat(trade_node_od,axis=0,ignore_index=True).fillna(0)

    index_columns = ["iso3_O","iso3_D", "node_id","trade_type","mode_type"]
    sectors = ["A","B","C"]
    trade_node_od_value = transform_rows_to_columns(trade_node_od,index_columns,"sector","value_usd",sectors)
    trade_node_od_tonnage = transform_rows_to_columns(trade_node_od,index_columns,"sector","tonnage",sectors)

    trade_node_od = pd.merge(trade_node_od_value,trade_node_od_tonnage,how="left",on=index_columns)
    del trade_node_od_tonnage, trade_node_od_value
    trade_node_od.to_csv(os.path.join(results_data_path,
                            "flow_paths",
                            "airport_maritimeport_splits.csv"),index=False)

    # trade_node_od = trade_node_od[trade_node_od["tonnage"] > 0]
    country_modes = list(set(zip(trade_node_od["iso3_O"].values.tolist(),
                        trade_node_od["mode_type"].values.tolist())))
    # print (country_modes)

    """Step 3: Partition the flows from the airports and ports to the road nodes in a country
        Airports are serving their own country
        Ports serve their own country and surrounding countries

        Kenya is served by 3 airports and Tanzania is served by 4 ports
            For these two countries first we need to figure out the preferred nearest airport/port  
    """
    population_column = "pop_2020"
    weight_columns = ["pop_2020","mining_area_m2","ag_prod_mt","C","G"]
    road_nodes = gpd.read_file(os.path.join(processed_data_path,
                            "networks",
                            "road",
                            "roads_voronoi.gpkg"),
                        layer="weights")
    road_nodes.drop("geometry",axis=1,inplace=True)
    # road_nodes = road_nodes[road_nodes[population_column] > 0]
    countries_port_partitions = [("KEN","air"),("TZA","port")]
    roads_nearest = [] 
    network_graph = create_multi_modal_network_africa(modes=["road","multi"])
    for i,(hvt,mode) in enumerate(country_modes):
        ports = list(set(trade_node_od[
                            (
                                trade_node_od["iso3_O"] == hvt
                            ) & (
                                trade_node_od["mode_type"] == mode
                            )
                        ]["node_id"].values.tolist()))
        roads = list(set(road_nodes[road_nodes["iso_code"] == hvt]["node_id"].values.tolist()))
        roads_routes = [list(zip([b]*len(roads),roads)) for b in ports]
        roads_routes = [item for sublist in roads_routes for item in sublist]
        roads_routes = pd.DataFrame(roads_routes,columns=["origin_id","destination_id"])
        # print (roads_routes)
        if (hvt,mode) in countries_port_partitions:
            roads_routes = route_roads_to_nearest_ports(roads_routes,network_graph,
                                                    sort_by="destination_id")
            roads_routes.drop("edge_path",axis=1,inplace=True)
        # else:
        #   roads_routes = network_od_paths_assembly(roads_routes,
        #                         network_graph,
        #                         "max_flow_cost")

        # roads_routes["mode_type"] = mode
        roads_nearest.append(roads_routes)

    roads_nearest = pd.concat(roads_nearest,axis=0,ignore_index=True)
    roads_nearest = pd.merge(roads_nearest,
                            road_nodes,
                            how="left",left_on=["destination_id"],right_on=["node_id"])
    roads_nearest.drop("node_id",axis=1,inplace=True)
    # print (roads_nearest)
    roads_nearest["iso3_O"] = roads_nearest.apply(lambda x:x.origin_id.split("_")[0],axis=1)
    roads_nearest["iso3_D"] = roads_nearest.apply(lambda x:x.destination_id.split("_")[0],axis=1)

    roads_nearest = roads_nearest[["origin_id","destination_id","iso3_O","iso3_D"] + weight_columns]
    """Normalise the weights
    """
    for wt in weight_columns:
        roads_nearest[wt] = roads_nearest[wt]/roads_nearest.groupby(["origin_id","iso3_D"])[wt].transform('sum')
    
    rn = roads_nearest.copy()
    rn.columns = ["destination_id","origin_id","iso3_D","iso3_O"] + weight_columns
    
    """Partition OD values
    """
    trade_od_exports = trade_node_od[trade_node_od["trade_type"] == "import"]
    trade_od_exports.rename(columns={"node_id":"origin_id"},inplace=True)
    roads_nearest = pd.merge(roads_nearest,trade_od_exports,how="left",on=["origin_id","iso3_O","iso3_D"])

    sector_columns = ["A","B","C"]
    sector_countries = ["KEN","TZA","ZMB"]
    import_weight_columns = ["pop_2020","C","G"]
    default_import_columns = ["pop_2020"]*len(sector_columns)
    export_weight_columns = ["ag_prod_mt","mining_area_m2","C"]
    default_export_columns = ["ag_prod_mt","mining_area_m2","pop_2020"]
    roads_nearest = make_od_pairs(roads_nearest,
                                sector_columns,
                                import_weight_columns,
                                export_weight_columns,
                                sector_countries,
                                default_import_columns,
                                default_export_columns,
                                trade_type="import")

    od_pairs.append(roads_nearest)
    trade_od_imports = trade_node_od[trade_node_od["trade_type"] == "export"]
    trade_od_imports.rename(columns={"node_id":"destination_id"},inplace=True)
    rn = pd.merge(rn,trade_od_imports,how="left",on=["destination_id","iso3_O","iso3_D"])
    rn = make_od_pairs(rn,
                        sector_columns,
                        import_weight_columns,
                        export_weight_columns,
                        sector_countries,
                        default_import_columns,
                        default_export_columns,
                        trade_type="export")
    od_pairs.append(rn)
    del roads_nearest, rn

    """Step 4: Find road OD pairs
    """
    land_ods = trade_od[trade_od["q_land_predict"] > 0]
    land_ods.rename(columns={"q_land_predict":"tonnage","v_land_predict":"value_usd"},inplace=True)
    index_columns = ["iso3_O","iso3_D"]
    sectors = ["A","B","C"]
    # road_ods_value = transform_rows_to_columns(road_ods,index_columns,"sector","value_usd",sectors)
    # road_ods_tonnage = transform_rows_to_columns(road_ods,index_columns,"sector","tonnage",sectors)
    # road_ods = pd.merge(road_ods_value,road_ods_tonnage,how="left",on=index_columns)
    # del road_ods_tonnage, road_ods_value

    country_limit = 10
    sector_columns = ["A","B","C"]
    sector_countries = ["KEN","TZA","ZMB"]
    import_weight_columns = ["pop_2020","C","G"]
    default_import_columns = ["pop_2020"]*len(sector_columns)
    export_weight_columns = ["ag_prod_mt","mining_area_m2","C"]
    default_export_columns = ["ag_prod_mt","mining_area_m2","pop_2020"]
    column_combinations = list(zip(sector_columns,
                                    import_weight_columns,
                                    export_weight_columns,
                                    default_import_columns,
                                    default_export_columns
                                )
                            )
    road_node_od_pairs = []
    # land_ods = land_ods[land_ods["iso3_O"].isin(["TZA"])]
    for i, (s,iwc,ewc,dic,dec) in enumerate(column_combinations):
        road_ods = land_ods[land_ods["sector"] == s]
        for row in road_ods.itertuples():
            origins = road_nodes[road_nodes["iso_code"] == row.iso3_O]
            origins.rename(columns={"node_id":"origin_id","iso_code":"iso3_O"},inplace=True)
            origins["sector"] = s
            weight_column = ewc
            if row.iso3_O not in sector_countries:
                weight_column = dec
                origins = origins.sort_values(by=weight_column,ascending=False).head(country_limit)
            
            if origins[weight_column].sum() > 0:
                origins["from_tonnage"] = (1.0*row.tonnage/365.0)*origins[weight_column]/origins[weight_column].sum()
                origins["from_value"] = (1.0*row.value_usd/365.0)*origins[weight_column]/origins[weight_column].sum()

                destinations = road_nodes[road_nodes["iso_code"] == row.iso3_D]
                destinations.rename(columns={"node_id":"destination_id","iso_code":"iso3_D"},inplace=True)
                weight_column = iwc
                if row.iso3_D not in sector_countries:
                    weight_column = dic
                    destinations = destinations.sort_values(by=weight_column,ascending=False).head(country_limit)

                if destinations[weight_column].sum():
                    destinations["weight"] = destinations[weight_column]/destinations[weight_column].sum()
                    origins = origins[origins["from_tonnage"] > 0][["origin_id","iso3_O","sector","from_tonnage","from_value"]]
                    destinations = destinations[destinations["weight"] > 0][["destination_id","iso3_D","weight"]]
                    if len(origins.index) > 0 and len(destinations.index) > 0:
                        ods = (origins.assign(dummy=1).merge(destinations.assign(dummy=1), on='dummy').drop('dummy', axis=1))
                        ods = ods[["origin_id","destination_id",
                        			"iso3_O","iso3_D","sector",
                        			"from_tonnage","from_value","weight"]]
                        ods[["tonnage","value_usd"]] = ods[["from_tonnage","from_value"]].multiply(ods["weight"],axis="index")
                        ods = ods[ods["tonnage"] >= tonnage_threshold]
                        if len(ods.index) > 0:
                            if len(origins.index) <= len(destinations.index):
                            	ods = network_od_paths_assembly(ods,network_graph,"max_flow_cost")
                            else:
                            	od_cols = ods.columns.values.tolist()
                            	ods.columns = ["destination_id","origin_id"] + od_cols[2:]
                            	ods = network_od_paths_assembly(ods,network_graph,"max_flow_cost")
                            	od_cols = ods.columns.values.tolist()
                            	ods.columns = ["destination_id","origin_id"] + od_cols[2:]

                            ods["hvt_pass"] = ods.apply(
                                                    lambda x:len(
                                                                hvt_network[
                                                                        hvt_network["edge_id"].isin(x.edge_path)
                                                                        ].index
                                                                ),axis=1)
                            # ods = pd.merge(ods,ods_paths,how="left",on=["origin_id","destination_id"])
                            # print (ods)
                            # del ods_paths
                            road_node_od_pairs.append(ods[ods["hvt_pass"] > 0][["origin_id",
                                                            "destination_id",
                                                            "iso3_O","iso3_D",
                                                            "sector",
                                                            "tonnage","value_usd"]])
                            del ods

            print (f"* Done with {row.iso3_O}-{row.iso3_D} for sector {s}")

    # road_node_od_pairs = pd.DataFrame(road_node_od_pairs,
    #                             columns=["origin_id",
    #                             "destination_id",
    #                             "iso3_O","iso3_D","tonnage","value_usd"])
    road_node_od_pairs = pd.concat(road_node_od_pairs,axis=0,ignore_index=True)
    road_node_od_pairs = road_node_od_pairs.groupby(["origin_id",
                                                    "destination_id",
                                                    "iso3_O",
                                                    "iso3_D",
                                                    "sector"])["tonnage","value_usd"].sum().reset_index()

    index_columns = ["origin_id","destination_id","iso3_O","iso3_D"]
    sectors = ["A","B","C"]
    road_ods_value = transform_rows_to_columns(road_node_od_pairs,index_columns,"sector","value_usd",sectors)
    road_ods_tonnage = transform_rows_to_columns(road_node_od_pairs,index_columns,"sector","tonnage",sectors)
    road_ods = pd.merge(road_ods_value,road_ods_tonnage,how="left",on=index_columns)
    del road_ods_tonnage, road_ods_value
    od_pairs.append(road_ods)
    od_pairs = pd.concat(od_pairs,axis=0,ignore_index=True)
    print (od_pairs)

    sector_value_columns = [f"{s}_value_usd" for s in sector_columns]
    sector_tonnage_columns = [f"{s}_tonnage" for s in sector_columns]
    od_pairs["total_value_usd"] = od_pairs[sector_value_columns].sum(axis=1)
    od_pairs["total_tonnage"] = od_pairs[sector_tonnage_columns].sum(axis=1)

    od_pairs = od_pairs[["origin_id",
                        "destination_id",
                        "iso3_O","iso3_D"
                        ] + sector_value_columns + sector_tonnage_columns + [
                        "total_value_usd",
                        "total_tonnage"]]

    od_pairs[od_pairs["total_tonnage"] >= tonnage_threshold].to_csv(os.path.join(results_data_path,
                                                            "flow_paths",
                                                            "od_matrix_nodes.csv"),index=False)

    od_pairs[od_pairs["total_tonnage"] > 0].to_csv(os.path.join(results_data_path,
                            "flow_paths",
                            "od_matrix_nodes_detailed.csv"),index=False)


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)