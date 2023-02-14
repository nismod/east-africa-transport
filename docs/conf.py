# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = 'East Africa Transport Risk Analysis'
copyright = '2022, OPSIS'
author = 'OPSIS'

# The full version, including alpha/beta/rc tags
release = '0.1'

# -- Hack for ReadTheDocs and apidoc options -----------------------------------
# This hack is necessary since RTD does not issue `sphinx-apidoc` before running
# If extensions (or modules to document with autodoc) are in another directory,
# DON'T FORGET: Check the box "Install your project inside a virtualenv using
# setup.py install" in the RTD Advanced Settings.
# `sphinx-build -b html . _build/html`. See Issue:
# https://github.com/rtfd/readthedocs.org/issues/1139

# It also appears necessary in order to pass options to sphinx-apidoc which obr
# or setuptools don't currently allow. See issue:
# https://github.com/sphinx-doc/sphinx/issues/1861

import inspect
import os
import subprocess
import sys
# mock modules which we can avoid installing for docs-building
from unittest.mock import MagicMock

# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# sys.path.insert(0, os.path.abspath('.'))


__location__ = os.path.join(os.getcwd(), os.path.dirname(
    inspect.getfile(inspect.currentframe())))

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.join(__location__, '../src'))


class Mock(MagicMock):
    @classmethod
    def __getattr__(cls, name):
        return MagicMock()

mock_modules = [
    'igraph',
    'boltons.iterutils',
    'cartopy',
    'cartopy.crs',
    'cartopy.geodesic',
    'cartopy.io.shapereader',
    'colour',
    'fiona',
    'fiona.crs',
    'geopandas',
    'geopy.distance',
    'matplotlib',
    'matplotlib.lines',
    'matplotlib.patches',
    'matplotlib.pyplot',
    'networkx',
    'openpyxl',
    'rasterio',
    'rasterio.crs',
    'rasterio.dtypes',
    'rasterio.enums',
    'rasterio.errors',
    'rasterio.features',
    'rasterio.mask',
    'rasterio.warp',
    'rasterio.windows',
    'rasterio.vrt',
    'rasterstats',
    'rtree',
    'SALib',
    'SALib.analyze',
    'SALib.sample',
    'SALib.analyze.morris',
    'scipy',
    'scipy.interpolate',
    'scipy.spatial',
    'scipy.stats',
    'shapely',
    'shapely.errors',
    'shapely.geometry',
    'shapely.ops',
    'snkit',
    'snkit.utils',
    'tabula',
    'tqdm',
]
sys.modules.update((mod_name, Mock()) for mod_name in mock_modules)


output_dir = os.path.join(__location__, "api")
module_dir = os.path.join(__location__, "../src/eatra")
cmd_line_template = "sphinx-apidoc -f -M -o {outputdir} {moduledir}"
cmd_line = cmd_line_template.format(outputdir=output_dir, moduledir=module_dir)
subprocess.call(cmd_line.split(" "))


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon',
              'sphinx.ext.inheritance_diagram', 'sphinx.ext.autosummary',
              'sphinx.ext.imgmath', 'sphinx.ext.intersphinx', 'sphinx.ext.todo',
              'sphinx.ext.autosummary', 'sphinx.ext.viewcode',
              'sphinx.ext.coverage', 'sphinx.ext.doctest',
              'sphinx.ext.ifconfig', 'sphinx.ext.graphviz', 'sphinx.ext.autosectionlabel']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store','._*']

# The master toctree document.
master_doc = 'index'

# The suffix of source filenames.
source_suffix = ['.rst', '.md']

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = False

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ['eatra.']

# Make sure the target is unique
autosectionlabel_prefix_document = True

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = False