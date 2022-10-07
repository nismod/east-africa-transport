====================
Organization of Data
====================
.. Important::
	- This section describes how the data for the East Africa Transport Risk Analysis (EATRA) is organized in folders
	- To implement the EATRA without any changes in existing codes, all data described here should be stored exactly as indicated below

Input and Output folders
------------------------
All data are organised within the folders:
	- ``incoming_data``: Contains data obtained from various organizations, which requires cleaning and processing for setting up the model analysis
	- ``data``: Contains cleaned data that used in the model analysis
	- ``results``: Contains the results of the model analysis
	- ``figures``: Contains maps and graph outputs

.. Note::
	- Changes made to contents of the ``incoming_data`` and ``data`` folders will affect the Python scripts
	- If the users change the file and folder paths within the ``incoming_data`` and ``data`` folders then they will have to modify the Python script that need these files and folders as inputs
	- All data in the ``results`` and ``figures`` folders can be recreated by implmenting the Python scripts