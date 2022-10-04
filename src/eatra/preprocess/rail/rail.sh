#!/usr/bin/env bash
#
# Extract railways and stations from OSM
#
set -e
set -x

# Extract date string
date="210422"

# Extract rail features from .osm.pbf to .gpkg
countries=(
    "kenya"
    "tanzania"
    "uganda"
    "zambia"
)
mkdir -p scratch/rail
for country in "${countries[@]}"; do
    osmium tags-filter \
        incoming_data/osm/$country-$date.osm.pbf \
        wnr/railway \
        --overwrite \
        -o scratch/rail/$country-rail.osm.pbf

    OSM_CONFIG_FILE=scripts/preprocess/rail/osmconf_rail.ini ogr2ogr -f GPKG \
        scratch/rail/$country-rail.gpkg \
        scratch/rail/$country-rail.osm.pbf \
        points lines multipolygons
done

# Run script
python scripts/preprocess/rail/process_rail.py

# Replace gpkg with new one which includes costs
python scripts/preprocess/rail/costs_rail.py
