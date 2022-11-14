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
from .plot_utils import *
from .east_africa_plotting_attributes import *

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']
    output_data_path = config['paths']['output']
    figure_path = config['paths']['figures']

    folder_path = os.path.join(output_data_path,'damage_tables')
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
            damage_parquet = os.path.join(results_data_path,
                'risk_results',
                'direct_damages_summary',
                f"{sector['sector']}_{sector['edge_layer']}_damages.parquet")
            damage_results = pd.read_parquet(damage_parquet)

            for hazard in hazards:
                data = []
                for epoch in epochs: 
                    for rcp in rcps:
                        for rp in rps:
                            filtered_df = hazard_data_details[(hazard_data_details.hazard == hazard) & 
                                                            (hazard_data_details.epoch == epoch) &
                                                            (hazard_data_details.rcp == rcp) &
                                                            (hazard_data_details.rp == rp)]
                            filtered_columns = ["edge_id",'damage_cost_unit']
                            for i in list(filtered_df.key):
                                filtered_columns.append(i+"_amin")
                                filtered_columns.append(i+"_mean")
                                filtered_columns.append(i+"_amax")
                            if(set(filtered_columns)).issubset(damage_results.columns):
                                damage_results_new = damage_results[filtered_columns]
                                if len(damage_results_new.columns) > 2:
                                    # VERSION 1: 
                                    # damage_results_new.mean = damage_results_new.loc[:, damage_results_new.columns.str.contains("_mean")].mean(axis=1)
                                    # damage_results_new.min = damage_results_new.loc[:, damage_results_new.columns.str.contains("_amin")].mean(axis=1)
                                    # damage_results_new.max = damage_results_new.loc[:, damage_results_new.columns.str.contains("_amax")].mean(axis=1)
                                    
                                    # data.append([hazard, epoch, rcp, rp,
                                    #             damage_results_new.mean.sum(),
                                    #             damage_results_new.min.sum(),
                                    #             damage_results_new.max.sum()])

                                    # VERSION 2:
                                    damage_results_sum = damage_results_new.sum(numeric_only=True, axis=0)
                    
                                    data.append([hazard, epoch, rcp, rp,
                                                damage_results_sum.loc[damage_results_sum.index.str.contains('_mean')].mean(),
                                                damage_results_sum.loc[damage_results_sum.index.str.contains('_amin')].min(),
                                                damage_results_sum.loc[damage_results_sum.index.str.contains('_amax')].max()])

                                    # VERSION 3:
                                    # damage_results_sum = damage_results_new.sum(numeric_only=True, axis=0)
                    
                                    # data.append([hazard, epoch, rcp, rp,
                                    #             damage_results_sum.loc[damage_results_sum.index.str.contains('_mean')].mean(),
                                    #             damage_results_sum.loc[damage_results_sum.index.str.contains('_mean')].min(),
                                    #             damage_results_sum.loc[damage_results_sum.index.str.contains('_mean')].max()])

                                    # VERSION 4: 
                                    # damage_results_new.mean = damage_results_new.loc[:, damage_results_new.columns.str.contains("_mean")].mean(axis=1)
                                    # damage_results_new.min = damage_results_new.loc[:, damage_results_new.columns.str.contains("_amin")].min(axis=1)
                                    # damage_results_new.max = damage_results_new.loc[:, damage_results_new.columns.str.contains("_amax")].max(axis=1)
                                    
                                    # data.append([hazard, epoch, rcp, rp,
                                    #             damage_results_new.mean.sum(),
                                    #             damage_results_new.min.sum(),
                                    #             damage_results_new.max.sum()])

                                    # VERSION 5:
                                    # damage_results_sum = damage_results_new.sum(numeric_only=True, axis=0)
                    
                                    # data.append([hazard, epoch, rcp, rp,
                                    #             damage_results_sum.loc[damage_results_sum.index.str.contains('_mean')].mean(),
                                    #             damage_results_sum.loc[damage_results_sum.index.str.contains('_amin')].mean(),
                                    #             damage_results_sum.loc[damage_results_sum.index.str.contains('_amax')].mean()])



                df = pd.DataFrame(data, columns=['hazard', 'epoch', 'rcp', 'rp', 'mean', 'min', 'max'])
                if df.empty != True:
                    df.to_excel(
                     os.path.join(
                                folder_path, 
                                f"{sector['sector_label'].lower().replace(' ','_')}_{sector['edge_layer']}_{hazard}_damage_table.xlsx"
                                )
                            )
if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

