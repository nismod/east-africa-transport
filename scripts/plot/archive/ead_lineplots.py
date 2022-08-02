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

def quantiles(dataframe,grouping_by_columns,grouped_columns):
    quantiles_list = ['median','q5','q95']
    df_list = []
    df_columns = []
    for quant in quantiles_list:
        if quant == 'median':
            df = dataframe.groupby(grouping_by_columns)[grouped_columns].quantile(0.5)
        elif quant == 'q5':
            df = dataframe.groupby(grouping_by_columns)[grouped_columns].quantile(0.05)
        elif quant == 'q95':
            df = dataframe.groupby(grouping_by_columns)[grouped_columns].quantile(0.95)

        df.rename(columns=dict((g,f"{g}_{quant}") for g in grouped_columns),inplace=True)
        df_columns += [f"{g}_{quant}" for g in grouped_columns]
        df_list.append(df)
    return pd.concat(df_list,axis=1).reset_index(), df_columns

def filter_asset_total_damage_values(sector,damage_data_path,
                            damage_string,
                            damages_filter_columns,damages_filter_values,
                            damage_groupby,
                            damage_sum_columns,layer_key):
    asset_id_column = sector[f"{layer_key}_id_column"]
    asset_filter_column = sector[f"{layer_key}_damage_filter_column"]
    asset_filter_list = sector[f"{layer_key}_damage_categories"]
    damages = pd.read_csv(
                    os.path.join(
                        damage_data_path,
                        f"{sector['sector_gpkg'].replace('.gpkg','')}_{sector[f'{layer_key}_layer']}_{damage_string}.csv"
                        )
                    )
    for d_filter in damages_filter_columns:
        damages[d_filter] = damages[d_filter].apply(str)
    damages = damages.set_index(damages_filter_columns)
    damages = damages[damages.index.isin(damages_filter_values)].reset_index()

    #damages, damage_sum_columns = quantiles(damages,[asset_id_column] + damage_groupby,damage_sum_columns)

    damages = damages.groupby(
                    damage_groupby,dropna=False
                    ).agg(
                        dict(
                            zip(
                                damage_sum_columns,["sum"]*len(damage_sum_columns)
                                )
                            )
                        ).reset_index() 
    
    min_damages = min(damages[damage_sum_columns].min())
    max_damages = max(damages[damage_sum_columns].max())

    return damages, min_damages, max_damages

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,"ead_epoch")
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)
        
    damage_string = "EAD_EAEL" 
    # damage_string = "EAD" 
    damage_columns = ["EAD_undefended_mean","EAD_undefended_amin","EAD_undefended_amax"]
    # damage_columns = ["EAD_undefended_mean","EAD_undefended_min","EAD_undefended_max"]
    damage_groupby = ["hazard","rcp","epoch"]
    damages_filter_columns = ["hazard","rcp","epoch"]

    hazard = ["coastal","river"]
    years = ["2030","2050","2080"]
    rcp = ["4.5","8.5"]
    rcp_colors = ['#2171b5','#08306b']
    rcp_markers = ['s-','^-']

    sector_details = sector_attributes() 

    for sector in sector_details:
        if sector["sector"] in ["road"]: # ["road", "rail"]
            damage_data_path = os.path.join(output_data_path,
                                                    "risk_results",
                                                    "direct_damages_summary") 
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
                
                tot_damages, min_limits, max_limits = filter_asset_total_damage_values(sector,
                                                        damage_data_path,damage_string,
                                                        damages_filter_columns,
                                                        tot_damages_filter_values,
                                                        damage_groupby,damage_columns,"edge")
                if tot_damages.empty == False:
                    # rps = list(set(tot_damages['rp'].values.tolist()))
                    # figure_texts = ['a.','b.','c.']
                    plot_column = "EAD_undefended"
                    length_factor = 0.000001 # Convert usd to million usd
                    fig, ax = plt.subplots(1,1,
                        figsize=(20,12),
                        dpi=500)
                    # ax.plot(tot_damages[tot_damages['epoch'] == baseyear]['epoch'],
                    #     length_factor*tot_damages[tot_damages['epoch'] == baseyear][f"{plot_column}_mean"],
                    #     'o-',color='#fd8d3c',markersize=10,linewidth=2.0,
                    #     label='Baseline')
                    plt.axhline(y = length_factor*tot_damages[tot_damages['epoch'] == baseyear][f"{plot_column}_mean"].item(), 
                        color="#fd8d3c",
                        linestyle = '-',
                        markersize=10,
                        linewidth=2.0,
                        label='Baseline')
                    for i, (r,m,cl) in enumerate(list(zip(rcp,rcp_markers,rcp_colors))):
                        exp = tot_damages[(tot_damages['rcp'] == r)]
                        ax.plot(exp['epoch'],
                            length_factor*exp[f"{plot_column}_mean"],
                            m,color=cl,markersize=10,linewidth=2.0,
                            label=f"RCP {r} - mean")
                            # label=f"RCP {r} - median")
                        ax.fill_between(exp['epoch'],
                            length_factor*exp[f"{plot_column}_amin"],
                            length_factor*exp[f"{plot_column}_amax"],
                            # length_factor*exp[f"{plot_column}_min"],
                            # length_factor*exp[f"{plot_column}_max"],
                            alpha=0.3,facecolor=cl,
                            label=f"RCP {r} - min-max")
                            # label=f"RCP {r} - Q5-Q95")
                    
                    ax.set_xlabel('Year',fontsize=14,fontweight='bold')
                    ax.set_ylabel('Expected Annual Damage (million USD)',fontsize=14,fontweight='bold')
                    ax.set_ylim(length_factor*min_limits,length_factor*max_limits)
                    ax.tick_params(axis='both', labelsize=14)
                    # ax.set_xticks([t for t in rps])
                    #a x.set_xticklabels([str(t) for t in rps])
                    ax.grid(True)
                    # ax.set_xticks([t for t in list(set(exposures[exposures['year'] == baseyear]['return_period'].values))], 
                        # [str(t) for t in list(set(exposures[exposures['year'] == baseyear]['return_period'].values))])
                    ax.text(
                        0.01,
                        1.015,
                        f"Expected annual damages (million USD) from {h} flooding",
                        horizontalalignment='left',
                        transform=ax.transAxes,
                        size=18,
                        weight='bold')
                    ax.legend(
                        loc='lower left', 
                        bbox_to_anchor=(0,0.763),
                        prop={'size':18,'weight':'bold'})
                    plt.tight_layout()
                    save_fig(
                        os.path.join(
                            folder_path, 
                            f"{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{h}_EAD_lineplot.png"
                        )
                    )
                    plt.close()

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

