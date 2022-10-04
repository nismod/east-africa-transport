#!/usr/bin/env bash
#
# Extract roads from OSM
#
set -e
set -x

# Extract date string
date="211101"

# Extract road features from .osm.pbf to .gpkg
# countries=(
#     "kenya"
#     "tanzania"
#     "uganda"
#     "zambia"
# )

country="africa"
mkdir -p scratch/road
# for country in "${countries[@]}"; do
osmium tags-filter \
    incoming_data/osm/$country-$date.osm.pbf \
    wnr/highway \
    --overwrite \
    -o scratch/road/$country-road.osm.pbf

OSM_CONFIG_FILE=scripts/preprocess/road/osmconf_road.ini ogr2ogr -f GPKG \
    scratch/road/$country-road.gpkg \
    scratch/road/$country-road.osm.pbf \
    points lines
# done

# Run script
python scripts/preprocess/road/process_road.py

# Replace gpkg with new one which includes costs 
python scripts/preprocess/road/costs_road.py
