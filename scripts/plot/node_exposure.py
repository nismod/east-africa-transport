"""Generates summary excel file with exposed port and airport nodes 
"""
import sys
import os
import warnings
import fiona
import pandas as pd
import geopandas as gpd
from plot_utils import *
from tqdm import tqdm
tqdm.pandas()

def main(config):
    epsg_project = 3857
    
    data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    folder_path = os.path.join(results_data_path,'node_exposure')
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    hazard_asset_intersection_path = os.path.join(
                                results_data_path,
                                "hazard_asset_intersection")
    hazard_damage_parameters_csv = os.path.join(data_path,
                                "damage_estimation_processing",
                                "hazard_damage_parameters.csv") 

    hazard_damages = []
    hazard_data_path = os.path.join(data_path,
                        "hazards",
                        "layers")
    hazard_data_files = []
    for root, dirs, files in os.walk(hazard_data_path):
        for file in files:
            if file.endswith("with_transforms.csv"):
                hazard_data_files.append(file)

    hazard_attributes = pd.read_csv(hazard_damage_parameters_csv)

    hazard_csv = os.path.join(data_path,
                                "hazards",
                                "hazard_layers.csv")
    hazard_data_details = pd.read_csv(hazard_csv,encoding="latin1").fillna(0)

    sector_attributes = [
        {
            'network':'air',
            'column_id':'node_id',
            'column_list':['IATA','Name','country','lat','lon','Freight',
                           'Passengers','iso2','iso_code','continent','node_id','geometry']
        },
        {
            'network':'port',
            'column_id':'node_id',
            'column_list':['node_id', 'iso_code', 'continent', 'name', 'country', 
                   'location', 'type', 'latitude', 'longitude',
                   'passengers_embarked', 'passengers_disembarked', 'passenger_total',
                   'cargo_import', 'cargo_export', 'cargo_transit', 'cargo_inwards',
                   'cargo_outwards', 'cargo_total', 'Unnamed: 16', 'Unnamed: 17','geometry']
        }
    ]

    for sector in sector_attributes:
        damages_all = []
        for hazard_file in hazard_data_files:
            hazard_intersection_file = os.path.join(hazard_asset_intersection_path,
                                                    f"{sector['network']}_splits__{hazard_file.replace('__with_transforms.csv','')}__nodes.geoparquet")
            hazard_data_details = pd.read_csv(hazard_csv,encoding="latin1").fillna(0)
            if os.path.isfile(hazard_intersection_file) is True: 
                hazard_df = gpd.read_parquet(hazard_intersection_file)
                hazard_df = hazard_df.to_crs(epsg=epsg_project)

                hazard_columns = [c for c in hazard_df.columns.values.tolist() if c not in sector['column_list']]
                hazard_df = hazard_df.groupby(sector['column_id'])[hazard_columns].sum().reset_index()
                hazard_data_details = hazard_data_details[hazard_data_details.key.isin(hazard_columns)]
                haz_rcp_epoch_confidence_subsidence_model = list(set(hazard_data_details.set_index(["hazard","rcp","epoch","confidence","subsidence","model"]).index.values.tolist()))

                for i,(haz,rcp,epoch,confidence,subsidence,model) in enumerate(haz_rcp_epoch_confidence_subsidence_model):
                    haz_df = hazard_data_details[
                                        (hazard_data_details.hazard == haz
                                        ) & (
                                        hazard_data_details.rcp == rcp
                                        ) & (
                                        hazard_data_details.epoch == epoch
                                        ) & (
                                        hazard_data_details.confidence == confidence
                                        ) & (
                                        hazard_data_details.subsidence == subsidence
                                        ) & (
                                        hazard_data_details.model == model
                                        )]
                    #print (haz_df)
                    haz_cols, haz_rps = map(list,list(zip(*sorted(
                                                list(zip(haz_df.key.values.tolist(),
                                                haz_df.rp.values.tolist()
                                                )),key=lambda x:x[-1],reverse=True))))
                    haz_prob = [1.0/rp for rp in haz_rps]
                    damages = hazard_df[[sector['column_id']] + haz_cols]
                    damages["hazard"] = haz
                    damages["rcp"] = rcp
                    damages["epoch"] = epoch
                    damages["confidence"] = confidence
                    damages["subsidence"] = subsidence
                    damages["model"] = model
                    damages.columns = [sector['column_id']] + haz_rps + ["hazard","rcp","epoch","confidence","subsidence","model"] 
                    #print (damages)
                    damages_all.append(damages)
        damages_all = pd.concat(damages_all,axis=0,ignore_index=True)
        sort_columns = [sector['column_id']] + ["hazard","rcp","epoch"]
        summary = damages_all.groupby(sort_columns)[haz_rps].mean().reset_index()

        summary["sum"] = summary[haz_rps].sum(axis=1)
        summary['flooded'] = summary['sum'].apply(lambda x: 'True' if x >0 else 'False')
        summary.drop(columns=["sum"],inplace=True)
        summary = summary[summary['flooded']=="True"]
        summary.drop(columns=["flooded"],inplace=True)

        summary.to_csv(os.path.join(folder_path,                         
                                  f"{sector['network']}_exposure_summary.csv"))


if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)

