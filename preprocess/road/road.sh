#!/usr/bin/env bash
#
# Extract roads from OSM
#
set -e
set -x

# Extract date string
date="210422" #this should change to 211027 once raw files are updated

# Extract road features from .osm.pbf to .gpkg
countries=(
    "kenya"
    "tanzania"
    "uganda"
    "zambia"
)
mkdir -p scratch/road
for country in "${countries[@]}"; do
    osmium tags-filter \
        incoming_data/osm/$country-$date.osm.pbf \
        wnr/highway \
        --overwrite \
        -o scratch/road/$country-road.osm.pbf

    OSM_CONFIG_FILE=preprocess/road/osmconf_road.ini ogr2ogr -f GPKG \
        scratch/road/$country-road.gpkg \
        scratch/road/$country-road.osm.pbf \
        points lines multipolygons
done

# Run script
python preprocess/road/process_road.py
