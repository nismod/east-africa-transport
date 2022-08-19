"""Sensitivity analysis testing for trasnport modelling

"""
import os
import sys
import json

import numpy as np
import pandas as pd
import warnings
import scipy.stats
from SALib.sample import morris
import SALib.analyze.morris
import matplotlib.pyplot as plt
from tqdm import tqdm
from SALib.sample import saltelli
from SALib.analyze import sobol
tqdm.pandas()


def load_config():
    """Read config.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    with open(config_path, "r") as config_fh:
        config = json.load(config_fh)
    return config

def save_fig(output_filename):
    print(" * Save", os.path.basename(output_filename))
    plt.savefig(output_filename,bbox_inches='tight')
    plt.close()

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    sensitivity_plots = os.path.join(figure_path,"sensitivity_plots")
    if os.path.exists(sensitivity_plots) == False:
        os.mkdir(sensitivity_plots)

    df = pd.read_csv(os.path.join(results_data_path,
                    "global_sensitivity",
                    f"rail_edges_direct_damages_all_parameters.csv"))
    df = df[(df["option"] == "no_adaptation") & (df["hazard"] == "river")]
    print (df)

    parameter_labels = ["rcp","epoch","model","rp","cost_uncertainty_parameter","damage_uncertainty_parameter"]

    Y = df["direct_damages"].values
    EY = np.mean(Y)
    varY = np.var(Y)

    S1_index = []
    for param in parameter_labels:
        df_effect = df.groupby(
                        [param]
                            )["direct_damages"].mean().reset_index()
        var_effect = np.var(df_effect["direct_damages"].values - EY)
        S1_index.append((param,var_effect/varY))

    S1_index = pd.DataFrame(S1_index,columns=["param","S1"])
    print (S1_index)

    S2_index = []
    for idx1 in range(len(parameter_labels[:-1])):
        p1 = parameter_labels[idx1]
        df1 = df.groupby([p1]
                        )["direct_damages"].mean().reset_index()
        df1.rename(columns={"direct_damages":"dp1"},inplace=True)
        df1["dp1"]  = df1["dp1"] - EY
        for p2 in parameter_labels[idx1+1:]:
            df2 = df.groupby(
                            [p2]
                            )["direct_damages"].mean().reset_index()
            df2.rename(columns={"direct_damages":"dp2"},inplace=True)
            df2["dp2"]  = df2["dp2"] - EY
            df12 = df.groupby(
                            [p1,p2]
                            )["direct_damages"].mean().reset_index()

            df12 = pd.merge(df12,df1,how="left",on=[p1])
            df12 = pd.merge(df12,df2,how="left",on=[p2])
            df12["diff"] = df12["direct_damages"] - df12["dp1"] - df12["dp2"] - EY
            S2_index.append((p1,p2,np.var(df12["diff"])/varY))
            # del df1, df2, df12

    S2_index = pd.DataFrame(S2_index,columns=["p1","p2","S2"])
    print (S2_index)

    print (S1_index["S1"].sum() + S2_index["S2"].sum())

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)
