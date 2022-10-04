"""Functions for plotting
"""
import os
import sys
import warnings
import geopandas as gpd
import pandas as pd
import numpy as np
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
from plot_utils import *
from east_africa_plotting_attributes import *

def read_timeseries(timeseries_path,filename,hazard,rcp):
    timeseries = pd.read_csv(
        os.path.join(timeseries_path,
                     filename),
        encoding = 'latin1',
        dtype={'hazard': 'str','rcp':'str'})
    filtered_df = timeseries[(timeseries.hazard == hazard) & 
                             (timeseries.rcp == rcp)]
    filtered_df.set_index(['edge_id', 'damage_cost_unit','hazard','rcp'], inplace = True)
    summary = filtered_df.agg('sum')
    summary = summary.to_frame().reset_index().rename(columns={'index':'year',0:'ead'})
    summary.year = summary.year.astype("int")
    return summary

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_path = config['paths']['results']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,'ead_timeseries')
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    timeseries_path = os.path.join(
        results_path,
        "risk_results",
        "loss_damage_timeseries")

    hazards = ['river','coastal']
    rcp = ["4.5","8.5"]
    rcp_colors = ['#2171b5','#08306b']
    rcp_markers = ['s-','^-']

    sector_details = sector_attributes() 

    for sector in sector_details:
        if sector["sector"] in ["road","rail"]:
            filename_mean = f"{sector['sector']}_{sector['edge_layer']}_EAD_timeseries_mean.csv"
            filename_min = f"{sector['sector']}_{sector['edge_layer']}_EAD_timeseries_amin.csv"
            filename_max = f"{sector['sector']}_{sector['edge_layer']}_EAD_timeseries_amax.csv"
        
            for hazard in hazards:
                length_factor = 0.000001 # Convert usd to million usd
                fig, ax = plt.subplots(1,1,
                    figsize=(15,9),
                    dpi=500)
                for i, (r,m,cl) in enumerate(list(zip(rcp,rcp_markers,rcp_colors))):
                    mean = read_timeseries(timeseries_path,filename_mean,hazard,r)
                    amin = read_timeseries(timeseries_path,filename_min,hazard,r)
                    amax = read_timeseries(timeseries_path,filename_max,hazard,r)
                    
                    min_limits = amin['ead'].min()
                    max_limits = amax['ead'].max()
                    
                    ax.plot(mean['year'],
                            length_factor * mean['ead'],
                            m, color = cl, markersize = 1, linewidth = 2.0,
                            label = f"RCP {r} - mean")
                    ax.fill_between(amin['year'],
                                    length_factor * amin['ead'],
                                    length_factor * amax['ead'],
                                    alpha=0.3,facecolor=cl,
                                    label=f"RCP {r} - min-max")
                ax.set_xlabel('Year',fontsize=16,fontweight='bold')
                ax.set_ylabel('Expected Annual Damage (million USD)',fontsize=16,fontweight='bold')
                ax.set_xlim(2020, 2080)
                ax.set_ylim(0,length_factor*max_limits)
                ax.tick_params(axis='both', labelsize=14)
                # ax.set_xticks(np.arange(int(mean['year'].min()), int(mean['year'].max())+1, 10))
                ax.set_xticks(np.arange(int(mean['year'].min()), 2080+1, 10))
                ax.grid(True)
                ax.text(
                    0.01,
                    1.015,
                    f"Expected annual damages (million USD) to {sector['sector']} networks from {hazard} flooding",
                    horizontalalignment='left',
                    transform=ax.transAxes,
                    size=18,
                    weight='bold')
                ax.legend(
                    loc='lower left', 
                    bbox_to_anchor=(0,0.73),
                    prop={'size':18,'weight':'bold'})
                plt.tight_layout()
                save_fig(
                    os.path.join(
                        folder_path,
                        f"{sector['sector']}_{sector['edge_layer']}_{hazard}_EAD_timeseries.png"
                    )
                )
                plt.close()

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

