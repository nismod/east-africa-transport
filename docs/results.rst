====================
Analysis and Results
====================
.. Important::
    - This section describes the steps Analysis and Results steps of the East Africa Transport Risk Analysis (EATRA)
    - To implement the EATRA without any changes in existing codes, all data described here should be created and stored exactly as indicated below

Exposure analysis
-----------------
Purpose:
    - Spatially intersect hazards and network assets, which involves overlaying each hazard map layer with each asset geometry and estimating:
        - The magnitude of the hazard at the location of the asset
        - The extent of the asset geometries that are within the hazard areas given by the hazard map layer
    - Write final results to geoparquet files

Execution:
    - Load data as described in `Topological network requirements <https://east-africa-transport.readthedocs.io/en/latest/parameters.html#topological-network-requirements>`_ and `Spatial data requirements <https://east-africa-transport.readthedocs.io/en/latest/parameters.html#spatial-data-requirements>`_, and `Administrative areas with statistics data requirements <https://east-africa-transport.readthedocs.io/en/latest/parameters.html#administrative-areas-with-statistics-data-requirements>`_
    - Run :py:mod:`eatra.exposure.split_networks`

Result:
    - Hazard levels and spatial extents affecting each infrastructure asset across all return periods, climate scenarios, and time epoch of every hazard type.
    - Geoparquet output files in the directory ``/results/hazard_asset_intersection``

Direct damage estimation 
------------------------
Purpose: 
    
Execution:
    - Run :py:mod:`eatra.direct_damages.damage_loss_setup_script`

Indirect economic loss estimation
---------------------------------



Adaptation assessment
---------------------
adaptaion_options_costs.py 
benefit_cost_ratio_estimations.py


Sensitivity analysis
--------------------


Processing outputs and plots
----------------------------
Purpose:
    - Several scripts are written to generate statistics and plots to process results
    - These codes are very specific to the kinds of data and outputs produced from the analysis
    - See the scripts in :py:mod:`eatra.plot`