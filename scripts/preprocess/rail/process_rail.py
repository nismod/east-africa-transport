#!/usr/bin/env python
# coding: utf-8
"""Process railways from OSM
- extract network (mark disused/abandoned/proposed/under construction as
not current)
- process to connected network (link nodes and split edges)
"""
import os
from glob import glob

import fiona
import geopandas as gpd
gpd._compat.USE_PYGEOS = False
import snkit
from tqdm import tqdm


def main():
    raw_files = sorted(glob('scratch/rail/*-rail.gpkg'))

    for fname in tqdm(raw_files):
        print(f"\n{fname}")
        layers = fiona.listlayers(fname)
        out_fname = fname.replace('.gpkg', '_filtered.gpkg')
        try:
            os.remove(out_fname)
        except FileNotFoundError:
            pass

        if 'points' in layers:
            df = process_points(gpd.read_file(fname, layer='points'))
            if not df.empty:
                df.to_file(out_fname, layer='points', driver="GPKG")

        if 'lines' in layers:
            df = process_lines(gpd.read_file(fname, layer='lines'))
            if not df.empty:
                df.to_file(out_fname, layer='lines', driver="GPKG")

        if 'multipolygons' in layers:
            df = process_polygons(gpd.read_file(fname, layer='multipolygons'))
            if not df.empty:
                df.to_file(out_fname, layer='multipolygons', driver="GPKG")

                df = polys_to_points(df)
                df.to_file(out_fname, layer='centroids', driver="GPKG")

    ## Connected network
    filtered_files = sorted(glob('scratch/rail/*_filtered.gpkg'))

    for fname in tqdm(filtered_files):
        country = os.path.basename(fname).replace('-rail_filtered.gpkg', '')
        print(country)

        out_fname = os.path.join('data', 'rail', f"{country}-rail.gpkg")
        try:
            os.remove(out_fname)
        except FileNotFoundError:
            pass

        nodes = read_nodes(fname)
        edges = read_edges(fname)

        network = snkit.Network(nodes, edges)
        network = snkit.network.snap_nodes(network)
        network = snkit.network.split_edges_at_nodes(network)
        network = snkit.network.add_endpoints(network)
        network = snkit.network.add_ids(
            network,
            edge_prefix=f"rail_{country}",
            node_prefix=f"rail_{country}")
        network = snkit.network.add_topology(network, id_col='id')

        network.edges.to_file(out_fname, layer='edges', driver='GPKG')
        network.nodes.to_file(out_fname, layer='nodes', driver='GPKG')


def process_points(df):
    print("Railway", df.railway.unique())

    # add a boolean "is_current" column
    # to mark any past/future points as not current
    df['is_current'] = df['railway'].isin((
        'stop',
        'station',
        'halt',
        'yes'))

    return df[['osm_id', 'name', 'railway', 'is_current', 'geometry']]


def process_lines(df):
    print("Railway", df.railway.unique())

    # add a boolean "is_current" column
    # to mark any past/future lines as not current
    df['is_current'] = ~df['railway'].isin((
        'abandoned',
        'disused',
        'construction',
        'proposed',
        'tram',
        'funicular'))

    return df[['osm_id', 'name', 'railway', 'is_current', 'bridge', 'geometry']]


def process_polygons(df):
    print("Railway", df.railway.unique())
    if "disused" in df.columns:
        print("Disused", df.disused.unique())
    else:
        df['disused'] = ''

    # add a boolean "is_current" column
    # to mark any past/future lines as not current
    df['is_current'] = (
        ~df['railway'].isin(('construction', 'proposed'))
        & ~df['disused'].isin(('yes',))
    )

    return df[['osm_id', 'osm_way_id', 'name', 'railway', 'is_current', 'geometry']]


def polys_to_points(df):
    df.geometry = df.geometry.centroid
    return df


def read_nodes(fname):
    nodes = gpd.read_file(fname, layer='points')
    try:
        centroids = gpd.read_file(fname, layer='centroids')
    except ValueError:
        return nodes
    # If we have centroids, add nodes
    def get_id(row):
        if row.osm_id is None:
            return row.osm_way_id
        else:
            return row.osm_id
    centroids.osm_id = centroids.apply(get_id, axis=1)
    centroids = centroids.drop('osm_way_id', axis=1)
    nodes = nodes.append(centroids)
    return nodes


def read_edges(fname):
    edges = gpd.read_file(fname, layer='lines')
    return edges


if __name__ == '__main__':
    main()
