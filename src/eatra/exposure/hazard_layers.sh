#!/usr/bin/env bash

cd ../../data

countries=(
    "kenya"
    "tanzania"
    "uganda"
    "zambia"
)

for country in "${countries[@]}"; do
	( cd "$country" && ls hazards/*.tif >> hazard_layers_basic.csv )  
done

cd ../

python scripts/exposure/hazard_layers.py

cd data

for country in "${countries[@]}"; do
	( cd "$country" && ls layers/*.csv >> hazard_layers_chunks.csv )  
done

cd ../

python scripts/exposure/split_networks.py