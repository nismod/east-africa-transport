"""Plot adaptation cost ranges (national results)
"""
import sys
import os
import ast
import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import copy
from matplotlib import cm
from .plot_utils import *

mpl.style.use('ggplot')
mpl.rcParams['font.size'] = 10.
mpl.rcParams['font.family'] = 'tahoma'
mpl.rcParams['axes.labelsize'] = 10.
mpl.rcParams['xtick.labelsize'] = 9.
mpl.rcParams['ytick.labelsize'] = 9.

def plot_ranges(input_data, division_factor,x_label, y_label,plot_title,plot_color,plot_label,plot_file_path):
    fig, ax = plt.subplots(figsize=(8, 4))
    vals_min_max = list(zip(*list(h for h in input_data.itertuples(index=False))))

    percentlies = 100.0*np.arange(0,len(vals_min_max[0]))/len(vals_min_max[0])
    ax.plot(percentlies,
        1.0*np.array(vals_min_max[0])/division_factor,
        linewidth=0.5,
        color=plot_color
    )
    ax.plot(percentlies,
        1.0*np.array(vals_min_max[1])/division_factor,
        linewidth=0.5,
        color=plot_color
    )
    ax.fill_between(percentlies,
        1.0*np.array(vals_min_max[0])/division_factor,
        1.0*np.array(vals_min_max[1])/division_factor,
        alpha=0.5,
        edgecolor=None,
        facecolor=plot_color,
        label = plot_label
    )

    if 'BCR' in y_label:
        ax.plot(np.arange(0,100),
            np.array([1]*100),
            linewidth=0.5,
            color='red',
            label = 'BCR = 1'
        )
        ax.set_yscale('log')
    # ax.tick_params(axis='x', rotation=45)
    ax.legend(loc='upper left')
    plt.xlabel(x_label, fontweight='bold')
    plt.ylabel(y_label, fontweight='bold')
    plt.title(plot_title)

    plt.tight_layout()
    plt.savefig(plot_file_path, dpi=500)
    plt.close()

def plot_many_ranges_subplots(input_dfs, division_factor,x_label, y_label,plot_title,plot_color,plot_labels,plot_file_path):
    # fig, ax = plt.subplots(figsize=(8, 4))
    fig, ax = plt.subplots(1, len(input_dfs), figsize=(8, 4), sharey=True)

    length = []
    for i in range(len(input_dfs)):
        input_data = input_dfs[i]

        vals_min_max = []
        for a, b in input_data.itertuples(index=False):
            if a < b:
                min_, max_ = a, b
            else:
                min_, max_ = b, a
            vals_min_max.append((min_, max_))

        vals_min_max.sort(key=lambda el: el[1])

        vals_min_max = list(zip(*vals_min_max))

        percentlies = 100.0*np.arange(0,len(vals_min_max[0]))/len(vals_min_max[0])
        length.append(len(vals_min_max[0]))
        ax[i].plot(percentlies,
            1.0*np.array(vals_min_max[0])/division_factor,
            linewidth=0.5,
            color=plot_color[i]
        )
        ax[i].plot(percentlies,
            1.0*np.array(vals_min_max[1])/division_factor,
            linewidth=0.5,
            color=plot_color[i]
        )
        ax[i].fill_between(percentlies,
            1.0*np.array(vals_min_max[0])/division_factor,
            1.0*np.array(vals_min_max[1])/division_factor,
            alpha=0.5,
            edgecolor=None,
            facecolor=plot_color[i],
            label = plot_labels[i]
        )

        if 'BCR' in y_label:
            ax[i].plot(np.arange(0,100),
                np.array([1]*100),
                linewidth=0.5,
                color='red',
                label = 'BCR = 1'
            )
            ax[i].set_yscale('log')

    # ax.set_yscale('log')

    # ax.tick_params(axis='x', rotation=45)
        ax[i].legend(loc='upper left')
        ax[i].set_xlabel(x_label, fontweight='bold')
    
    # fig.text(0.5, 0.04, 'Hazard scenarios', ha="center", va="center", fontweight='bold')
    fig.text(0.015, 0.5, y_label, ha="center", va="center", rotation=90, fontweight='bold')

    fig.text(0.5, 0.98, plot_title, ha="center", va="center", fontweight='bold')
    # plt.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize = 8)
    fig.subplots_adjust(hspace=0)

    # plt.ylabel(y_label, fontweight='bold')
    # plt.title(plot_title)

    plt.tight_layout()
    plt.savefig(plot_file_path, dpi=500)
    plt.close()

def plot_many_ranges(input_dfs, division_factor,x_label, y_label,plot_title,plot_color,plot_labels,plot_file_path):
    fig, ax = plt.subplots(figsize=(8, 4))

    length = []
    for i in range(len(input_dfs)):
        input_data = input_dfs[i]
        vals_min_max = []
        for a, b in input_data.itertuples(index=False):
            if a < b:
                min_, max_ = a, b
            else:
                min_, max_ = b, a
            vals_min_max.append((min_, max_))

        vals_min_max.sort(key=lambda el: el[1])

        vals_min_max = list(zip(*vals_min_max))

        percentlies = 100.0*np.arange(0,len(vals_min_max[0]))/len(vals_min_max[0])
        length.append(len(vals_min_max[0]))
        ax.plot(percentlies,
            1.0*np.array(vals_min_max[0])/division_factor,
            linewidth=0.5,
            color=plot_color[i]
        )
        ax.plot(percentlies,
            1.0*np.array(vals_min_max[1])/division_factor,
            linewidth=0.5,
            color=plot_color[i]
        )
        ax.fill_between(percentlies,
            1.0*np.array(vals_min_max[0])/division_factor,
            1.0*np.array(vals_min_max[1])/division_factor,
            alpha=0.5,
            edgecolor=None,
            facecolor=plot_color[i],
            label = plot_labels[i]
        )

    length = max(length)
    if 'BCR' in y_label:
        ax.plot(np.arange(0,100),
            np.array([1]*100),
            linewidth=0.5,
            color='red',
            label = 'BCR = 1'
        )
        ax.set_yscale('log')

    # ax.set_yscale('log')

    # ax.tick_params(axis='x', rotation=45)
    ax.legend(loc='upper left')
    plt.xlabel(x_label, fontweight='bold')
    plt.ylabel(y_label, fontweight='bold')
    plt.title(plot_title)

    plt.tight_layout()
    plt.savefig(plot_file_path, dpi=500)
    plt.close()

def main(config):
    incoming_data_path = config['paths']['incoming_data']
    processed_data_path = config['paths']['data']
    results_data_path = config['paths']['results']

    figure_path = config['paths']['figures']

    bcr_plots = os.path.join(figure_path,"bcr_plots")
    if os.path.exists(bcr_plots) == False:
        os.mkdir(bcr_plots)

    rcps_cols = ["river__rcp_4.5__BCR","river__rcp_8.5__BCR"]
    rcp_colors = ['#54278f','#08519c']
    rcp_labels = ['RCP 4.5','RCP 8.5']

    for sector in ["rail_edges","road_edges"]:
        df = pd.read_csv(os.path.join(results_data_path,
                        "adaptation_benefits_costs_bcr",
                        f"{sector}_adaptation_benefits_costs_bcr_15_days_disruption.csv"))

        adaptation_options = list(set(df["adaptation_option"].values.tolist()))
        for option in adaptation_options:
            input_dfs = []
            option_df = df[df["adaptation_option"] == option]
            min_max_cols = [c for c in option_df.columns.values.tolist() if "_amin" in c or "_amax" in c]
            plot_file_path = os.path.join(bcr_plots,f"{sector}_{option}_bcr_ranges.png")
            for rcp in rcps_cols:
                input_dfs.append(option_df[[c for c in min_max_cols if rcp in c]])
            plot_many_ranges(input_dfs, 1.0,
                            "Percentile rank (%)",
                            "BCR ranges",
                            f"{sector.replace('_',' ').title()}:{option} BCRs across climate scenarios",
                            rcp_colors,
                            rcp_labels,
                            plot_file_path)


if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)
