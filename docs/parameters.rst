==================================
Required data inputs and paramters
==================================
.. Important::
    - This section describes the required data inputs and parameters for the East Africa Transport Risk Analysis (EATRA)
    - To implement the EATRA all data described here should be created with the data properties and column names as described below
    - If these data properties and column names are not provided in the data then the Python scripts will give run-time errors

Spatial data requirements
-------------------------
1. All spatial data inputs must:
    - Be projected to a valid coordinate system. Spatial data with no projection system will give errors 
    - Have valid geometries. Null or Invalid geometries will give errors  

.. Note::
    - The assumed projection system used in the model is EPSG:4326
    - If the users change any spatial data they have to create new data with a valid projection system 

Topological network requirements 
--------------------------------
1. A topological network is defined as a graph composed of nodes and edges  

2. All finalised networks data are created and stored:
    - In the file path - ``/data/network/``
    - As geopackages with post-processed network nodes and edges
    - The created networks are: ``road, rail, port, air``

.. Note::
    The names and properties of the attributes listed below are the essential network parameters for the whole model analysis. If the users wish to replace or change these datasets then they must retain the same names of columns with same types of values as given in the original data. 

    The essential attributes in these networks are listed below. See the data for all attributes and try to recreate your data with similar column names and attribute values.

    Several of these parameters and their values are created from ``incoming_data`` which is explained in the section :doc:`Pre-processing data for the model </predata>`

3. All nodes have the following attributes:
    - ``node_id`` - String Node ID
    - ``iso_code`` - String A3 ISO code of respective country 
    - ``continent`` - Continent of respective country 
    - ``geometry`` - Point geometry of node with projection ESPG:4326
    - Several other atttributes depending upon the specific transport sector

4. All edges have the following attributes:
    - ``edge_id`` - String edge ID
    - ``from_node`` - String node ID that should be present in node_id column
    - ``to_node`` - String node ID that should be present in node_id column
    - ``from_iso`` - String A3 ISO code of respective country of origin 
    - ``to_iso`` - String A3 ISO code of respective country of destination
    - ``from_continent`` - Continent of respective country of origin 
    - ``to_continent`` - Continent of respective country of destination
    - ``geometry`` - LineString geometry of edge with projection ESPG:4326
    - ``length_m`` - Float estimated length in meters of edge
    - ``min_speed`` - Float estimated minimum speed in km/hr on edge
    - ``max_speed`` - Float estimated maximum speed in km/hr on edge
    - ``min_cost`` - Float estimated minimum rehabilitation cost on edge
    - ``max_cost`` - Float estimated maximum rehabilitation cost on edge
    - ``unit_cost`` - String unit of rehabilitation cost (ie USD/km/lane)
    - ``min_tariff`` - Float estimated minimum tariff cost on edge
    - ``max_tariff`` - Float estimated maximum tariff cost on edge 
    - ``unit_tariff`` - String unit of tariff cost (ie USD/ton-km)
    - ``min_flow_cost`` - Float estimated minimum flow cost on edge
    - ``max_flow_cost`` - Float estimated maximum flow cost on edge
    - ``unit_flow_cost`` - String unit of flow cost (ie USD/ton)
    - Several other atttributes depending upon the specific transport sector

5. Attributes only present in roads edges:
    - ``highway`` - String value for road category (motorway, trunk, primary, secondary, or tertiary)
    - ``surface`` - String value for surface material of the road 
    - ``road_cond`` - String value for whether a road is paved or unpaved
    - ``bridge`` - String value for whether a road is a bridge or not
    - ``lanes`` - Float value for number of lanes of 
    - ``width_m`` - Float width of edge in meters

6. Attributes only present in rail edges: 
    - ``status`` - String value for status of the railway (open, proposed, construction, rehabilitation, disused, abandoned)
    - ``is_current`` - True/False value for whether the railway is active in the present 

.. Note::
    We assume that networks are provided as topologically correct connected graphs: each edge
    is a single LineString (may be straight line or more complex line), but must have exactly
    two endpoints, which are labelled as ``from_node`` and ``to_node`` (the values of these
    attributes must correspond to the ``node_id`` of a node).

    Wherever two edges meet, we assume that there is a shared node, matching each of the intersecting edge endpoints. For example, at a t-junction there will be three edges meeting at one node.

    Due to gaps in geometries and connectivity in the raw datasets several dummy nodes and edges have been created in the node and edges join points and lines. For example there are more nodes in the rail network than stations.


OD matrices requirements 
------------------------
1. An OD matrix quantifies the volume (in tons) and value (in US$) is commodities being transported from an origin node to a destination node on a network.   

2. All finalised OD data are created and stored:
    - In the file path - ``/results/flow_paths/``
    - As csv files

3. All nodes have the following attributes:
    - ``origin_id`` - String Node ID of origin node
    - ``destination_id`` - String Node ID of destination node  
    - ``iso3_O`` - String A3 ISO code of origin country 
    - ``iso3_D`` - String A3 ISO code of destination country
    - ``total_value_usd`` - Total value in US$ being transported from origin-destination
    - ``total_tonnage`` - Total value in tonnage being transported from origin-destination
    - Several other commodity specific tonnage and US$ estimates depending upon the commodity classification

.. Note::
    OD network data is a created output from flow allocation modelling. It requires several input datasets and processing steps as described in `Project Final Report <https://transport-links.com/download/final-report-decision-support-systems-for-resilient-strategic-transport-networks-in-low-income-countries/>`_. The data is generated by running the script :py:mod:`eatra.flows.od_matrix_creation`

Hazards data requirements
-------------------------
1. All hazard datasets are stored:
    - In sub-folders in the path - ``/data/hazards/floodmaps``
    - As GeoTiff files
    - See ``/data/hazards/hazard_layers.csv`` for details of all hazard files

2. Single-band GeoTiff hazard raster files should have attributes:
    - values - inundation depth in meters
    - raster grid geometry
    - projection systems: Default assumed = EPSG:4326

.. Note::
    The hazard datasets were obtained from WRI Aqueduct flood product datasets, available openly and freely at https://www.wri.org/data/aqueduct-floods-hazard-maps
    
    Flood depths are given in metres over grid squares (~900 m2 at the Equator). 

If changes are made in the ``/data/hazards/floodmaps`` folder, execute the :py:mod:`eatra.exposure.hazard_layers` script to update the ``hazard_layers_basic.csv``, ``hazard_layers.csv``, ``hazard_layers_chunks.csv``, and ``layers`` sub-folder.  

Administrative areas with statistics data requirements
------------------------------------------------------
1. Boundary datasets are stored:
    - In the path - ``/data/admin_boundaries/``
    - As Geopackages
    - With polygon geometries of boundary with projection ESPG:4326

.. Note::
    The boundary datasets were obtained from GADM, available openly and freely at https://gadm.org/data.html

    Information on the continent assigned to each country was matched using Natural Earth dataset, available openly and freely at: https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/


2. Global lakes and reservoir dataset for map plotting are stored:
    - In the path - ``/data/naturalearth/``
    - As Shapefiles

.. Note::
    The lake and reservoir dataset was obtained from Natural Earth, available openly and freely at https://www.naturalearthdata.com/downloads/110m-physical-vectors/110mlakes-reservoirs/

3. Population raster file is stored:
    - In the path - ``/incoming_data/population/Africa_1km_Population/AFR_PPP_2020_adj_v2.tif``
    - As GeoTiff 

4. Single-band GeoTiff population raster files should have attributes:
    - values - estimates of total number of people per grid square
    - raster grid geometry
    - projection systems: Geographic, WGS84

.. Note::
    The population raster was obtained from Worldpop, available openly and freely at https://hub.worldpop.org/doi/10.5258/SOTON/WP00004 

    The population dataset presents people per pixel (PPP) for 2020 at a spatial resolution of 0.00833333 decimal degrees (approx 1km at the equator) for the continent of Africa. National totals have been adjusted to match UN Population Division estimates


Damage data and costs requirements 
----------------------------------
For assessing direct damages to assets due to flooding we need two sets of information. 

1. Fragility: Failure or damage information that tells us about the percentage of damage an asset would sustain due to hazard exposures.

2. Cost: Rehabilitation or construction costs that can be assigned to each asset, based on some general principles.

Generalised direct damage (fragility) curves vs flood depths are taken from Koks et al., (2019) based on Espinet et al., (2018) for different types of infrastructure assets, specifically: paved roads, unpaved roads, and railway lines. 

All damage curves are stored:
    - In the file - ``/data/damage_curves/damage_curves_transport_flooding.xlsx``
    - And mapped accordingly in - ``/data/damage_curves/asset_damage_curve_mapping.csv``

For rehabilitation or reconstruction cost data the analysis referred to information from a range of cost estimates for different road projects financed by the World Bank and African Development Bank (AfDB). 

Rehabilitation costs are stored: 
    - In the file - ``/data/costs/rehabilitation_costs.xlsx``

Adaptation options and costs requirements
-----------------------------------------
1. All adaptation options input datasets are stored:
    - In the file - ``/data/adaptation/adaptation_options_and_costs.xlsx``

.. Note::
    The adaptation data is very specific and if new options are created then the users will need to change the scripts as well

    If new adaptation options are created then the users will also need to provide updated damage curves in the path ``/data/damage_curves/adaptation_options/damage_curves_transport_flooding_{id}``