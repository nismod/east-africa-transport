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


Flow disruption analysis 
------------------------
Purpose:
    - Calculate the indirect economic indirect losses from disruptions of network links
    - Perform a economic criticality assessment of every network link that is potentially damaged by flooding
    - Estimate economic losses in US$/day due to flow rerouting and flow isolations 

Execution:
    - Run the flow assignment results are described in `Assigning flows onto networks <https://east-africa-transport.readthedocs.io/en/latest/predata.html#assigning-flows-onto-networks>`_
    - Run the exposure analysis as described in `Exposure analysis <https://east-africa-transport.readthedocs.io/en/latest/results.html#exposure-analysis>`_
    - Run :py:mod:`eatra.flows.flow_disruption_setup`

Result: 
    - Indirect economic losses csv result files ain the directory ``/results/risk_results/flow_disruptions``


Risk estimation and adaptation assessment 
-----------------------------------------
Purpose:
    - Calculate the direct damages and indirect losses from network failures with and without adaptation options
    - Develop expected annual damages (EAD) and expected annual economic losses (EAEL) estimates
    - Create timeseries and NPV calculations for the scenarios
    - Estimate adaptation options costs and benefits, and benefit-cost ratios

Execution:
    - Run :py:mod:`eatra.analysis.damage_loss_setup_script`
    - Run :py:mod:`eatra.adaptation.benefit_cost_ratio_estimations`

Result: 
    - Direct damages and indirect losses parquet and csv result files as well as summary, timeseries, and npv files in the directory ``/results/risk_results``
    - Above results for each adaptation options in the directory ``/results/adaptation_option_{id}``
    - Adaptation option benefit-cost ratios in the directory ``/results/adaptation_benefits_costs_bcr``


Sensitivity analysis
--------------------
Purpose:
    - Conduct a global sensitivity analysis to capture the influence of a given model parameter on the final risk outcomes 
    - Simulate several realisations of the input parameters and run the analysis for each realisation

Execution: 
    - Run :py:mod:`eatra.sensitivity_analysis.sensitivity_estimation`

Result: 
    - Sensitivity analysis result csv files in the directory ``/results/global_sensitivity``
    

Processing outputs and plots
----------------------------
Purpose:
    - Several scripts are written to generate statistics and plots to process results
    - These codes are very specific to the kinds of data and outputs produced from the analysis
    - See the scripts in :py:mod:`eatra.plot`