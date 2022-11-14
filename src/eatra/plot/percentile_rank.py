"""Functions for plotting
"""
import os
import sys
import warnings
import geopandas
import pandas
import numpy as np
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
from .plot_utils import *
from .east_africa_plotting_attributes import *


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

		# vals_min_max.sort(key=lambda el: el[1])

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
		# ax.set_xscale('log')
		ax.set_yscale('log')

	# ax.tick_params(axis='x', rotation=45)
	ax.legend(loc='upper left')
	plt.xlabel(x_label, fontweight='bold')
	plt.ylabel(y_label, fontweight='bold')
	plt.title(plot_title)
	ax.grid(linewidth=0.25,zorder=0)
	plt.tight_layout()
	plt.savefig(plot_file_path, dpi=500)
	plt.close()


def main(config):
	incoming_data_path = config['paths']['incoming_data']
	processed_data_path = config['paths']['data']
	output_data_path = config['paths']['results']
	figure_path = config['paths']['figures']

	folder_path = os.path.join(figure_path,"percentile_rank")
	if os.path.exists(folder_path) == False:
		os.mkdir(folder_path)

	durations = [15,30,60]

	value_thr = 100000
	
	modes = ['rail','road']
	duration_colors = ['#f03b20','#6baed6','#3182bd','#08519c']
	duration_labels = ['EAD'] + ['EAEL for max. {} days disruption events'.format(d) for d in durations]

	for m in range(len(modes)):
		risk_df = pd.read_csv(os.path.join(output_data_path,
			'risk_results',
			'direct_damages_summary',
			'{}_edges_EAD_EAEL.csv').format(modes[m]),
			dtype = {'epoch': str, 'rcp': str}
		)

		risk_df = risk_df[risk_df['rcp'] == '8.5']
		risk_df = risk_df[risk_df['epoch'] == '2080']
		risk_df = risk_df[(risk_df['EAEL_no_adaptation_mean'] + risk_df['EAD_no_adaptation_mean']) > value_thr]
		risk_df['zeroes'] = [0]*len(risk_df.index)

		risk_cols = ['zeroes','EAD_no_adaptation_mean']
		fig, ax = plt.subplots(figsize=(8, 4))

		for d in range(len(durations)):
			risk_df['max_risk_{}_days'.format(durations[d])] = durations[d]*risk_df['EAEL_no_adaptation_mean'] + risk_df['EAD_no_adaptation_mean']
			risk_cols.append('max_risk_{}_days'.format(durations[d]))

		risk_df = risk_df[risk_cols].sort_values(['max_risk_{}_days'.format(durations[-1])], ascending=True)
		risk_ranges = []

		for c in range(len(risk_cols)-1):
			risk_ranges.append(risk_df[[risk_cols[c],risk_cols[c+1]]])

		plot_many_ranges(risk_ranges,
			1e6,
			'Percentile rank (%)', 
			'EAD and EAEL (million US$)',
			'{} - EAD and EAEL ranges for Total Risks > {:,} US$'.format(modes[m].title(),value_thr),
			duration_colors,
			duration_labels,
			os.path.join(folder_path,
			'{}-changing-risks-with-days.png'.format(modes[m])))


if __name__ == '__main__':
	# Ignore reading-geopackage warnings
	warnings.filterwarnings('ignore', message='.*Sequential read of iterator was interrupted.*')
	# Load config
	CONFIG = load_config()
	main(CONFIG)
