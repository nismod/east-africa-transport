"""Plotting helpers
"""
import os
from collections import namedtuple

import cartopy.crs as ccrs
import geopandas
import matplotlib.pyplot as plt
import rasterio
import rioxarray


def save_fig(output_filename):
    plt.savefig(output_filename)


def get_axes(extent=(-3.82, 1.82, 4.37, 11.51)):
    """Get map axes
    """
    ax_proj = ccrs.epsg(3857)

    plt.figure(figsize=(4, 6), dpi=150)
    ax = plt.axes([0.025, 0.025, 0.95, 0.95], projection=ax_proj)
    proj = ccrs.PlateCarree()
    ax.set_extent(extent, crs=proj)
    ax.patch.set_facecolor('#bfc0bf')

    return ax


def plot_raster(ax,
                tif_path,
                cmap='viridis',
                levels=None,
                colors=None,
                clip_extent=None):
    """Plot raster with vectors/labels
    """
    # Open raster
    ds = rioxarray.open_rasterio(tif_path, mask_and_scale=True)
    if clip_extent is not None:
        left, right, bottom, top = clip_extent
        ds = ds.rio.clip_box(
            minx=left,
            miny=bottom,
            maxx=right,
            maxy=top,
        )

    # Check raster CRS
    with rasterio.open(tif_path) as da:
        crs_code = da.crs.to_epsg()

    if crs_code == 4326:
        crs = ccrs.PlateCarree()
    else:
        crs = ccrs.epsg(crs_code)

    # Plot raster
    if levels is not None and colors is not None:
        ds.plot(ax=ax, levels=levels, colors=colors, transform=crs)
    else:
        ds.plot(ax=ax, cmap=cmap, transform=crs)

    return ax


def plot_basemap(ax, data_path, ax_crs=3857, plot_regions=False):
    """Plot countries and regions background
    """
    states = geopandas.read_file(
        os.path.join(data_path, 'admin', 'admin0.gpkg')).to_crs(ax_crs)

    lakes = geopandas.read_file(os.path.join(data_path, 'nature',
                                             'lakes.gpkg')).to_crs(ax_crs)

    states.plot(ax=ax, edgecolor='#ffffff', facecolor='#e4e4e300', zorder=1)

    if plot_regions:
        regions = geopandas.read_file(
            os.path.join(data_path, 'admin', 'admin1.gpkg')).to_crs(ax_crs)
        regions.plot(ax=ax, edgecolor='#00000000', facecolor='#dededc')
        regions.plot(ax=ax,
                     edgecolor='#ffffff',
                     facecolor='#00000000',
                     zorder=2)

    lakes.plot(ax=ax, edgecolor='none', facecolor='#87cefa', zorder=1)


def plot_basemap_labels(ax,
                        data_path,
                        include_regions=False,
                        include_zorder=2):
    """Plot countries and regions background
    """
    proj = ccrs.PlateCarree()
    labels = []
    # could read from CSV here

    if include_regions:
        regions = geopandas.read_file(
            os.path.join(data_path, 'admin', 'admin1.gpkg')).to_crs(4326)
        regions_labels = [(r.ADMIN_1_NAME, r.geometry.centroid.x,
                           r.geometry.centroid.y)
                          for r in regions.itertuples()]
        labels += regions_labels

    for text, x, y in labels:
        ax.text(x,
                y,
                text,
                size=6,
                alpha=0.7,
                horizontalalignment='center',
                zorder=include_zorder,
                transform=proj)


def scale_bar(ax, length=100, location=(0.8, 0.05), linewidth=3):
    """Draw a scale bar
    Adapted from https://stackoverflow.com/questions/32333870/how-can-i-show-a-km-ruler-on-a-cartopy-matplotlib-plot/35705477#35705477
    Parameters
    ----------
    ax : axes
    length : int
        length of the scalebar in km.
    location: tuple
        center of the scalebar in axis coordinates (ie. 0.5 is the middle of the plot)
    linewidth: float
        thickness of the scalebar.
    """
    # lat-lon limits
    llx0, llx1, lly0, lly1 = ax.get_extent(ccrs.PlateCarree())

    # Transverse mercator for length
    x = (llx1 + llx0) / 2
    y = lly0 + (lly1 - lly0) * location[1]
    tmc = ccrs.TransverseMercator(x, y)

    # Extent of the plotted area in coordinates in metres
    x0, x1, y0, y1 = ax.get_extent(tmc)

    # Scalebar location coordinates in metres
    sbx = x0 + (x1 - x0) * location[0]
    sby = y0 + (y1 - y0) * location[1]
    bar_xs = [sbx - length * 500, sbx + length * 500]

    # Plot the scalebar and label
    ax.plot(bar_xs, [sby, sby], transform=tmc, color='k', linewidth=linewidth)
    ax.text(sbx,
            sby + 50 * length,
            str(length) + ' km',
            transform=tmc,
            horizontalalignment='center',
            verticalalignment='bottom',
            size=8)


Style = namedtuple('Style', ['color', 'zindex', 'label'])
Style.__doc__ += """: class to hold an element's styles
Used to generate legend entries, apply uniform style to groups of map elements
"""


def within_extent(x, y, extent):
    """Test x, y coordinates against (xmin, xmax, ymin, ymax) extent
    """
    xmin, xmax, ymin, ymax = extent
    return (xmin < x) and (x < xmax) and (ymin < y) and (y < ymax)


def plot_point_assets(ax,
                      nodes,
                      colors,
                      size,
                      marker,
                      zorder,
                      proj_lat_lon=ccrs.PlateCarree()):
    ax.scatter(list(nodes.geometry.x),
               list(nodes.geometry.y),
               transform=proj_lat_lon,
               facecolor=colors,
               s=size,
               marker=marker,
               zorder=zorder)
    return ax


def plot_line_assets(ax,
                     edges,
                     colors,
                     size,
                     zorder,
                     proj_lat_lon=ccrs.PlateCarree()):
    ax.add_geometries(list(edges.geometry),
                      crs=proj_lat_lon,
                      linewidth=size,
                      edgecolor=colors,
                      facecolor='none',
                      zorder=zorder)
    return ax


def plot_polygons(ax,
                  df,
                  df_column,
                  color_map,
                  divisor,
                  legend_label,
                  vmin=0,
                  vmax=1,
                  ax_crs=3857):
    df = df.to_crs(epsg=ax_crs)
    df[df_column] = 1.0 * df[df_column] / divisor
    return df.plot(ax=ax,
                   column=df[df_column],
                   cmap=color_map,
                   vmin=0,
                   vmax=200,
                   legend=False,
                   legend_kwds={
                       'label': legend_label,
                       'orientation': 'horizontal'
                   },
                   zorder=5)


def add_colorbar(fig, ax, min_value, max_value, color_map, legend_label):
    # add colorbar axes to the figure
    # here, need trial-and-error to get [l,b,w,h] right
    # l:left, b:bottom, w:width, h:height; in normalized unit (0-1)
    cbax = fig.add_axes([0.92, 0.02, 0.05, 0.90])  # [0.025, 0.025, 0.95, 0.95]
    cbax.set_title(legend_label, fontsize=20, fontweight='bold')

    sm = plt.cm.ScalarMappable(cmap=color_map,
                               norm=plt.Normalize(vmin=min_value,
                                                  vmax=max_value))
    # at this stage,
    # 'cbax' is just a blank axes, with un needed labels on x and y axes

    # blank-out the array of the scalar mappable 'sm'
    sm._A = []
    # draw colorbar into 'cbax'
    cbar = fig.colorbar(sm, cax=cbax, orientation='vertical', ax=ax)
    cbar.ax.tick_params(labelsize=20)
