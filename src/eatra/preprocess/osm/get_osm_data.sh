#!/usr/bin/env bash
#
# Download country extracts for Kenya, Tanzania, Uganda and Zambia
#

pushd incoming_data/osm

# download extracts
wget -i extracts.txt

popd
