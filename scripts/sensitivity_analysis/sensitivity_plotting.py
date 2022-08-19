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

def find_sobol_first_order_index(df,parameter_labels,output_column):
    S1_index = []
    EY = np.mean(df[output_column].values)
    varY = np.var(df[output_column].values)
    for param in parameter_labels:
        df_effect = df.groupby(
                        [param]
                            )[output_column].mean().reset_index()
        var_effect = np.var(df_effect[output_column].values - EY)
        S1_index.append((param,var_effect/varY))

    S1_index = pd.DataFrame(S1_index,columns=["param","S1"])
    return S1_index

def find_sobol_second_order_index(df,parameter_labels,output_column):
    S2_index = []
    EY = np.mean(df[output_column].values)
    varY = np.var(df[output_column].values)
    for idx1 in range(len(parameter_labels[:-1])):
        p1 = parameter_labels[idx1]
        df1 = df.groupby([p1]
                        )[output_column].mean().reset_index()
        df1.rename(columns={output_column:"dp1"},inplace=True)
        df1["dp1"]  = df1["dp1"] - EY
        for p2 in parameter_labels[idx1+1:]:
            df2 = df.groupby(
                            [p2]
                            )[output_column].mean().reset_index()
            df2.rename(columns={output_column:"dp2"},inplace=True)
            df2["dp2"]  = df2["dp2"] - EY
            df12 = df.groupby(
                            [p1,p2]
                            )[output_column].mean().reset_index()

            df12 = pd.merge(df12,df1,how="left",on=[p1])
            df12 = pd.merge(df12,df2,how="left",on=[p2])
            df12["diff"] = df12[output_column] - df12["dp1"] - df12["dp2"] - EY
            S2_index.append((p1,p2,np.var(df12["diff"])/varY))
            # del df1, df2, df12

    S2_index = pd.DataFrame(S2_index,columns=["param1","param2","S2"])
    return S2_index

def find_sobol_total_index(S1_index,S2_index):
    ST = []
    for s1 in S1_index.itertuples():
        s2_sum = S2_index[(S2_index["param1"] == s1.param) | (S2_index["param2"] == s1.param)]["S2"].sum()
        ST.append((s1.param,s2_sum))

    ST = pd.DataFrame(ST,columns=["param","ST"])
    ST = pd.merge(ST,S1_index,how="left",on=["param"])
    ST["ST"] = ST["ST"] + ST["S1"]

    return ST

def create_matrix_dataframe(S1,S2):
    S1 = S1.sort_values(by="S1",ascending=False)
    S1["param2"] = S1["param"]
    params = S1["param"].values.tolist()
    S1.rename(columns={"param":"param1","S1":"value"},inplace=True)
    S2.rename(columns={"S2":"value"},inplace=True)
    S3 = S2.copy()
    S3.columns = ["param2","param1","value"]
    S_matrix = pd.concat([S1,S2,S3],axis=0,ignore_index=True)
    S_matrix = (S_matrix.set_index(["param1"]).pivot(
                                    columns="param2"
                                    )["value"].rename_axis(None, axis=1)).fillna(0)
    S_matrix["SUM"] = S_matrix[params].sum(axis=1)
    S_matrix = S_matrix.sort_values(by="SUM",ascending=False)
    params = S_matrix.index.values.tolist()

    S_matrix = S_matrix[params]
    # S_matrix.index = params
    return S_matrix

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']
    figure_path = config['paths']['figures']

    sensitivity_plots = os.path.join(figure_path,"sensitivity_plots")
    if os.path.exists(sensitivity_plots) == False:
        os.mkdir(sensitivity_plots)

    sensitivity_types = [
                            {
                                "damage_type":"direct_damages",
                                "damage_file_string":"direct_damages",
                                "hazard":"river",
                                "parameter_names": ["rcp","epoch","model",
                                                    "rp","cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter"],
                                "parameter_labels":["RCP","EPOCH","MODEL",
                                                    "RP","DCOST","FRAG"]
                            },
                            {
                                "damage_type":"direct_damages",
                                "damage_file_string":"direct_damages",
                                "hazard":"coastal",
                                "parameter_names": ["rcp","epoch",
                                                    "rp","cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter",
                                                    "confidence","subsidence"],
                                "parameter_labels":["RCP","EPOCH",
                                                    "RP","DCOST","FRAG","CONF","SUBS"]
                            },
                            {
                                "damage_type":"economic_losses",
                                "damage_file_string":"economic_losses",
                                "hazard":"river",
                                "parameter_names": ["rcp","epoch","model",
                                                    "rp","cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter",
                                                    "duration"],
                                "parameter_labels":["RCP","EPOCH","MODEL",
                                                    "RP","DCOST","FRAG","DUR"]
                            },
                            {
                                "damage_type":"economic_losses",
                                "damage_file_string":"economic_losses",
                                "hazard":"coastal",
                                "parameter_names": ["rcp","epoch",
                                                    "rp","cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter",
                                                    "confidence","subsidence","duration"],
                                "parameter_labels":["RCP","EPOCH",
                                                    "RP","DCOST","FRAG","CONF","SUBS","DUR"]
                            },
                            {
                                "damage_type":"EAD",
                                "damage_file_string":"EAD_EAEL",
                                "hazard":"river",
                                "parameter_names": ["rcp","epoch","model",
                                                    "cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter"],
                                "parameter_labels":["RCP","EPOCH","MODEL",
                                                    "DCOST","FRAG"]
                            },
                            {
                                "damage_type":"EAD",
                                "damage_file_string":"EAD_EAEL",
                                "hazard":"coastal",
                                "parameter_names": ["rcp","epoch",
                                                    "cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter",
                                                    "confidence","subsidence"],
                                "parameter_labels":["RCP","EPOCH",
                                                    "DCOST","FRAG","CONF","SUBS"]
                            },
                            {
                                "damage_type":"EAEL",
                                "damage_file_string":"EAD_EAEL",
                                "hazard":"river",
                                "parameter_names": ["rcp","epoch","model",
                                                    "cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter","duration"],
                                "parameter_labels":["RCP","EPOCH","MODEL",
                                                    "DCOST","FRAG","DUR"]
                            },
                            {
                                "damage_type":"EAEL",
                                "damage_file_string":"EAD_EAEL",
                                "hazard":"coastal",
                                "parameter_names": ["rcp","epoch",
                                                    "cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter",
                                                    "confidence","subsidence","duration"],
                                "parameter_labels":["RCP","EPOCH",
                                                    "DCOST","FRAG","CONF","SUBS","DUR"]
                            },
                            {
                                "damage_type":"total_risk",
                                "damage_file_string":"EAD_EAEL",
                                "hazard":"river",
                                "parameter_names": ["rcp","epoch","model",
                                                    "cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter","duration"],
                                "parameter_labels":["RCP","EPOCH","MODEL",
                                                    "DCOST","FRAG","DUR"]
                            },
                            {
                                "damage_type":"total_risk",
                                "damage_file_string":"EAD_EAEL",
                                "hazard":"coastal",
                                "parameter_names": ["rcp","epoch",
                                                    "cost_uncertainty_parameter",
                                                    "damage_uncertainty_parameter",
                                                    "confidence","subsidence","duration"],
                                "parameter_labels":["RCP","EPOCH",
                                                    "DCOST","FRAG","CONF","SUBS","DUR"]
                            },

                            ]
    adaptation_option = "no_adaptation"
    for sensitivity in sensitivity_types:
        for sector in ["rail_edges","road_edges"]:
            df = pd.read_csv(os.path.join(results_data_path,
                                        "global_sensitivity",
                                        f"{sector}_{sensitivity['damage_file_string']}_all_parameters.csv"))
            df = df[(df["option"] == adaptation_option) & (df["hazard"] == sensitivity["hazard"])]
            if len(df.index) > 0:
                if sensitivity["damage_type"] in ["economic_losses","EAEL"]:
                    duration_effect= []
                    for dur in [10,20,30,40,50]:
                        dur_df = df.copy()
                        dur_df["duration"] = dur
                        dur_df[sensitivity["damage_type"]] = dur*dur_df[sensitivity["damage_type"]]
                        duration_effect.append(dur_df)
                    df = pd.concat(duration_effect,axis=0,ignore_index=True)
                if sensitivity["damage_type"] == "total_risk":
                    duration_effect= []
                    for dur in [10,20,30,40,50]:
                        dur_df = df.copy()
                        dur_df["duration"] = dur
                        dur_df["EAEL"] = dur*dur_df["EAEL"]
                        dur_df["total_risk"] = dur_df["EAD"] + dur_df["EAEL"]
                        duration_effect.append(dur_df)
                    df = pd.concat(duration_effect,axis=0,ignore_index=True)

                parameter_names = sensitivity["parameter_names"]
                parameter_labels = sensitivity["parameter_labels"]
                param_details = dict(list(zip(parameter_names,parameter_labels)))
                df.rename(columns=param_details,inplace=True)
                parameter_labels = [c for c in df.columns.values.tolist() if c in parameter_labels]
                
                # normalize the model output
                df[sensitivity["damage_type"]] = (df[sensitivity["damage_type"]] - df[sensitivity["damage_type"]].mean())/df[sensitivity["damage_type"]].std() 

                S1 = find_sobol_first_order_index(df,parameter_labels,sensitivity["damage_type"])
                S2 = find_sobol_second_order_index(df,parameter_labels,sensitivity["damage_type"])
                risk_sens = find_sobol_total_index(S1,S2)

                # print (S1)
                # print (S2)
                S1_S2_matrix = create_matrix_dataframe(S1,S2) 
                # Plot spyder plot with influence of different variables
                # risk_sens = pd.DataFrame(sobol_parameter_total_effect,columns=["names","ST","S1"])
                risk_sens["ST"] = 100*risk_sens["ST"]
                risk_sens["S1"] = 100*risk_sens["S1"]
                risk_sens = risk_sens.groupby('param').sum()
                risk_sens = risk_sens.T
                stats=risk_sens.loc['ST',np.array(risk_sens.columns)].values
                angles=np.linspace(0, 2*np.pi, len(np.array(risk_sens.columns)), endpoint=False)
                
                # close the plot
                stats=np.concatenate((stats,[stats[0]]))
                angles=np.concatenate((angles,[angles[0]]))
                cols = risk_sens.columns.values.tolist()
                xticks = cols + [cols[0]]

                # fig = plt.figure(figsize=(12, 12),dpi=500)
                fig = plt.figure(figsize=(10, 5))
                ax = plt.subplot(121, projection='polar')

                ax.plot(angles, stats, 'o-', linewidth=2,color="#de2d26")
                ax.set_ylim([0, 100])   
                ax.fill(angles, stats, alpha=0.25,color="#de2d26")
                ax.set_thetagrids(angles * 180/np.pi, np.array(xticks))
                ax.tick_params(axis='x',labelsize=14,labelcolor='black',color='black',pad=14)
                ax.set_rgrids([10,20,30,40,50,60,70,80,90,100])
                # ax.tick_params(pad=-3)

                if sensitivity['damage_type'] in ["direct_damages","economic_losses","total_risk"]:
                    st = sensitivity['damage_type'].replace('_',' ').title()
                else:
                    st = sensitivity['damage_type']

                ax.set_title(
                        f"(a) Total sensitivity to variables",
                        fontsize=12,fontweight='black')
                ax1 = plt.subplot(122)
                data = S1_S2_matrix.to_numpy()
                plt.imshow(data, interpolation='none')
                labels = S1_S2_matrix.columns.values.tolist()
                ax1.tick_params(top=True, bottom=False,
                                labeltop=True, labelbottom=False)
                ax1.set_xticks(np.arange(len(labels)), labels=labels)
                ax1.set_yticks(np.arange(len(labels)), labels=labels)

                # Rotate the tick labels and set their alignment.
                # plt.setp(ax.get_xticklabels(), rotation=45, ha="right",
                #          rotation_mode="anchor")

                # Loop over data dimensions and create text annotations.
                for i in range(len(labels)):
                    for j in range(len(labels)):
                        text = ax1.text(j, i, round(data[i, j],2),
                                       ha="center", va="center", color="w",weight='bold')

                ax1.set_title("(b) Individial and correlated sensitivity effects of variables",
                            fontsize=12,fontweight='black')

                fig.suptitle(
                        f"{sector.split('_')[0].title()}: {st} {sensitivity['hazard'].title()} flooding influence of variables",
                        fontsize=18,fontweight='black', y=1.08)
                fig.tight_layout()
                save_fig(
                    os.path.join(
                        sensitivity_plots,
                        f"{sector}_{sensitivity['damage_type']}_{sensitivity['hazard']}_flooding_parameter_sensitivity.png"
                        )
                    )

if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)
