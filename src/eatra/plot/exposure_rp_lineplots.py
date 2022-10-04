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

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    output_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(figure_path,'exposure_rp')
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    hazard_csv = os.path.join(processed_data_path, 
        'hazards',
        'hazard_layers.csv')
    hazard_data_details = pd.read_csv(hazard_csv,encoding='latin1')

    hazards = hazard_data_details.hazard.unique()
    epochs = hazard_data_details.epoch.unique()
    rcps = hazard_data_details.rcp.unique()
    rps = hazard_data_details.rp.unique()

    sector_details = sector_attributes() 
    
    for sector in sector_details:
        if sector['sector'] in ['road','rail']: # ['road', 'rail']
            exposure_parquet = os.path.join(output_data_path,
                'risk_results',
                'direct_damages_summary',
                f"{sector['sector']}_{sector['edge_layer']}_exposures.parquet")
            exposure_results = pd.read_parquet(exposure_parquet)

            for hazard in hazards:
                data = []
                for epoch in epochs: 
                    for rcp in rcps:
                        for rp in rps:
                            filtered_df = hazard_data_details[(hazard_data_details.hazard == hazard) & 
                                                            (hazard_data_details.epoch == epoch) &
                                                            (hazard_data_details.rcp == rcp) &
                                                            (hazard_data_details.rp == rp)]
                            filtered_columns = ['edge_id','exposure_unit'] + list(filtered_df.key)
                            if(set(filtered_columns)).issubset(exposure_results.columns):
                                exposure_results_new = exposure_results[filtered_columns]
                                if len(exposure_results_new.columns) > 2:
                                    # exposure_results_new.mean = exposure_results_new.iloc[:, 2:].mean(axis=1)
                                    # exposure_results_new.min = exposure_results_new.iloc[:, 2:].min(axis=1)
                                    # exposure_results_new.max = exposure_results_new.iloc[:, 2:].max(axis=1)

                                    # data.append([hazard, epoch, rcp, rp,
                                    #             exposure_results_new.mean.sum(),
                                    #             exposure_results_new.min.sum(),
                                    #             exposure_results_new.max.sum()])

                                    exposure_results_sum = exposure_results_new.sum(numeric_only=True, axis=0)
                                    data.append([hazard, epoch, rcp, rp,
                                                 exposure_results_sum.mean(),
                                                 exposure_results_sum.min(),
                                                 exposure_results_sum.max()])

                df = pd.DataFrame(data, columns=['hazard', 'epoch', 'rcp', 'rp', 'mean', 'min', 'max'])
                if df.empty != True:
                    min_limits = min(df[['mean','min','max']].min())
                    max_limits = max(df[['mean','min','max']].max())
                    
                    figure_texts = ['a.','b.','c.']
                    years = ['2030','2050','2080']
                    rcp = ['4.5','8.5']
                    rcp_colors = ['#2171b5','#08306b']
                    rcp_markers = ['s-','^-']
                    if hazard == 'river':
                        baseyear = '1980'
                    if hazard == 'coastal':
                        baseyear = 'hist'
                    length_factor = 0.001 # Convert length from m to km

                    fig, ax_plots = plt.subplots(1,3,
                        figsize=(20,12),
                        dpi=500)
                    ax_plots = ax_plots.flatten()
                    j = 0
                    for year in years:
                        ax = ax_plots[j]
                        ax.plot(df[df['epoch'] == baseyear]['rp'],
                                length_factor*df[df['epoch'] == baseyear]['mean'],
                                'o-',color='#fd8d3c',markersize=10,linewidth=2.0,
                                label='Baseline')
                        for i, (r,m,cl) in enumerate(list(zip(rcp,rcp_markers,rcp_colors))):
                            exp = df[(df['epoch'] == year) & (df['rcp'] == r)]
                            ax.plot(exp['rp'],
                                    length_factor*exp['mean'],
                                    m,color=cl,markersize=10,linewidth=2.0,
                                    label=f"RCP {r} - mean")
                            ax.fill_between(exp['rp'],length_factor*exp['min'],
                                length_factor*exp['max'],
                                alpha=0.3,facecolor=cl,
                                label=f"RCP {r} - min-max")

                        ax.set_xlabel('Return period (years)',fontsize=14,fontweight='bold')
                        ax.set_ylabel('Flooded length (km)',fontsize=14,fontweight='bold')
                        ax.set_xscale('log')
                        ax.set_ylim(length_factor*min_limits,length_factor*max_limits)
                        ax.tick_params(axis='both', labelsize=14)
                        ax.set_xticks([t for t in rps])
                        ax.set_xticklabels([str(t) for t in rps])
                        ax.grid(True)
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
                                folder_path, 
                                f"{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{hazard}_exposures_lineplot.png"
                                )
                            )
                    plt.close()
if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

