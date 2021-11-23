#!/usr/bin/env python
# coding: utf-8
"""Parse hazard layer metadata from path/filenames
"""
import re
import pandas
import os
import json

def load_config():
    """Read config.json"""
    config_path = os.path.join(os.path.dirname(__file__),"..","..","config.json")
    with open(config_path, "r") as config_fh:
        config = json.load(config_fh)
    return config

def main(path):
    # Read basic info
    csv_path = os.path.join(path,"hazard_layers_basic.csv")
    df = pandas.read_csv(csv_path, names = ["path"])

    # Set hazard type 
    df["hazard"] = None

    def hazard(p):
        if "inuncoast" in p:
            return "coastal"
        if "inunriver" in p:
            return "river"

    df["hazard"] = df.path.apply(lambda p: hazard(p))

    # Set return period
    df["rp"] = None

    df.loc[df.hazard == "coastal", "rp"] = df[df.hazard == "coastal"].path.apply(
        lambda p: int(re.search(r"rp(\d+)", p).group(1))
    )

    df.loc[df.hazard == "river", "rp"] = df[df.hazard == "river"].path.apply(
        lambda p: int(re.search(r"rp(\d+)", p).group(1))
    )

    # Set RCP
    df["rcp"] = None


    def rcp(p):
        if "historical" in p:
            return "baseline"
        return int(re.search(r"rcp(\d+)", p).group(1)) + 0.5


    df.loc[df.hazard == "coastal", "rcp"] = df[df.hazard == "coastal"].path.apply(
        rcp
    )

    df.loc[df.hazard == "river", "rcp"] = df[df.hazard == "river"].path.apply(
        rcp
    )

    # Set epoch
    df["epoch"] = None


    def epoch(p):
        if "_hist_" in p:
            return "hist"
        return int(re.search(r"_(\d\d\d\d)_", p).group(1))


    df.loc[df.hazard == "coastal", "epoch"] = df[df.hazard == "coastal"].path.apply(
        epoch
    )

    df.loc[df.hazard == "river", "epoch"] = df[df.hazard == "river"].path.apply(
        epoch
    )

    # Set confidence
    df["confidence"] = None

    def confidence(p):
        if "_0.tif" in p:
            return 95
        if "0_perc_50.tif" in p:
            return 50
        if "0_perc_05.tif" in p:
            return 5
        if "_5.tif" in p:
            return 95
        if "5_perc_50.tif" in p:
            return 50
        if "5_perc_05.tif" in p:
            return 5

    df.loc[df.hazard == "coastal", "confidence"] = df[df.hazard == "coastal"].path.apply(
        confidence
    )

    # Set subsidence
    df["subsidence"] = None


    def subsidence(p):
        if "nosub" in p:
            return "nosub"
        if "wtsub" in p:
            return "wtsub"

    df.loc[df.hazard == "coastal", "subsidence"] = df[df.hazard == "coastal"].path.apply(
        subsidence
    )

    # Set model
    df["model"] = None

    def model(p):
        if "000000000WATCH" in p:
            return "baseline"
        if "00000NorESM1-M" in p:
            return "NorESM1"
        if "0000GFDL-ESM2M" in p:
            return "GFDL"
        if "0000HadGEM2-ES" in p:
            return "HadGEM2"
        if "00IPSL-CM5A-LR" in p:
            return "IPSL"
        if "MIROC-ESM-CHEM" in p:
            return "MIROC"
        
    df.loc[df.hazard == "river", "model"] = df[df.hazard == "river"].path.apply(
        model
    )

    # Sort
    df = df.sort_values(by=["hazard", "rcp", "epoch", "rp", "confidence", "subsidence", "model"]).reset_index(
        drop=True
    )

    # Set key (encode all values)
    df["key"] = df.apply(
        lambda h: f"{h.hazard}__rp_{h.rp}__rcp_{h.rcp}__epoch_{h.epoch}__conf_{h.confidence}__subs_{h.subsidence}__model_{h.model}",
        axis=1,
    )

    # Save all
    df.to_csv(os.path.join(path,"hazard_layers.csv"), index=False)

    # Save broken down by hazard, RCP, epoch
    for hazard in df.hazard.unique():
        hazard_subset = df[df.hazard == hazard].copy()
        for rcp in hazard_subset.rcp.unique():
            rcp_subset = hazard_subset[hazard_subset.rcp == rcp].copy()
            for epoch in rcp_subset.epoch.unique():
                epoch_subset = rcp_subset[rcp_subset.epoch == epoch].copy()
                epoch_subset.to_csv(os.path.join(path,"layers",f"{hazard}__rcp_{rcp}__epoch_{epoch}.csv"))

if __name__ == '__main__':
    # Load config
    CONFIG = load_config()
    
    countries = ["kenya", "tanzania", "uganda", "zambia"]

    for country in countries: 
        path = CONFIG["paths"]["data"]
        data_path = os.path.join(path, country)
        print (data_path)

        main(data_path)

