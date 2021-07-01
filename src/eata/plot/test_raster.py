import os
import sys

import matplotlib.pyplot as plt

from eata.config import load_config
from eata.plot.map import get_axes, plot_basemap, plot_raster


if __name__ == '__main__':
    base_path = load_config()["base_path"]
    try:
        tif_path = sys.argv[1]
    except:
        # GeoTIFF to plot
        tif_path = os.path.join(
            base_path, 'hazards',
            'flood.tif')

    try:
        png_path = sys.argv[2]
    except:
        # PNG output - default to same name as TIF, but .png
        png_path = os.path.join(
            os.path.dirname(tif_path),
            os.path.basename(tif_path).replace(".tif", ".png"))

    print("Plotting", tif_path)
    print("to image", png_path)
    ax = get_axes()
    plot_raster(
        ax, tif_path,
        levels=[0, 0.01, 0.1, 1, 10],
        colors=['#fde725', '#20a378', '#287d8e', '#481567', '#000000']
    )
    plot_basemap(ax, os.path.join(base_path, 'data'))
    plt.savefig(png_path)
