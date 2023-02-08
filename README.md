# East Africa Transport Analysis

This is a project-specific repository for transport analysis in East Africa,
focussing on Kenya, Tanzania, Uganda and Zambia.

The methodology of the model developed here is described in [Project Final Report](https://transport-links.com/download/final-report-decision-support-systems-for-resilient-strategic-transport-networks-in-low-income-countries/>`)

The results of the model are visualised here [East Africa Transport Risk Analysis tool](https://east-africa-infrastructureresilience.org)

## Development

Clone this repository using [GitHub Desktop](https://desktop.github.com/) or on
the command line:

    git clone git@github.com:nismod/east-africa-transport.git

Change directory into the root of the project:

    cd east-africa-transport

Optionally install python packages using pip:

    pip install geopandas fiona snkit tqdm

Alternativel it may be easier to install
[conda](https://docs.conda.io/en/latest/miniconda.html) and then run

    conda env create -f .environment.yml
    conda activate east-africa-transport

Then
- `preprocess/osm/get_osm_data.sh` downloads OpenStreetMap extracts
- `preprocess/rail/rail.sh` extracts a connected and lightly cleaned rail network


## Funding and acknowledgements

This code is being developed as part of a research project funded by UKAID
through the UK Foreign, Commonwealth & Development Office under the High Volume
Transport Applied Research Programme, managed by IMC Worldwide.

The views expressed in this project or accompanying documentation do not
necessarily reflect the UK government’s official policies.
