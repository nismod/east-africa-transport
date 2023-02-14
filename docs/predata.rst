=================================
Pre-processing data for the model
=================================
.. Important::
    The topological network data and parameters described in :ref:`Topological network requirements <parameters:Topological network requirements>` had to be created from several data sources, all of which are available openly and freely. 

    - This section describes collected datasets that are used to create data for the East Africa Transport Risk Analysis (EATRA)
    - To implement the EATRA pre-processing without any changes in existing codes, all data described here should be created and stored exactly as indicated below
    - It is required to run the Python scripts in the same order as described here
    - If the users want to use the same data and make modifications in values of data then they can follow the steps and codes explained below. Otherwise this whole process can be skipped if the users know how to create the networks in the formats specified in the :ref:`Topological network requirements <parameters:Topological network requirements>`
    - Mostly all inputs are read using the Python libraries of `pandas <https://pandas.pydata.org>`_ and `geopandas <http://geopandas.org>`_. The user should familiarise themselves with file reading and writing functions in these libraries. For example most codes use the geopandas function `read_file <http://geopandas.org/io.html>`_  and `to_file <http://geopandas.org/io.html>`_ to read and write shapefiles, and the pandas functions `read_excel and to_excel <http://pandas.pydata.org/pandas-docs/stable/user_guide/io.html>`_ and `read_csv and to_csv <http://pandas.pydata.org/pandas-docs/stable/user_guide/io.html>`_ to read and write excel and csv data respectively  

Creating the road network
-------------------------

Data for the road networks were extracted from OpenStreetMap (OSM) and then further processed and cleaned. The steps outlined below describe the processed which can easily be replicated.     

1. Extract data from OSM 
    - Verify the date and geographical extent noted in ``incoming_data/osm/extracts.txt`` 
    - Execute the following script: :py:mod:`eatra.preprocess.osm.get_osm_data.sh`
    - This creates a .osm.pbf file in ``incoming_data/osm``
    - The file can also be manually downloaded from Geofabrik's free download server here https://download.geofabrik.de/

2. Create road topology
    - Execute the following script: :py:mod:`eatra.preprocess.road.road.sh`
    - Temporary files are saved in ``scratch/road``   
    - This script creates the ``road`` geopackage file with an ``edges`` layer and a ``nodes`` layer in the folder path ``data/network/``


Creating the rail network
-------------------------
Like the road network, data for the railway network in this study was also extracted from OSM and processed to create topological networks. 

An in-depth analysis of the railway network data was conducted to create a spatially detailed railway network across the four countries consisting of 423 nodes identified as stations, stops and halts and 12,372 kilometres of lines identified and classified into five categories described below.

1. Open: The existing railway routes which were in operation.

2. Disused/Abandoned: The existing railway routes which were no longer in use.

3. Rehabilitation: Existing railway routes which were being rehabilitated following periods of disuse. 

4. Construction: New railway routes and lines which were currently being constructed.

5. Proposed: New railway routes and lines in the proposal phase which are the most likely to proceed due to funding commitments. 

Based on these categories, railway lines were further classified as functional, the railway routes which were in operation, and non-functional, the railway routes which were no longer in use, or were being rehabilitated following periods of disuse.

This final network is the ``rail`` geopackage file with an ``edges`` layer and a ``nodes`` layer in the folder path ``data/network/``

Creating the port network
-------------------------
For the case study region ports are significant hubs linking to the road and railway networks. The waterway ports are either: 

1. Maritime ports: Located along the eastern coastline of the country, connecting it to the routes on the Indian Ocean. 

2. Inland ports: Such ports are concentrated along two main lake waterbodies, which are: 
    A.  Lake Victoria: Where the ports connect Tanzania to other ports in Uganda and Kenya. 
    B.  Lake Tanganyika: Where the ports connect Tanzania to other ports in Burundi, DRC and Zambia. 

While there are several ports concentrated around the case study region, we have selected a few important ports for the case study countries for this analysis. For example, we have excluded ports along Lake Nyasa which borders Tanzania with Malawi and Mozambique because they are quite small and do not transport significant volumes of cargoes. Kenya and Tanzania both have a major port (at Mombasa and Dar Es Salaam respectively), while there are many smaller seaport (and numerous other smaller ports) in these two countries (World Port Source, 2021). Uganda and Zambia are land-locked, so have no seaport activity, although there is significant activity on inland waterways, particularly crossing the major lakes in the region. 

The annual numbers of cargo tonnes reported for ports in Tanzania is based on the annual reporting done in 2015/16 by the Tanzania Port Authority (TPA) (Tanzania Ports Authority, 2016). The statistics for the Port of Mombasa in Kenya are extracted from annual reports and financial statistics published by the Kenya Port Authority (KPA) (Kenya Ports Authority, 2018). Unfortunately, there are no reported statistics and detailed information for most ports in the region. 

The maritime port of Lamu in Kenya has recently been built and is yet to have any significant cargo flows, although this could change in the future (Bachmann & Musembi Kilaka, 2021). Amongst inland waterway ports Mwanza port on Lake Victoria is the most significant port, which has long-distance road and rail corridor links to the Dar es Salaam port on one side and waterway links to Port Bell in Uganda and the Kisumo port in Kenya on the other side. Similarly, the Kigoma port on Lake Tanganyika is a significant port with shipping connecting to ports in Burundi and DRC forming key linkages for routes which carry imports and exports all the way from the Dar es Salaam port.

This final network is the ``port`` geopackage file with an ``edges`` layer and a ``nodes`` layer in the folder path ``data/network/``

Creating the airport network
----------------------------

This project is only concerned with the main airports in the case study countries, with significant volumes of freight or passengers that would have an effect on the long-distance land transport networks. The project scope does not include analysing airline transport within the region, which is in any case quite insignificant, especially for freight transport. The largest airport in the case study region is in Nairobi (Jomo Kenyatta International Airport, Kenya), with other large airport hubs located in Kampala (Entebbe International Airport, Uganda), Dar Es Salaam (Julius Nyerere International Airport, Tanzania), Lusaka (Kenneth Kaunda International Airport, Zambia), Eldoret (Eldoret international Airport, Kenya) and Mombasa (Moi International Airport, Kenya). 

Their estimated annual tonnages of imported and exported freight was taken from country specific reports (Kenya Civil Aviation Authority, 2018), (Uganda Civil Aviation Authority, 2017), (Tanzania Civil Aviation Administration, 2020), (Zambia Airports Corporation Limited, 2018). 

This final network is the ``air`` geopackage file with a ``nodes`` layer in the folder path ``data/network/``


Creating the multi-modal network edges
--------------------------------------
The multi-modal edges can only be created once all the other networks are created. The code inputs the finalized ``road``, ``rail``, ``port`` and ``airport`` files in the ``data/network/`` folder path. The multi-modal network edges are all created by executing 1 Python script: :py:mod:`eatra.preprocess.other_networks.multi_modal`


Assigning flows onto networks
-----------------------------
Flow assignments involve estimating volume (in tons/day) and values (in US$/day) of commodities being moved along transport networks. The specific focus in this project has been on import and export cargo freight only. The detailed methodology of flow assignments is explained in the report `Project Final Report <https://transport-links.com/download/final-report-decision-support-systems-for-resilient-strategic-transport-networks-in-low-income-countries/>`_. In brief the data preparation for flow assignment involves:

1. Creating a country-country Origin-Destination (OD) matrix of imports and exports.

2. Identifying airports, port, road and rail border crossings in each country where imports and export enter and leave.

3. Allocating country-country OD-matrix estimates to border crossings based on known estimates of volumnes of cargo handled at different border crossings.

4. Collecting spatially socio-economic data within a country to infer where economic supply and demand for commodities are concentrated.

5. Disaggregating imports and export volumes to road and rail network nodels in proximity of locations of economic supply and demand to create a node-node OD matrix.

6. Using the multi-modal transport network to assign trade volumes based on a least cost routing algorithm under capacity constraints.

The flow allocation is done by executing 2 Python scripts:
    - :py:mod:`eatra.flows.od_matrix_creation`, which generates an OD matrix as described in :ref:`OD matrices requirements <parameters:OD matrices requirements>`
    - :py:mod:`eatra.flows.flow_assignments`, which generates flow assignment results in the file ``results/flow_paths/``  
