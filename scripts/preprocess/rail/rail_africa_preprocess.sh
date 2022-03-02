#!/usr/bin/env bash
#
# Extract railways and stations from OSM Africa
#
set -e
set -x

# Extract date string
date="211101"

mkdir -p scratch/rail

osmium tags-filter \
    incoming_data/osm/africa-211101.osm.pbf \
    wnr/railway \
    --overwrite \
    -o scratch/rail/africa-rail.osm.pbf

OSM_CONFIG_FILE=scripts/preprocess/rail/osmconf_rail.ini ogr2ogr -f GPKG \
    scratch/rail/africa-rail.gpkg \
    scratch/rail/africa-rail.osm.pbf \
    points lines multipolygons

# Run script
python scripts/preprocess/rail/process_rail.py scratch/rail/africa-rail.gpkg
