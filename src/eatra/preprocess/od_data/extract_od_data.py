'''
Examples showing how to extract tables from pdf file
using Tabula and PyPDF2
Author: Raghav Pant
Date: 29 Jan, 2018
'''
import sys
import os
import json

import pandas as pd
import geopandas as gpd
import csv
import os
from tabula import read_pdf, convert_into
# from PyPDF2 import PdfFileReader, PdfFileWriter
import numpy as np
from tqdm import tqdm
tqdm.pandas()

def load_config():
    """Read config.json
    """
    config_path = os.path.join(os.path.dirname(__file__),'..', '..','..', 'config.json')
    with open(config_path, 'r') as config_fh:
        config = json.load(config_fh)
    return config

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    df = read_pdf(os.path.join(processed_data_path,
                            "flow_od_data",
                            "ANNUAL-REPORT-FOR-THE-YEAR-ENDED-JUNE-2016.pdf"), pages = "45",area = [102.4,68.09,102.4+314.73,68.09+480.41])
    
    df = df[0]
    df.columns = ["port","quantity","value1","value2"]
    ports = ["Dar es Salaam G/C","TICTS","Tanga","Mtwara"]
    port_dict = dict([(p,[]) for p in ports])
    for row in df.itertuples():
        if row.port in ports:
            q = str(row.quantity).split(" ")[0]
            q = int(q.replace(",",''))
            port_dict[row.port].append(q)

    port_df = []
    for k,v in port_dict.items():
        port_df.append(tuple([k]+v))

    port_df = pd.DataFrame(port_df,columns=["port","imports","exports"])
    port_df["port_code"] = ["DSM","DSM","TNG","MTW"]
    port_df["import_fraction"] = port_df["imports"]/port_df["imports"].sum()
    port_df["export_fraction"] = port_df["exports"]/port_df["exports"].sum()
    print (port_df)
    port_df = port_df.groupby(["port_code"])[["imports","import_fraction","exports","export_fraction"]].sum().reset_index()
    print (port_df)
    port_df.to_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "tanzania_port_2015_shares.csv"),index=False)

    countries = ["TANZANIA","ZAMBIA", "D. R. CONGO", "BURUNDI", "RWANDA", "MALAWI", "UGANDA", "Others", "TOTAL"]
    country_codes = ["TZA","ZMB","COD","BDI","RWA","MWI","UGA","ROF","TOT"]
    df = read_pdf(os.path.join(processed_data_path,
                            "flow_od_data",
                            "ANNUAL-REPORT-FOR-THE-YEAR-ENDED-JUNE-2016.pdf"), pages = "44")
    df = df[0]
    df.columns = ["cargo_type"] + [c for c in df.columns.values.tolist()[1:]]
    df = df[["cargo_type"] + [c for c in df.columns.values.tolist() if "2015/2016" in c]]
    df.columns = ["cargo_type","TZA","ZMB","COD","BDI","RWA","MWI","UGA","ROF","TOT"] 
    for c in country_codes:
        if c == "TZA":
            df[c] = df.progress_apply(
                                lambda x:int(str(x[c]).split(" ")[0].replace(",","")) if str(x[c]) not in ("NaN","nan") else 0,
                                axis=1)
        else:
            df[c] = df.progress_apply(
                                lambda x:int(str(x[c]).replace(",","")) if str(x[c]) not in ("NaN","nan","-") else 0,
                                axis=1)
    df = df[df["cargo_type"].isin(["TOTAL IMPORTS","TOTAL EXPORTS"])]
    df.to_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "dsm_port_2015_import_exports.csv"),index=False)
    df = df[[c for c in df.columns.values.tolist() if c not in ("TZA","ROF","TOT")]]
    cargo_types = ["TOTAL IMPORTS","TOTAL EXPORTS"]
    mapping = []
    for cargo_type in cargo_types:
        df_extract = df[df["cargo_type"] == cargo_type][[c for c in df.columns.values.tolist() if c != "cargo_type"]]
        values = list(zip(["TZA"]*len(df_extract.columns),df_extract.columns,df_extract.T.values.tolist()))
        if cargo_type == "TOTAL IMPORTS":
            cols = ["iso3_O","iso3_D","tons"]
        else:
            cols = ["iso3_D","iso3_O","tons"]
        values = pd.DataFrame(values,columns=cols)
        values["tons"] = values.progress_apply(lambda x:x.tons[0],axis=1)
        mapping.append(values) 

    df = read_pdf(os.path.join(processed_data_path,
                            "flow_od_data",
                            "KPA Annual Report 2015 (without photos).pdf"), pages = "17")
    df = df[0]
    df.columns = ["country","trade_type","2011","2012","2013","2014","2015"]
    df.loc[13,"country"] = "SOUTH SUDAN"
    df = df[~df["country"].isin(["SOUTH","SUDAN"])]
    countries = [c for c in df["country"].values.tolist() if str(c) not in ("NaN","nan","-")]
    countries = [[c]*3 for c in countries]
    country_codes = [[c]*3 for c in ["UGA","TZA","BDI","RWA","SSD","COD","SOM","ROF","TOT"]]
    df["country"] = [item for sublist in countries for item in sublist]
    df["country_code"] = [item for sublist in country_codes for item in sublist]
    for c in "2011","2012","2013","2014","2015":
        df[c] = df.progress_apply(
                                lambda x:int(str(x[c]).replace(",","")) if str(x[c]) not in ("NaN","nan","-") else 0,
                                axis=1)
    print (df)
    df.to_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "mombasa_port_2015_import_exports.csv"),index=False)

    df = df[~df["country_code"].isin(["ROF","TOT"])]
    cargo_types = ["Imports","Exports"]
    for cargo_type in cargo_types:
        df_extract = df[df["trade_type"] == cargo_type]
        values = list(zip(["KEN"]*len(df_extract.index),df_extract["country_code"].values.tolist(),df_extract["2015"].values.tolist()))
        if cargo_type == "Imports":
            cols = ["iso3_O","iso3_D","tons"]
        else:
            cols = ["iso3_D","iso3_O","tons"]
        values = pd.DataFrame(values,columns=cols)
        mapping.append(values)

    mapping = pd.concat(mapping,axis=0,ignore_index=True)
    print (mapping)    
    mapping.to_csv(os.path.join(processed_data_path,
                            "flow_od_data",
                            "mombasa_dsm_2015_import_exports.csv"),index=False)

if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)