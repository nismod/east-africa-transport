#!/usr/bin/env bash
#
# Download country extracts for Kenya, Tanzania, Uganda and Zambia
#

pushd incoming_data/osm

# download extracts
wget -i extracts.txt

countries=(
    "kenya"
    "tanzania"
    "uganda"
    "zambia"
)
# check extracts
for country in "${countries[@]}"; do
    md5sum --check $country-*.osm.pbf.md5
done

popd
