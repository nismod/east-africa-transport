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

def plot_spyder_chart(ax,risk_sens,title):
    # # Plot spyder plot with influence of different variables
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

    ax.plot(angles, stats, 'o-', linewidth=2,color="#de2d26")
    ax.set_ylim([0, 100])   
    ax.fill(angles, stats, alpha=0.25,color="#de2d26")
    ax.set_thetagrids(angles * 180/np.pi, np.array(xticks))
    ax.tick_params(axis='x',labelsize=12,labelcolor='black',color='black',pad=14)
    ax.set_rgrids([20,40,60,80,100])
    return ax

def plot_matrix(ax,S1_S2_matrix,title):
    data = S1_S2_matrix.to_numpy()
    max_val = data.max()
    ax.imshow(data, interpolation='none',cmap="YlGn")
    labels = S1_S2_matrix.columns.values.tolist()
    ax.tick_params(top=False, bottom=False,
                    labeltop=False, labelbottom=False)
    # ax.set_xticks(np.arange(len(labels)), labels=labels)
    ax.set_yticks(np.arange(len(labels)), labels=labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            if data[i, j] < 0.95*max_val:
                color = 'k'
            else:
                color = 'w'
            text = ax.text(j, i, round(data[i, j],2),
                           ha="center", va="center", color=color)

    # bbox = ax.get_yticklabels()[-1].get_window_extent()
    # print (bbox)
    # x,_ = ax.transAxes.inverted().transform([bbox.x0, bbox.y0])
    # ax.set_title('A title aligned with the y-axis labels', ha='left', x=x)
    ax.set_title(
            title,
            fontsize=12,fontweight='black',x=-0.4)

    return ax

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
    # adaptation_option = "no_adaptation"
    all_values = []
    for sensitivity in sensitivity_types:
        for sector in ["rail_edges","road_edges"]:
            df = pd.read_csv(os.path.join(results_data_path,
                                        "global_sensitivity",
                                        f"{sector}_{sensitivity['damage_file_string']}_all_parameters.csv"))
            df_check = df[(df["option"] == "no_adaptation") & (df["hazard"] == sensitivity["hazard"])]
            if len(df_check.index) > 0:
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
                adaptation_options = list(set(df["option"].values.tolist()))
                adaptation_options = [a for a in adaptation_options if a != "no_adaptation"]
                no_adaptation = df[(df["option"] == "no_adaptation") & (df["hazard"] == sensitivity["hazard"])]
                # no_adaptation = no_adaptation[parameter_labels + [sensitivity["damage_type"]]].set_index(parameter_labels)
                for adaptation_option in adaptation_options:
                    df_option = df[(df["option"] == adaptation_option) & (df["hazard"] == sensitivity["hazard"])]
                    if len(df_option.index) > 0:
                        # df_select = no_adaptation[no_adaptation.index.isin(df_option.index.values.tolist())]
                        
                        df_option = df_option.groupby(parameter_labels)[sensitivity["damage_type"]].sum().reset_index()
                        df_select = no_adaptation.groupby(parameter_labels)[sensitivity["damage_type"]].sum().reset_index()

                        df_option = df_option[parameter_labels + [sensitivity["damage_type"]]].set_index(parameter_labels)
                        df_select = df_select[parameter_labels + [sensitivity["damage_type"]]].set_index(parameter_labels)

                        df_option[sensitivity["damage_type"]] = df_option[sensitivity["damage_type"]].sub(
                                                                df_select[sensitivity["damage_type"]],
                                                                axis='index',
                                                                fill_value=0)
                        df_option[sensitivity["damage_type"]] = -1.0*df_option[sensitivity["damage_type"]]
                        if df_option[sensitivity["damage_type"]].sum() > 0:
                            # normalize the model output
                            df_option[sensitivity["damage_type"]] = (df_option[sensitivity["damage_type"]] - df_option[sensitivity["damage_type"]].mean())/df[sensitivity["damage_type"]].std() 

                            S1 = find_sobol_first_order_index(df_option.reset_index(),parameter_labels,sensitivity["damage_type"])
                            S2 = find_sobol_second_order_index(df_option.reset_index(),parameter_labels,sensitivity["damage_type"])
                            risk_sens = find_sobol_total_index(S1,S2)
                            S1_S2_matrix = create_matrix_dataframe(S1,S2) 
                            all_values.append((sensitivity["hazard"],sector,adaptation_option,risk_sens,S1_S2_matrix))

    texts = ['a','b','c','d','e','f','g','h']
    for sensitivity in sensitivity_types:
        for sector in ["rail_edges","road_edges"]:
            values = [v for v in all_values if v[0] == sensitivity["hazard"] and v[1] == sector]
            if len(values) > 0:
                # fig = plt.figure(figsize=(20, 20),dpi=500)
                if sector == "rail_edges":
                    fig, ax_plots = plt.subplots(len(values),2,
                                    subplot_kw={'projection': "polar"},
                                    figsize=(10,20),
                                    dpi=500)
                else:
                    fig, ax_plots = plt.subplots(len(values),2,
                                    subplot_kw={'projection': "polar"},
                                    figsize=(10,25),
                                    dpi=500)
                ax_plots = ax_plots.flatten()
                j = 0
                # print (fig)
                fig.suptitle(
                        f"{sector.split('_')[0].title()}: Adaptation options influence of variables affecting {sensitivity['hazard'].title()} flooding",
                        fontsize=18,fontweight='black',y=1.01)
                for row in range(len(values)):
                    ax_plots[j] = plot_spyder_chart(ax_plots[j],values[row][3],
                                    f'({texts[row]}){values[row][2].title()}')
                    ax_plots[j+1].remove()
                    ax = fig.add_subplot(len(values), 2, j+2)
                    ax = plot_matrix(ax,values[row][4],f'({texts[row]}){values[row][2].title()}')
                    j = j + 2

                fig.tight_layout()
                save_fig(
                    os.path.join(
                        sensitivity_plots,
                        f"{sector}_{sensitivity['hazard']}_adaptation_options_flooding_parameter_sensitivity.png"
                        )
                    )


if __name__ == '__main__':
    # Ignore reading-geopackage warnings
    warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
    # Load config
    CONFIG = load_config()
    main(CONFIG)
