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
                                "sector_label":"railways",
                                "edge_layer":"edges",
                                "node_layer":"nodes",
                                "area_layer":None,
                                "edge_id_column":"edge_id",
                                "node_id_column":"node_id",
                                "area_id_column":None,
                                "edge_classify_column":"status",
                                "node_classify_column":None,
                                "area_classify_column":None,
                                "edge_damage_filter_column":"is_current",
                                "node_damage_filter_column":None,
                                "area_damage_filter_column":None,
                                "edge_damage_categories":[True,False],
                                "node_damage_categories":None,
                                "area_damage_categories":None,
                                "edge_categories":["abandoned","construction","disused","open","proposed","rehabilitation"],
                                "node_categories":None,
                                "area_categories":None,
                                "edge_categories_colors":["#e31a1c","#387eb8","#ff7f00","#4eae4a","#727171","#9351a4"],
                                "node_categories_colors":None,
                                "area_categories_colors":None,
                                "edge_categories_labels":["Abandoned","Construction","Disused","Open","Proposed","Rehabilitation"],
                                "node_categories_labels":None,
                                "area_categories_labels":None,
                                "edge_categories_linewidth":[2.0,2.0,2.0,2.0,2.0,2.0],
                                "edge_categories_linestyle":["solid","solid","solid","solid","dashed","solid"],
                                "edge_categories_zorder":[6,9,6,8,7,6],
                                "node_categories_markersize":[10.0],
                                "node_categories_marker":["."],
                                "node_categories_zorder":[11],
                            },
                            {
                                "sector":"road",
                                "sector_gpkg":"road.gpkg",
                                "sector_label":"roads",
                                "edge_layer":"edges",
                                "node_layer":"nodes",
                                "area_layer":None,
                                "edge_id_column":"edge_id",
                                "node_id_column":"node_id",
                                "area_id_column":None,
                                "edge_classify_column":"road_cond", #"highway",
                                "node_classify_column":None,
                                "area_classify_column":None,
                                "edge_damage_filter_column":None,
                                "node_damage_filter_column":None,
                                "area_damage_filter_column":None,
                                "edge_damage_categories":None,
                                "node_damage_categories":None,
                                "area_damage_categories":None,
                                "edge_categories": ["paved","unpaved"], #["motorway","trunk","primary","secondary","tertiary","other"],
                                "node_categories":None,
                                "area_categories":None,
                                "edge_categories_colors":["#0093ca","#d5b43c"],#["#000000","#6a51a3","#ce1256","#f16913","#fdae6b","#fdae6b"],
                                "node_categories_colors":None,
                                "area_categories_colors":None,
                                "edge_categories_labels":["Paved","Unpaved"],
                                                         #["Motorways","Trunk Roads",
                                                         #   "Primary Roads","Secondary Roads",
                                                         #   "Tertiary/Other Roads","Tertiary/Other Roads"],
                                "node_categories_labels":None,
                                "area_categories_labels":None,
                                "edge_categories_linewidth":[1.5,0.8], #[1.5,1.5,1.5,0.8,0.8,0.8],
                                "edge_categories_linestyle":["solid","solid"], #["solid","solid","solid","solid","solid","solid"],
                                "edge_categories_zorder":[10,6],#[10,9,8,7,6,6],
                                "node_categories_markersize":[10.0],
                                "node_categories_marker":".",
                                "node_categories_zorder":[11],
                            },
                            {
                                "sector":"port",
                                "sector_gpkg":"port.gpkg",
                                "sector_label":"ports",
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
                                "sector_label":"airports",
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
                                                "RWA","BDI","MWI","MOZ","COD"],
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
                        "coastal_provinces":["KEN.21_1","KEN.40_1","KEN.14_1","KEN.19_1"],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":(0.01,0.04),
                        "offset_river":(0.3,0.4,0.1,0.6),
                        "offset_coastal":(0,0.5,1.1,-1.1),
                        "save_fig":"kenya-region.png"
                        },
                        {
                        "country":"tanzania",
                        "center_countries":["TZA"],
                        "boundary_countries":["KEN","TZA","UGA","ZMB",
                                                "RWA","BDI","MWI","MOZ","COD"],
                        "coastal_provinces":["TZA.27_1","TZA.20_1","TZA.10_1","TZA.15_1","TZA.2_1",
                                            "TZA.18_1","TZA.19_1","TZA.28_1","TZA.29_1","TZA.30_1"],
                        "country_labels":True,
                        "country_label_offset":{"UGA":-0.02,"All":0.07},
                        "admin_labels":True,
                        "legend_location":(0.01,0.05),
                        "offset_river":(0.8,0.6,0.8,0.8),
                        "offset_coastal":(0,0.5,0,0),
                        "save_fig":"tanzania-region.png"
                        },
                        {
                        "country":"uganda",
                        "center_countries":["UGA"],
                        "boundary_countries":["KEN","TZA","UGA",
                                                "RWA","SSD",
                                                "COD"],
                        "coastal_provinces":[],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":(0.42,0.01),
                        "offset_river":(0.2,0.4,0.4,0.1),
                        "offset_coastal":(0,0,0,0),
                        "save_fig":"uganda-region.png"
                        },
                        {
                        "country":"zambia",
                        "center_countries":["ZMB"],
                        "boundary_countries":["TZA","ZMB",
                                                "COD","MWI","MOZ",
                                                "ZWE","AGO","NAM","BWA"],
                        "coastal_provinces":[],
                        "country_labels":True,
                        "country_label_offset":{"All":0.07},
                        "admin_labels":True,
                        "legend_location":(0.01,0.73),
                        "offset_river":(0.2,0.4,0.5,0.6),
                        "offset_coastal":(0,0,0,0),
                        "save_fig":"zambia-region.png"
                        },
                        {
                        "country":"regional",
                        "center_countries":["KEN","TZA","UGA","ZMB"],
                        "boundary_countries":["KEN","TZA","UGA","ZMB",
                                                "RWA","BDI","ETH","SSD",
                                                "SOM","COD","MWI","MOZ",
                                                "ZWE","AGO","NAM","BWA","CAF"],
                        "coastal_provinces":["KEN.21_1","KEN.40_1","KEN.14_1","KEN.19_1",
                                            "TZA.27_1","TZA.20_1","TZA.10_1","TZA.15_1","TZA.2_1",
                                            "TZA.18_1","TZA.19_1","TZA.28_1","TZA.29_1","TZA.30_1"],
                        "country_labels":True,
                        "country_label_offset":{"KEN":(0,-0.5),
                                                    "TZA":(0,0), 
                                                    "UGA":(0.5,0.5),
                                                    "ZMB":(0,-1),
                                                    "RWA":(0.15,0),
                                                    "BDI":(0,0.10),
                                                    "ETH":(0,0),
                                                    "SSD":(0.25,0),
                                                    "SOM":(-0.3,-0.3),
                                                    "COD":(1.5,-2),
                                                    "MWI":(-0.65,-0.5),
                                                    "MOZ":(2.5,2.5),
                                                    "ZWE":(0,-0.25),
                                                    "AGO":(0.5,0.5),
                                                    "NAM":(-0.15,-0.15),
                                                    "BWA":(1,-0.15),
                                                    "CAF":(1,0),
                                                    "All":(0.07,0.7)},
                        "admin_labels":True,
                        "legend_location":"upper left",
                        "offset_river":(0.2,0.7,0.6,0.2),
                        "offset_coastal":(0.2,0.2,0.6,0.2),
                        "save_fig":"east-africa-region.png"
                        },
                    ]
    return map_country_codes