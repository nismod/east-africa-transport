import os
import sys
import geopandas as gpd
import pandas as pd
from plot_utils import *
    
def sector_attributes():    
    sector_attributes = [
                            {
                                "sector":"rail",
                                "sector_gpkg":"rail.gpkg",
                                "sector_label":"Railways",
                                "edge_layer":"edges",
                                "node_layer":"nodes",
                                "area_layer":None,
                                "edge_id_column":"id",
                                "node_id_column":"id",
                                "area_id_column":None,
                                "edge_classify_column":"is_current",
                                "node_classify_column":None,
                                "area_classify_column":None,
                                "edge_damage_filter_column":"is_current",
                                "node_damage_filter_column":None,
                                "area_damage_filter_column":None,
                                "edge_damage_categories":[True,False],
                                "node_damage_categories":None,
                                "area_damage_categories":None,
                                "edge_categories":[True,False],
                                "node_categories":None,
                                "area_categories":None,
                                "edge_categories_colors":["#238b45","#969696"],
                                "node_categories_colors":None,
                                "area_categories_colors":None,
                                "edge_categories_labels":["Functional","Non-Functional"],
                                "node_categories_labels":None,
                                "area_categories_labels":None,
                                "edge_categories_linewidth":[2.0,2.0],
                                "edge_categories_zorder":[10,9],
                                "node_categories_markersize":[10.0],
                                "node_categories_marker":["."],
                                "node_categories_zorder":[11],
                            },
                            {
                                "sector":"road",
                                "sector_gpkg":"road.gpkg",
                                "sector_label":"Roads",
                                "edge_layer":"edges",
                                "node_layer":"nodes",
                                "area_layer":None,
                                "edge_id_column":"edge_id",
                                "node_id_column":"node_id",
                                "area_id_column":None,
                                "edge_classify_column":"highway",
                                "node_classify_column":None,
                                "area_classify_column":None,
                                "edge_damage_filter_column":None,
                                "node_damage_filter_column":None,
                                "area_damage_filter_column":None,
                                "edge_damage_categories":None,
                                "node_damage_categories":None,
                                "area_damage_categories":None,
                                "edge_categories":["motorway","trunk","primary","secondary","tertiary","other"],
                                "node_categories":None,
                                "area_categories":None,
                                "edge_categories_colors":["#000000","#6a51a3","#ce1256","#f16913","#fdae6b","#fdae6b"],
                                "node_categories_colors":None,
                                "area_categories_colors":None,
                                "edge_categories_labels":["Motorways","Trunk Roads",
                                                            "Primary Roads","Secondary Roads",
                                                            "Tertiary/Other Roads","Tertiary/Other Roads"],
                                "node_categories_labels":None,
                                "area_categories_labels":None,
                                "edge_categories_linewidth":[1.5,1.5,1.5,0.8,0.8,0.8],
                                "edge_categories_zorder":[10,9,8,7,6,6],
                                "node_categories_markersize":[10.0],
                                "node_categories_marker":".",
                                "node_categories_zorder":[11],
                            },
                            {
                                "sector":"port",
                                "sector_gpkg":"port.gpkg",
                                "sector_label":"Ports",
                                "edge_layer":None,
                                "node_layer":None,
                                "edge_id_column":None,
                                "node_id_column":None,
                                "area_id_column":"node_id",
                                "area_layer":"areas",
                                "edge_damage_filter_column":None,
                                "node_damage_filter_column":None,
                                "area_damage_filter_column":None,
                                "edge_damage_categories":None,
                                "node_damage_categories":None,
                                "area_damage_categories":None,
                                "edge_classify_column":None,
                                "node_classify_column":None,
                                "area_classify_column":"category",
                                "edge_categories":None,
                                "node_categories":None,
                                "area_categories":["transport"],
                                "edge_categories_colors":None,
                                "node_categories_colors":None,
                                "area_categories_colors":["#08306b"],
                                "edge_categories_labels":None,
                                "node_categories_labels":None,
                                "area_categories_labels":["PORT AREAS"],
                                "edge_categories_linewidth":None,
                                "edge_categories_zorder":None,
                                "node_categories_markersize":[15.0],
                                "node_categories_marker":["o"],
                                "node_categories_zorder":[11],
                            },
                            {
                                "sector":"air",
                                "sector_gpkg":"airport.gpkg",
                                "sector_label":"Airports",
                                "edge_layer":None,
                                "node_layer":None,
                                "area_layer":"areas",
                                "edge_id_column":None,
                                "node_id_column":None,
                                "area_id_column":"node_id",
                                "edge_damage_filter_column":None,
                                "node_damage_filter_column":None,
                                "area_damage_filter_column":None,
                                "edge_damage_categories":None,
                                "node_damage_categories":None,
                                "area_damage_categories":None,
                                "edge_classify_column":None,
                                "node_classify_column":None,
                                "area_classify_column":"category",
                                "edge_categories":None,
                                "node_categories":None,
                                "area_categories":["transport"],
                                "edge_categories_colors":None,
                                "node_categories_colors":None,
                                "area_categories_colors":["#8c510a"],
                                "edge_categories_labels":None,
                                "node_categories_labels":None,
                                "area_categories_labels":["AIRPORT AREAS"],
                                "edge_categories_linewidth":None,
                                "edge_categories_zorder":None,
                                "node_categories_markersize":[15.0],
                                "node_categories_marker":["o"],
                                "node_categories_zorder":[11],
                            },
                            
                        ]

    return sector_attributes

def country_basemap_attributes():
    map_country_codes = [
                        {
                        "country":"kenya",
                        "center_countries":["KEN"],
                        "boundary_countries":["KEN","TZA","UGA",
                                                "ETH","SSD",
                                                "SOM"],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":"lower left",
                        "save_fig":"kenya-region.png"
                        },
                        {
                        "country":"tanzania",
                        "center_countries":["TZA"],
                        "boundary_countries":["KEN","TZA","UGA","ZMB",
                                                "RWA","BDI","MWI","MOZ"],
                        "country_labels":True,
                        "country_label_offset":{"UGA":-0.02,"All":0.07},
                        "admin_labels":True,
                        "legend_location":"lower left",
                        "save_fig":"tanzania-region.png"
                        },
                        {
                        "country":"uganda",
                        "center_countries":["UGA"],
                        "boundary_countries":["KEN","TZA","UGA",
                                                "RWA","SSD",
                                                "COD"],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":"upper left",
                        "save_fig":"uganda-region.png"
                        },
                        {
                        "country":"zambia",
                        "center_countries":["ZMB"],
                        "boundary_countries":["TZA","ZMB",
                                                "COD","MWI","MOZ",
                                                "ZWE","AGO","NAM","BWA"],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":"upper left",
                        "save_fig":"zambia-region.png"
                        },
                    ]
    return map_country_codes

def country_risk_basemap_attributes():
    map_country_codes = [
                        {
                        "country":"kenya",
                        "center_countries":["KEN"],
                        "boundary_countries":["KEN","TZA","UGA",
                                                "ETH","SSD",
                                                "SOM"],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":"upper right",
                        "save_fig":"kenya-region.png"
                        },
                        {
                        "country":"tanzania",
                        "center_countries":["TZA"],
                        "boundary_countries":["KEN","TZA","UGA","ZMB",
                                                "RWA","BDI","MWI","MOZ"],
                        "country_labels":True,
                        "country_label_offset":{"UGA":-0.02,"All":0.07},
                        "admin_labels":True,
                        "legend_location":"upper right",
                        "save_fig":"tanzania-region.png"
                        },
                        {
                        "country":"uganda",
                        "center_countries":["UGA"],
                        "boundary_countries":["KEN","TZA","UGA",
                                                "RWA","SSD",
                                                "COD"],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":"upper right",
                        "save_fig":"uganda-region.png"
                        },
                        {
                        "country":"zambia",
                        "center_countries":["ZMB"],
                        "boundary_countries":["TZA","ZMB",
                                                "COD","MWI","MOZ",
                                                "ZWE","AGO","NAM","BWA"],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":"upper right",
                        "save_fig":"zambia-region.png"
                        },
                    ]
    return map_country_codes