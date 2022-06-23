"""Functions for plotting
"""
import os
import sys
import warnings
import geopandas
import pandas
import numpy
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
from plot_utils import *
from east_africa_plotting_attributes import *

AFRICA_GRID_EPSG = 4326

def get_asset_total_damage_values(sector,damage_data_path,
                            damage_string,asset_dataframe,
                            damages_filter_columns,damages_filter_values,
                            damage_groupby,
                            damage_sum_columns,layer_key):
    asset_id_column = sector[f"{layer_key}_id_column"]
    asset_filter_column = sector[f"{layer_key}_damage_filter_column"]
    asset_filter_list = sector[f"{layer_key}_damage_categories"]
    # damages = pd.read_csv(
    #                 os.path.join(
    #                     damage_data_path,
    #                     f"{sector['sector_gpkg'].replace('.gpkg','')}_{sector[f'{layer_key}_layer']}_{damage_string}.csv"
    #                     )
    #                 )
    damages = pd.read_parquet(
                    os.path.join(
                        damage_data_path,
                        "direct_damages_summary",
                        f"{sector['sector']}_{sector['edge_layer']}_{damage_string}.parquet"
                        )
                    )
    
    for d_filter in damages_filter_columns:
        damages[d_filter] = damages[d_filter].apply(str)
    damages = damages.set_index(damages_filter_columns)
    damages = damages[damages.index.isin(damages_filter_values)].reset_index()
    if asset_filter_column is not None:
        asset_ids = asset_dataframe[asset_dataframe[asset_filter_column].isin(asset_filter_list)][asset_id_column].values.tolist()
        damages = damages[damages[asset_id_column].isin(asset_ids)]
    # damages = damages.groupby(
    #                 [asset_id_column] + damage_groupby,dropna=False
    #                 ).agg(
    #                     dict(
    #                         zip(
    #                             damage_sum_columns,["sum"]*len(damage_sum_columns)
    #                             )
    #                         )
    #                     ).reset_index() 
    damages = damages.groupby([asset_id_column] + damage_groupby,dropna=False)[damage_sum_columns].mean().reset_index()
    # print (damages)
    return pd.merge(
                    asset_dataframe[[asset_id_column,sector[f"{layer_key}_classify_column"],"geometry"]],
                    damages,how="left",on=[asset_id_column]).fillna(0)

def line_map_plotting_colors_width(ax,df,weights,column,
                        ax_crs=4326,
                        edge_classify_column=None,
                        edge_categories=["1","2","3","4","5"],
                        edge_colors=['#feb24c','#fd8d3c','#fc4e2a','#e31a1c','#b10026'],
                        edge_labels=[None,None,None,None,None],
                        edge_zorder=[6,7,8,9,10],
                        divisor=1.0,legend_label="Legend",
                        no_value_label="No value",
                        no_value_color="#969696",
                        line_steps=6,
                        width_step=0.02,
                        interpolation="linear",
                        legend_size=8,
                        plot_title=False,
                        significance=0,
                        legend_location='upper right'):
    
    if ax_crs is None or ax_crs == 4326:
        proj = ccrs.PlateCarree()
    else:
        proj = ccrs.epsg(ax_crs)

    layer_details = list(
                        zip(
                            edge_categories,
                            edge_colors,
                            edge_labels,
                            edge_zorder
                            )
                        )
    max_weight = max(weights)
    width_by_range = generate_weight_bins(weights, 
                                width_step=width_step, 
                                n_steps=line_steps,
                                interpolation=interpolation)
    min_width = 0.8*width_step
    min_order = min(edge_zorder)

    if edge_classify_column is None:
        line_geoms_by_category = {j:[] for j in edge_categories + [no_value_label]}
        for record in df.itertuples():
            geom = record.geometry
            val = getattr(record,column)
            buffered_geom = None
            for (i, ((nmin, nmax), width)) in enumerate(width_by_range.items()):
                if val == 0:
                    buffered_geom = geom.buffer(min_width)
                    cat = no_value_label
                    # min_width = width
                    break
                elif nmin <= val and val < nmax:
                    buffered_geom = geom.buffer(width)
                    cat = str(i+1)

            if buffered_geom is not None:
                line_geoms_by_category[cat].append(buffered_geom)
            else:
                print("Feature was outside range to plot", record.Index)

        legend_handles = create_figure_legend(divisor,
                        significance,
                        width_by_range,
                        max_weight,
                        'line',edge_colors,width_step)
        styles = OrderedDict([
            (cat,  
                Style(color=color, zindex=zorder,label=label)) for j,(cat,color,label,zorder) in enumerate(layer_details)
        ] + [(no_value_label,  Style(color=no_value_color, zindex=min_order-1,label=no_value_label))])
    else:
        line_geoms_by_category = OrderedDict([(j,[]) for j in edge_labels + [no_value_label]])
        for j,(cat,color,label,zorder) in enumerate(layer_details):
            # line_geoms_by_category[label] = []
            for record in df[df[edge_classify_column] == cat].itertuples():
                geom = record.geometry
                val = getattr(record,column)
                buffered_geom = None
                geom_key = label
                for (i, ((nmin, nmax), width)) in enumerate(width_by_range.items()):
                    if val == 0:
                        buffered_geom = geom.buffer(min_width)
                        geom_key = no_value_label
                        # min_width = width
                        break
                    elif nmin <= val and val < nmax:
                        buffered_geom = geom.buffer(width)

                if buffered_geom is not None:
                    line_geoms_by_category[geom_key].append(buffered_geom)
                else:
                    print("Feature was outside range to plot", record.Index)

            legend_handles = create_figure_legend(divisor,
                        significance,
                        width_by_range,
                        max_weight,
                        'line',["#023858"]*line_steps,width_step)

        styles = OrderedDict([
            (label,  
                Style(color=color, zindex=zorder,label=label)) for j,(cat,color,label,zorder) in enumerate(layer_details)
        ] + [(no_value_label,  Style(color=no_value_color, zindex=min_order-1,label=no_value_label))])
    
    for cat, geoms in line_geoms_by_category.items():
        # print (cat,geoms)
        cat_style = styles[cat]
        ax.add_geometries(
            geoms,
            crs=proj,
            linewidth=0.0,
            facecolor=cat_style.color,
            edgecolor='none',
            zorder=cat_style.zindex
        )
    
    if plot_title:
        ax.set_title(plot_title, fontsize=9)
    print ('* Plotting ',plot_title)
    first_legend = ax.legend(handles=legend_handles,
                            fontsize=legend_size,
                            title=legend_label,
                            loc=legend_location,
                            prop={'size':8,'weight':'bold'})
    ax.add_artist(first_legend).set_zorder(20)
    legend_from_style_spec(ax, styles,fontsize=legend_size,loc='lower left',zorder=20)
    return ax

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,"climate_scenarios_risk")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)


    admin_boundaries = os.path.join(processed_data_path,
                                    "Admin_boundaries",
                                    "east_africa_admin_levels",
                                    "admin_levels.gpkg")
    lakes_path = os.path.join(processed_data_path,"naturalearth","ne_10m_lakes.shp")

    map_country_codes = country_risk_basemap_attributes()
    sector_details = sector_attributes() 
    damage_string = "EAD_EAEL"
    damage_columns = ["EAD_undefended_mean"]
    damage_groupby = ["hazard","rcp","epoch"]
    damages_filter_columns = ["hazard","rcp","epoch"]
    no_value_string = "No risk/exposure/operation"
    legend_title = "Expected Annual Damages (US$)"

    # hazard = ["river","coastal"]
    hazard = ["river","coastal"]
    rcp = ["4.5","8.5"]

            
    for sector in sector_details:
        if sector["sector"] in ["road"]: #"road","rail"
            map_plot = map_country_codes[4] # regional
            edges = gpd.read_file(os.path.join(
                                    processed_data_path,
                                    "networks",
                                    sector["sector"],
                                    sector["sector_gpkg"]),
                                    layer=sector["edge_layer"])

            if len(edges) > 0:
                    if edges.crs is None:
                        edges = edges.set_crs(epsg=AFRICA_GRID_EPSG)
                    else:
                        edges = edges.to_crs(epsg=AFRICA_GRID_EPSG)

                    damage_data_path = os.path.join(output_data_path,
                                                            "risk_results")
                    for h in hazard:
                        if h == "river":
                            baseyear = "1980"
                        if h == "coastal":
                            baseyear = "hist"

                        tot_damages_filter_values = [
                                                    (h,"baseline",baseyear),
                                                    (h,"4.5","2030"),
                                                    (h,"4.5","2050"),
                                                    (h,"4.5","2080"),
                                                    (h,"8.5","2030"),
                                                    (h,"8.5","2050"),
                                                    (h,"8.5","2080")
                                                    ]
                        tot_edges = get_asset_total_damage_values(sector,
                                                            damage_data_path,damage_string,
                                                            edges,
                                                            damages_filter_columns,
                                                            tot_damages_filter_values,
                                                            damage_groupby,damage_columns,"edge")
                        
                        
                        weights = [
                            getattr(record,"EAD_undefended_mean")
                            for record in tot_edges.itertuples() if getattr(record,"EAD_undefended_mean") > 0
                        ]

                        if weights != []:
                            for r in rcp:
                                print("* Starting sector: "+sector['sector_label']+", hazard: "+h+", rcp: "+r+".")
                                damages_filter_values = [
                                                            (h,"baseline",baseyear),
                                                            (h,r,"2030"),
                                                            (h,r,"2050"),
                                                            (h,r,"2080")
                                                        ]
                                damages_filter_lables = ["Baseline","RCP "+r+" - 2030","RCP "+r+" - 2050","RCP "+r+" - 2080"]
                            
                                countries = geopandas.read_file(admin_boundaries,layer="level0").to_crs(AFRICA_GRID_EPSG)
                                countries = countries[countries["GID_0"].isin(map_plot["boundary_countries"])]
                                
                                lakes = geopandas.read_file(lakes_path).to_crs(AFRICA_GRID_EPSG)
                                regions = geopandas.read_file(admin_boundaries,layer="level1").to_crs(AFRICA_GRID_EPSG)
                                regions = regions[regions["GID_0"].isin(map_plot["center_countries"])]
                                coastal_prov = regions[regions["GID_1"].isin(map_plot["coastal_provinces"])]

                                if h == "river":
                                    bounds = countries[countries["GID_0"].isin(map_plot["center_countries"])].geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
                                    offset = map_plot["offset_river"]
                                    figsize = (14,16)
                                    arrow_location=(0.88,0.08)
                                    scalebar_location=(0.92,0.05)
                                if h == "coastal":
                                    bounds = coastal_prov.geometry.total_bounds # this gives your boundaries of the map as (xmin,ymin,xmax,ymax)
                                    offset = map_plot["offset_coastal"]
                                    figsize = (8,16)
                                    arrow_location=(0.83,0.1)
                                    scalebar_location=(0.87,0.07)
                                bounds = (bounds[0]-offset[0],bounds[2]+offset[1],bounds[1]-offset[2],bounds[3]+offset[3])
                                ax_proj = get_projection(extent=bounds)

                                figsize = (12,12)
                                                            
                                for j in range(len(damages_filter_values)):

                                    fig, ax = plt.subplots(1,1,
                                        subplot_kw={'projection': ax_proj},
                                        figsize=figsize,
                                        dpi=500)

                                    edges_damages = get_asset_total_damage_values(sector,
                                                                damage_data_path,damage_string,
                                                                edges,
                                                                damages_filter_columns,
                                                                [damages_filter_values[j]],
                                                                damage_groupby,damage_columns,"edge")
                                    ax = get_axes(ax,extent=bounds)
                                    plot_basemap(ax, countries,lakes,
                                                regions=regions
                                                )
                                    
                                    scale_bar_and_direction(ax,arrow_location,scalebar_location,scalebar_distance=50)
                                    ax = line_map_plotting_colors_width(
                                                                        ax,edges_damages,weights,"EAD_undefended_mean",
                                                                        legend_label=legend_title,
                                                                        no_value_label=no_value_string,
                                                                        width_step=0.01,
                                                                        interpolation="fisher-jenks",
                                                                        plot_title=f"Expected annual damages to {sector['sector_label']} from {h} flooding",
                                                                        legend_location=map_plot["legend_location"]
                                                                        )
                                    ax.text(
                                            0.02,
                                            0.80,
                                            f"{damages_filter_lables[j]}",
                                            horizontalalignment='left',
                                            transform=ax.transAxes,
                                            size=18,
                                            weight='bold',
                                            zorder=24)                            

                            
                                    save_fig(
                                            os.path.join(
                                                folder_path, 
                                                f"{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{h}_climate_scenarios_{r}_{j}.png"
                                                )
                                            )

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

