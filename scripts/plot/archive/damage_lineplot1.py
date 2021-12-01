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
                        ), 
                    low_memory=False
                    )
    for d_filter in damages_filter_columns:
        damages[d_filter] = damages[d_filter].apply(str)
    damages = damages.set_index(damages_filter_columns)
    damages = damages[damages.index.isin(damages_filter_values)].reset_index()

    damages, damage_sum_columns = quantiles(damages,[asset_id_column] + damage_groupby,damage_sum_columns)
    
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

    map_country_codes = country_risk_basemap_attributes()
    sector_details = sector_attributes() 
    damage_string = "direct_damages" 
    damage_columns = ["direct_damage_cost_mean"] 
    damage_groupby = ["hazard","rcp","rp","epoch"]
    damages_filter_columns = ["hazard","rcp","epoch"]

    hazard = ["river"] # add coastal?
    years = ["2030","2050","2080"]
    rcp = ["4.5","8.5"]
    rcp_colors = ['#2171b5','#08306b']
    rcp_markers = ['s-','^-']

    for sector in sector_details:
        if sector["sector"] in ["road","rail"]:
            for map_plot in map_country_codes:
                    damage_data_path = os.path.join(output_data_path,
                                                            map_plot["country"],    
                                                            "direct_damages_summary") 
                    for h in hazard:
                        tot_damages_filter_values = [
                                                    (h,"baseline","1980"),
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

                        rps = list(set(tot_damages['rp'].values.tolist()))
                        
                        figure_texts = ['a.','b.','c.']
                        plot_column = "direct_damage_cost_mean"
                        baseyear = "1980"
                        length_factor = 0.000001 # Convert usd to million usd
                        fig, ax_plots = plt.subplots(1,3,
                                figsize=(20,12),
                                dpi=500)
                        ax_plots = ax_plots.flatten()
                        j = 0
                        for year in years:
                            ax = ax_plots[j]
                            ax.plot(tot_damages[tot_damages['epoch'] == baseyear]['rp'],
                                    length_factor*tot_damages[tot_damages['epoch'] == baseyear][f"{plot_column}_median"],
                                    'o-',color='#fd8d3c',markersize=10,linewidth=2.0,
                                    label='Baseline')
                            for i, (r,m,cl) in enumerate(list(zip(rcp,rcp_markers,rcp_colors))):
                                exp = tot_damages[(tot_damages['epoch'] == year) & (tot_damages['rcp'] == r)]
                                ax.plot(exp['rp'],
                                        length_factor*exp[f"{plot_column}_median"],
                                        m,color=cl,markersize=10,linewidth=2.0,
                                        label=f"RCP {r} - median")
                                ax.fill_between(exp['rp'],length_factor*exp[f"{plot_column}_q5"],
                                    length_factor*exp[f"{plot_column}_q95"],
                                    alpha=0.3,facecolor=cl,
                                    label=f"RCP {r} - Q5-Q95")


                                        
                            ax.set_xlabel('Return period (years)',fontsize=14,fontweight='bold')
                            ax.set_ylabel('Direct damage costs (million USD)',fontsize=14,fontweight='bold')
                            ax.set_xscale('log')
                            ax.set_ylim(length_factor*min_limits,length_factor*max_limits)
                            ax.tick_params(axis='both', labelsize=14)
                            ax.set_xticks([t for t in rps])
                            ax.set_xticklabels([str(t) for t in rps])
                            ax.grid(True)
                            # ax.set_xticks([t for t in list(set(exposures[exposures['year'] == baseyear]['return_period'].values))], 
                            #             [str(t) for t in list(set(exposures[exposures['year'] == baseyear]['return_period'].values))])
                            ax.text(
                                0.05,
                                0.95,
                                f"{figure_texts[j]} {year}",
                                horizontalalignment='left',
                                transform=ax.transAxes,
                                size=18,
                                weight='bold')

                            j+=1            

                        ax_plots[-1].legend(
                                    loc='lower left', 
                                    bbox_to_anchor=(1.05,0.8),
                                    prop={'size':18,'weight':'bold'})
                        plt.tight_layout()
                        save_fig(
                                os.path.join(
                                    figure_path, 
                                    f"{map_plot['country']}_{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_damage_lineplot.png"
                                    )
                                )
                        plt.close()

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

