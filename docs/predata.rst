=================================
Pre-processing data for the model
=================================
.. Important::
    The topological network data and parameters described in `Topological network requirements <https://east-africa-transport.readthedocs.io/en/latest/parameters.html#topological-network-requirements>`_ had to be created from several data sources, all of which are available openly and freely. 

    - This section describes collected datasets that are used to create data for the East Africa Transport Risk Analysis (EATRA)
    - To implement the EATRA pre-processing without any changes in existing codes, all data described here should be created and stored exactly as indicated below
    - It is required to run the Python scripts in the same order as described here
    - If the users want to use the same data and make modifications in values of data then they can follow the steps and codes explained below. Otherwise this whole process can be skipped if the users know how to create the networks in the formats specified in the `Topological network requirements <https://east-africa-transport.readthedocs.io/en/latest/parameters.html#topological-network-requirements>`_
    - Mostly all inputs are read using the Python libraries of `pandas <https://pandas.pydata.org>`_ and `geopandas <http://geopandas.org>`_. The user should familiarise themselves with file reading and writing functions in these libraries. For example most codes use the geopandas function `read_file <http://geopandas.org/io.html>`_  and `to_file <http://geopandas.org/io.html>`_to read and write shapefiles, and the pandas functions `read_excel and to_excel <http://pandas.pydata.org/pandas-docs/stable/user_guide/io.html>`_ and `read_csv and to_csv <http://pandas.pydata.org/pandas-docs/stable/user_guide/io.html>`_ to read and write excel and csv data respectively  

Creating the road network
-------------------------

Data for the road networks were extracted from OpenStreetMap (OSM) and then further processed and cleaned. The steps outlined below describe the processed which can easily be replicated.     

1. Extract data from OSM 
    - Verify the date and geographical extent noted in ``incoming_data/osm/extracts.txt`` 
    - Execute the following script: ``scripts/preprocess/osm/get_osm_data.sh``
    - This creates a .osm.pbf file in ``incoming_data/osm``
    - The file can also be manually downloaded from Geofabrik's free download server here https://download.geofabrik.de/

2. Create road topology
    - Execute the following script: ``scripts/preprocess/road/road.sh``
    - Temporary files are saved in ``scratch/road``   
    - This script creates the ``road`` geopackage file with an ``edges`` layer and a ``nodes`` layer in the folder path ``data/network/``


Creating the rail network
--------------------------


Creating the port and airport network
-------------------------------------


Creating the air network and passenger data
-------------------------------------------


Creating the multi-modal network edges
--------------------------------------
The multi-modal edges can only be created once all the other networks are created. The code inputs the finalized ``road``, ``rail``, ``port`` and ``airport`` files in the ``data/network/`` folder path. The multi-modal network edges are all created by executing 1 Python script:``scripts/preprocess/other_networks/multi_modal.py``


Assigning flows onto networks
-----------------------------
