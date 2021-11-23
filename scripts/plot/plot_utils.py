"""Functions for plotting
"""
import os
import json
import warnings

from collections import namedtuple, OrderedDict

import cartopy.crs as ccrs
import geopandas
import pandas
import numpy
import math
import rasterio
import rioxarray
from shapely.geometry import box
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import LineString
from matplotlib.lines import Line2D
from scalebar import scale_bar

def _get_palette():
    colors = {
        'TRANSPARENT': '#00000000',
        'WHITE': '#ffffff',
        'GREY_1': '#e4e4e3',
        'GREY_2': '#dededc',
        # 'BACKGROUND': '#6baed6',
        'BACKGROUND': '#9ecae1',
    }
    Palette = namedtuple('Palette', colors.keys())
    return Palette(**colors)

Style = namedtuple('Style', ['color', 'zindex', 'label'])
Style.__doc__ += """: class to hold an element's styles
Used to generate legend entries, apply uniform style to groups of map elements
"""
Palette = _get_palette()
AFRICA_GRID_EPSG = 4326

def within_extent(x, y, extent):
    """Test x, y coordinates against (xmin, xmax, ymin, ymax) extent
    """
    xmin, xmax, ymin, ymax = extent
    return (xmin < x) and (x < xmax) and (ymin < y) and (y < ymax)

def get_projection(extent=(-74.04, -52.90, -20.29, -57.38), epsg=None):
    """Get map axes

    Default to Argentina extent // Lambert Conformal projection
    """
    if epsg is not None:
        ax_proj = ccrs.epsg(epsg)
    else:
        x0, x1, y0, y1 = extent
        cx = x0 + ((x1 - x0) / 2)
        cy = y0 + ((y1 - y0) / 2)
        ax_proj = ccrs.TransverseMercator(central_longitude=cx, central_latitude=cy)

    return ax_proj


def get_axes(ax,extent=None):
    """Get map axes

    Parameters
    ----------
    extent, optional: tuple (x0, x1, y0, y1)
        to be provided in AFRICA grid coordinates
    """
    if AFRICA_GRID_EPSG != 4326:
        ax_proj = ccrs.epsg(AFRICA_GRID_EPSG)
    else:
        ax_proj = ccrs.PlateCarree()

    # plt.figure(figsize=(12, 8), dpi=500)
    # ax = plt.axes([0.025, 0.025, 0.95, 0.95], projection=ax_proj)
    if extent is not None:
        ax.set_extent(extent, crs=ax_proj)
    ax.patch.set_facecolor(Palette.BACKGROUND)

    return ax

def scale_bar_and_direction(ax,arrow_location=(0.88,0.08),scalebar_location=(0.92,0.05),scalebar_distance=25,zorder=20):
    """Draw a scale bar and direction arrow

    Parameters
    ----------
    ax : axes
    length : int
        length of the scalebar in km.
    ax_crs: projection system of the axis
        to be provided in AFRICA grid coordinates
    location: tuple
        center of the scalebar in axis coordinates (ie. 0.5 is the middle of the plot)
    linewidth: float
        thickness of the scalebar.
    """
    # lat-lon limits
    scale_bar(ax, scalebar_location, scalebar_distance, color='k',zorder=zorder)

    ax.text(*arrow_location,transform=ax.transAxes, s='N', fontsize=14,zorder=zorder)
    arrow_location = numpy.asarray(arrow_location) + numpy.asarray((0.008,-0.03))
    # arrow_location[1] = arrow_location[1] - 0.02
    ax.arrow(*arrow_location, 0, 0.02, length_includes_head=True,
          head_width=0.01, head_length=0.04, overhang=0.2,transform=ax.transAxes, facecolor='k',zorder=zorder)

def plot_basemap_labels(ax,ax_crs=None,
                        labels=None,label_column=None,
                        label_id_column=None,label_offset={"All":1.0},
                        label_size=8,include_zorder=20):
    """Plot countries and regions background
    """
    if ax_crs is None or ax_crs == 4326:
        proj = ccrs.PlateCarree()
    else:
        proj = ccrs.epsg(ax_crs)
    extent = ax.get_extent(crs=proj)
    extent_x_center = (extent[0] + extent[1])/2.0
    extent_y_center = (extent[2] + extent[3])/2.0
    if labels is not None:
        for label in labels.itertuples():
            text = getattr(label,label_column)
            if label_id_column is not None:
                if getattr(label,label_id_column) in list(label_offset.keys()):
                    apply_offset = label_offset[getattr(label,label_id_column)]
                else:
                    apply_offset = label_offset["All"]
            else:
                apply_offset = label_offset["All"]
            if 'zanzibar' not in text.lower() and 'pemba' not in text.lower():
                x = float(label.geometry.centroid.x)
                y = float(label.geometry.centroid.y)
                if within_extent(x, y, extent) is False:
                    polygon = geopandas.GeoDataFrame(index=[0], 
                                                    crs=f"EPSG:{ax_crs}", 
                                                    geometry=[box(extent[0], extent[2], extent[1], extent[3])])
                    geom = label.geometry.intersection(polygon.geometry.values[0])
                    x = float(geom.centroid.x)
                    y = float(geom.centroid.y)

                if within_extent(x, y, extent):    
                    if text.lower() == "democratic republic of the congo":
                        # print (x,y,extent)
                        offset = -3.5
                    elif text.lower() == "malawi":
                        offset = -10.0
                    else:
                        offset = 1.5
                    if x < extent_x_center:
                        offset_x_adjust = -0.7
                    else:
                        offset_x_adjust = 0.7

                    if y < extent_y_center:
                        offset_y_adjust = -1.0
                    else:
                        offset_y_adjust = 1.1

                    ax.text(
                        x + offset_x_adjust*offset*apply_offset, y + offset_y_adjust*offset*apply_offset,
                        text,
                        alpha=0.7,
                        size=label_size,
                        horizontalalignment='center',
                        zorder = include_zorder,
                        transform=proj)

                    

def plot_basemap(ax, countries,lakes,ax_crs=AFRICA_GRID_EPSG,regions=None,country_labels=False,label_offset={"All":1.0},region_labels=False):
    if ax_crs is None or ax_crs == 4326:
        proj = ccrs.PlateCarree()
    else:
        proj = ccrs.epsg(ax_crs)
    # See more on projections here: https://scitools.org.uk/cartopy/docs/v0.15/crs/projections.html#cartopy-projections
    ax.add_geometries(
        list(countries.geometry),
        crs=proj,
        edgecolor=Palette.WHITE,
        facecolor=Palette.GREY_1,
        zorder=1)
    if country_labels is True:
            plot_basemap_labels(ax,ax_crs=ax_crs,
                                labels=countries,
                                label_column='NAME_0',
                                label_id_column='GID_0',
                                label_offset=label_offset,
                                label_size=10)
    ax.add_geometries(
        list(lakes.geometry),
        crs=proj,
        edgecolor=Palette.WHITE,
        facecolor=Palette.BACKGROUND,
        zorder=3)

    if regions is not None:
        ax.add_geometries(
            list(regions.geometry),
            crs=proj,
            edgecolor=Palette.WHITE,
            facecolor=Palette.GREY_2,
            zorder=2)
        if region_labels is True:
            plot_basemap_labels(ax,ax_crs=ax_crs,
                                labels=regions,
                                label_column='NAME_1',
                                label_offset={"All":0.0})

def plot_point_assets(ax,ax_crs,nodes,colors,size,marker,zorder):
    if ax_crs is None or ax_crs == 4326:
        proj = ccrs.PlateCarree()
    else:
        proj = ccrs.epsg(ax_crs)
    ax.scatter(
        list(nodes.geometry.x),
        list(nodes.geometry.y),
        transform=proj,
        facecolor=colors,
        s=size,
        marker=marker,
        zorder=zorder
    )
    return ax

def plot_line_assets(ax,ax_crs,edges,colors,size,zorder):
    if ax_crs is None or ax_crs == 4326:
        proj = ccrs.PlateCarree()
    else:
        proj = ccrs.epsg(ax_crs)
    ax.add_geometries(
        list(edges.geometry),
        crs=proj,
        linewidth=size,
        edgecolor=colors,
        facecolor='none',
        zorder=zorder
    )
    return ax

def get_sector_layer(sector,sector_data_path,layer_key):
    layer_name_key = f"{layer_key}_layer"
    layer_classify_key = f"{layer_key}_classify_column"
    layer_classify_values = f"{layer_key}_categories"
    if sector[layer_name_key] is not None:
        layer = geopandas.read_file(os.path.join(sector_data_path,sector["sector_gpkg"]),layer=sector[layer_name_key])
        layer = layer[layer[sector[layer_classify_key]].isin(sector[layer_classify_values])]
        return layer
    else:
        return []

def plot_lines_and_points(ax,legend_handles,sector,sector_dataframe=None,layer_key=None,marker_size_factor=1):  
    layer_details = list(zip(sector[f"{layer_key}_categories"],
                                        sector[f"{layer_key}_categories_colors"],
                                        sector[f"{layer_key}_categories_labels"],
                                        sector[f"{layer_key}_categories_zorder"]))
    use_labels = []
    for i,(cat,color,label,zorder) in enumerate(layer_details):
        if layer_key == "edge":
            ax = plot_line_assets(ax,AFRICA_GRID_EPSG,
                                sector_dataframe[sector_dataframe[sector["edge_classify_column"]] == cat],
                                color,
                                marker_size_factor*sector["edge_categories_linewidth"][i],
                                zorder)
            if label not in use_labels:
                legend_handles.append(mpatches.Patch(color=color,
                                                label=label))
                use_labels.append(label)
        elif layer_key == "node":
            ax = plot_point_assets(ax,AFRICA_GRID_EPSG,
                            sector_dataframe[sector_dataframe[sector["node_classify_column"]] == cat],
                            color,
                            sector["node_categories_markersize"][i],
                            sector["node_categories_marker"][i],
                            zorder)
            if label not in use_labels:
                legend_handles.append(plt.plot([],[],
                                        marker=sector["node_categories_marker"][i], 
                                        ms=marker_size_factor*sector["node_categories_markersize"][i], 
                                        ls="",
                                        color=color,
                                        label=label)[0])
                use_labels.append(label)
        
    return ax, legend_handles

def legend_from_style_spec(ax, styles, fontsize = 10, loc='lower left',zorder=20):
    """Plot legend
    """
    handles = [
        mpatches.Patch(color=style.color, label=style.label)
        for style in styles.values() if style.label is not None
    ]
    ax.legend(
        handles=handles,
        fontsize = fontsize,
        loc=loc
    ).set_zorder(zorder)

def generate_weight_bins(weights, n_steps=9, width_step=0.01, interpolation='linear'):
    """Given a list of weight values, generate <n_steps> bins with a width
    value to use for plotting e.g. weighted network flow maps.
    """
    min_weight = min(weights)
    max_weight = max(weights)
    # print (min_weight,max_weight)
    if min(weights) > 0:
        min_order = math.floor(math.log10(min(weights)))
        min_decimal_one = min_weight/(10**min_order)
        min_nearest = round(min_weight/(10**min_order),1)
        if min_nearest > min_decimal_one:
            min_nearest = min_nearest - 0.1
        min_weight = (10**min_order)*min_nearest
    
    if max(weights) > 0:
        max_order = math.floor(math.log10(max(weights)))
        max_decimal_one = max_weight/(10**max_order)
        max_nearest = round(max_weight/(10**max_order),1)
        if max_nearest < max_decimal_one:
            max_nearest += 0.1
        max_weight = (10**max_order)*max_nearest

    width_by_range = OrderedDict()

    if interpolation == 'linear':
        mins = np.linspace(min_weight, max_weight, n_steps,endpoint=True)
    elif interpolation == 'log':
        mins = np.geomspace(min_weight, max_weight, n_steps,endpoint=True)
    elif interpolation == 'quantiles':
        weights = np.array([min_weight] + list(weights) + [max_weight])
        mins = np.quantile(weights,q=np.linspace(0,1,n_steps,endpoint=True))
    elif interpolation == 'equal bins':
        mins = np.array([min_weight] + list(sorted(set([cut.right for cut in pd.qcut(sorted(weights),n_steps-1)])))[:-1] + [max_weight])  
    elif interpolation == 'fisher-jenks':
        weights = np.array([min_weight] + list(weights) + [max_weight])
        mins = jenkspy.jenks_breaks(weights, nb_class=n_steps-1)
    else:
        raise ValueError('Interpolation must be log or linear')
    maxs = mins[1:]
    mins = mins[:-1]
    assert len(maxs) == len(mins)

    if interpolation in ('log','fisher-jenks'):
        scale = np.geomspace(1, len(mins),len(mins))
    else:
        scale = np.linspace(1,len(mins),len(mins))


    for i, (min_, max_) in enumerate(zip(mins, maxs)):
        width_by_range[(min_, max_)] = scale[i] * width_step

    return width_by_range

def find_significant_digits(divisor,significance,width_by_range):
    divisor = divisor
    significance_ndigits = significance
    max_sig = []
    for (i, ((nmin, nmax), line_style)) in enumerate(width_by_range.items()):
        if round(nmin/divisor, significance_ndigits) < round(nmax/divisor, significance_ndigits):
            max_sig.append(significance_ndigits)
        elif round(nmin/divisor, significance_ndigits+1) < round(nmax/divisor, significance_ndigits+1):
            max_sig.append(significance_ndigits+1)
        elif round(nmin/divisor, significance_ndigits+2) < round(nmax/divisor, significance_ndigits+2):
            max_sig.append(significance_ndigits+2)
        else:
            max_sig.append(significance_ndigits+3)

    significance_ndigits = max(max_sig)
    return significance_ndigits


def create_figure_legend(divisor,significance,width_by_range,max_weight,legend_type,legend_colors,legend_weight,marker='o'):
    legend_handles = []
    significance_ndigits = find_significant_digits(divisor,significance,width_by_range)
    for (i, ((nmin, nmax), width)) in enumerate(width_by_range.items()):
        value_template = '{:.' + str(significance_ndigits) + \
            'f}-{:.' + str(significance_ndigits) + 'f}'
        label = value_template.format(
            round(nmin/divisor, significance_ndigits), round(nmax/divisor, significance_ndigits))

        if legend_type == 'marker':
            legend_handles.append(plt.plot([],[],
                                marker=marker, 
                                ms=width/legend_weight, 
                                ls="",
                                color=legend_colors[i],
                                label=label)[0])
        else:
            legend_handles.append(Line2D([0], [0], 
                            color=legend_colors[i], lw=width/legend_weight, label=label))

    return legend_handles

def line_map_plotting_colors_width(ax,df,column,
                        ax_crs=4326,
                        edge_classify_column=None,
                        edge_categories=["1","2","3","4","5"],
                        edge_colors=['#7bccc4','#6baed6','#807dba','#2171b5','#08306b'],
                        edge_labels=[None,None,None,None,None],
                        edge_zorder=[6,7,8,9,10],
                        divisor=1.0,legend_label="Legend",
                        no_value_label="No value",
                        no_value_color="#969696",
                        line_steps=6,
                        width_step=0.02,
                        interpolation="linear",
                        legend_size=7,
                        plot_title=False,
                        significance=0):
    
    if ax_crs is None or ax_crs == 4326:
        proj = ccrs.PlateCarree()
    else:
        proj = ccrs.epsg(ax_crs)

    layer_details = list(
                        zip(
                            edge_categories,
                            edge_colors,
                            edge_labels,
                            edge_zorder
                            )
                        )
    weights = [
        getattr(record,column)
        for record in df.itertuples() if getattr(record,column) > 0
    ]
    max_weight = max(weights)
    width_by_range = generate_weight_bins(weights, 
                                width_step=width_step, 
                                n_steps=line_steps,
                                interpolation=interpolation)
    min_width = 0.8*width_step
    min_order = min(edge_zorder)

    if edge_classify_column is None:
        line_geoms_by_category = {j:[] for j in edge_categories + [no_value_label]}
        for record in df.itertuples():
            geom = record.geometry
            val = getattr(record,column)
            buffered_geom = None
            for (i, ((nmin, nmax), width)) in enumerate(width_by_range.items()):
                if val == 0:
                    buffered_geom = geom.buffer(min_width)
                    cat = no_value_label
                    # min_width = width
                    break
                elif nmin <= val and val < nmax:
                    buffered_geom = geom.buffer(width)
                    cat = str(i+1)

            if buffered_geom is not None:
                line_geoms_by_category[cat].append(buffered_geom)
            else:
                print("Feature was outside range to plot", record.Index)

        legend_handles = create_figure_legend(divisor,
                        significance,
                        width_by_range,
                        max_weight,
                        'line',edge_colors,width_step)
        styles = OrderedDict([
            (cat,  
                Style(color=color, zindex=zorder,label=label)) for j,(cat,color,label,zorder) in enumerate(layer_details)
        ] + [(no_value_label,  Style(color=no_value_color, zindex=min_order-1,label=no_value_label))])
    else:
        line_geoms_by_category = OrderedDict([(j,[]) for j in edge_labels + [no_value_label]])
        for j,(cat,color,label,zorder) in enumerate(layer_details):
            # line_geoms_by_category[label] = []
            for record in df[df[edge_classify_column] == cat].itertuples():
                geom = record.geometry
                val = getattr(record,column)
                buffered_geom = None
                geom_key = label
                for (i, ((nmin, nmax), width)) in enumerate(width_by_range.items()):
                    if val == 0:
                        buffered_geom = geom.buffer(min_width)
                        geom_key = no_value_label
                        # min_width = width
                        break
                    elif nmin <= val and val < nmax:
                        buffered_geom = geom.buffer(width)

                if buffered_geom is not None:
                    line_geoms_by_category[geom_key].append(buffered_geom)
                else:
                    print("Feature was outside range to plot", record.Index)

            legend_handles = create_figure_legend(divisor,
                        significance,
                        width_by_range,
                        max_weight,
                        'line',["#023858"]*line_steps,width_step)

        styles = OrderedDict([
            (label,  
                Style(color=color, zindex=zorder,label=label)) for j,(cat,color,label,zorder) in enumerate(layer_details)
        ] + [(no_value_label,  Style(color=no_value_color, zindex=min_order-1,label=no_value_label))])
    
    for cat, geoms in line_geoms_by_category.items():
        # print (cat,geoms)
        cat_style = styles[cat]
        ax.add_geometries(
            geoms,
            crs=proj,
            linewidth=0.0,
            facecolor=cat_style.color,
            edgecolor='none',
            zorder=cat_style.zindex
        )
    
    if plot_title:
        ax.set_title(plot_title, fontsize=9)
    print ('* Plotting ',plot_title)
    first_legend = ax.legend(handles=legend_handles,fontsize=legend_size,title=legend_label,loc='upper right')
    ax.add_artist(first_legend).set_zorder(20)
    legend_from_style_spec(ax, styles,fontsize=legend_size,loc='lower left',zorder=20)
    return ax

def point_map_plotting_colors_width(ax,df,column,
                        ax_crs=4326,
                        point_classify_column=None,
                        point_categories=["1","2","3","4","5"],
                        point_colors=['#7bccc4','#6baed6','#807dba','#2171b5','#08306b'],
                        point_labels=[None,None,None,None,None],
                        point_zorder=[6,7,8,9,10],
                        marker="o",
                        divisor=1.0,
                        legend_label="Legend",
                        no_value_label="No value",
                        no_value_color="#969696",
                        point_steps=6,
                        width_step=0.02,
                        interpolation="linear",
                        legend_size=6,
                        plot_title=False,
                        significance=0):
    
    if ax_crs is None or ax_crs == 4326:
        proj = ccrs.PlateCarree()
    else:
        proj = ccrs.epsg(ax_crs)

    layer_details = list(
                        zip(
                            point_categories,
                            point_colors,
                            point_labels,
                            point_zorder
                            )
                        )
    weights = [
        getattr(record,column)
        for record in df.itertuples() if getattr(record,column) > 0
    ]
    max_weight = max(weights)
    width_by_range = generate_weight_bins(weights, 
                                width_step=width_step, 
                                n_steps=point_steps,
                                interpolation=interpolation)
    min_width = 0.8*width_step
    min_order = min(point_zorder)

    if point_classify_column is None:
        point_geoms_by_category = {j:[] for j in point_categories + [no_value_label]}
        for record in df.itertuples():
            geom = record.geometry
            val = getattr(record,column)
            for (i, ((nmin, nmax), width)) in enumerate(width_by_range.items()):
                if val == 0:
                    point_geoms_by_category[no_value_label].append((geom,min_width))
                    break
                elif nmin <= val and val < nmax:
                    point_geoms_by_category[str(i+1)].append((geom,width))

        legend_handles = create_figure_legend(divisor,
                        significance,
                        width_by_range,
                        max_weight,
                        'marker',point_colors,width_step/2,marker=marker)
        styles = OrderedDict([
            (cat,  
                Style(color=color, zindex=zorder,label=label)) for j,(cat,color,label,zorder) in enumerate(layer_details)
        ] + [(no_value_label,  Style(color=no_value_color, zindex=min_order-1,label=no_value_label))])
    else:
        # point_geoms_by_category = OrderedDict()
        # point_geoms_by_category[no_value_label] = []
        point_geoms_by_category = OrderedDict([(j,[]) for j in point_labels + [no_value_label]])
        # point_geoms_by_category[label] = []
        for j,(cat,color,label,zorder) in enumerate(layer_details):
            for record in df[df[point_classify_column] == cat].itertuples():
                geom = record.geometry
                val = getattr(record,column)
                buffered_geom = None
                geom_key = label
                for (i, ((nmin, nmax), width)) in enumerate(width_by_range.items()):
                    if val == 0:
                        point_geoms_by_category[no_value_label].append((geom,min_width))
                        # geom_key = no_value_label
                        # min_width = width
                        break
                    elif nmin <= val and val < nmax:
                        point_geoms_by_category[label].append((geom,width))


            legend_handles = create_figure_legend(divisor,
                        significance,
                        width_by_range,
                        max_weight,
                        'marker',["#023858"]*point_steps,width_step/2,marker=marker)

        styles = OrderedDict([
            (label,  
                Style(color=color, zindex=zorder,label=label)) for j,(cat,color,label,zorder) in enumerate(layer_details)
        ] + [(no_value_label,  Style(color=no_value_color, zindex=min_order-1,label=no_value_label))])


    for cat, geoms in point_geoms_by_category.items():
        cat_style = styles[cat]
        for g in geoms:
            ax.scatter(
                g[0].x,
                g[0].y,
                transform=proj,
                facecolor=cat_style.color,
                s=g[1],
                alpha=0.8,
                marker=marker,
                zorder=cat_style.zindex
            )

    if plot_title:
        plt.title(plot_title, fontsize=9)
    first_legend = ax.legend(handles=legend_handles,fontsize=legend_size,title=legend_label,loc='upper right')
    ax.add_artist(first_legend).set_zorder(20)
    print ('* Plotting ',plot_title)
    legend_from_style_spec(ax, styles,fontsize=legend_size,loc='lower left',zorder=20)
    return ax

def plot_raster(ax, tif_path, cmap='viridis', levels=None, colors=None,
                reproject_transform=None,clip_extent=None):
    """Plot raster with vectors/labels
    """
    # Open raster
    ds = rioxarray.open_rasterio(tif_path, mask_and_scale=True)
    if reproject_transform is not None:
        ds = ds.rio.reproject(f"EPSG:{reproject_transform}")
    if clip_extent is not None:
        left, right, bottom, top = clip_extent
        ds = ds.rio.clip_box(
            minx=left,
            miny=bottom,
            maxx=right,
            maxy=top,
        )
    if reproject_transform == 4326:
        crs = ccrs.PlateCarree()
    else:
        crs = ccrs.epsg(ax_crs)
    # Plot raster
    if levels is not None and colors is not None:
        im = ds.plot(
            ax=ax,
            levels=levels,
            colors=colors,
            transform=crs,
            alpha=0.6,
            add_colorbar=False
        )
    else:
        im =ds.plot(
            ax=ax,
            cmap=cmap,
            transform=crs,
            alpha=0.6,
            add_colorbar=False
        )

    return im


def load_config():
    """Read config.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    with open(config_path, "r") as config_fh:
        config = json.load(config_fh)
    return config


def geopandas_read_file_type(file_path, file_layer, file_database=None):
    if file_database is not None:
        return geopandas.read_file(os.path.join(file_path, file_database), layer=file_layer)
    else:
        return geopandas.read_file(os.path.join(file_path, file_layer))


def save_fig(output_filename):
    print(" * Save", os.path.basename(output_filename))
    plt.savefig(output_filename,bbox_inches='tight')
    plt.close()
