#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""Setup eata package
"""
from glob import glob
from os.path import basename, splitext

from setuptools import find_packages
from setuptools import setup


def readme():
    """Read README contents
    """
    with open('README.md', encoding='utf8') as f:
        return f.read()


def requirements():
    """Read requirements.txt for install_requires
    """
    with open('requirements.txt', encoding='utf8') as f:
        return [line for line in f.readlines() if line[0] != '#']


setup(
    name='eata',
    use_scm_version=True,
    license='MIT License',
    description='East Africa Transport Adaptation Analysis',
    long_description=readme(),
    long_description_content_type="text/markdown",
    author='Tom Russell',
    author_email='tom.russell@ouce.ox.ac.uk',
    url='https://github.com/nismod/east-africa-transport',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[splitext(basename(path))[0] for path in glob('src/*.py')],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: GIS',
        'Topic :: Utilities',
    ],
    keywords=[
        # eg: 'keyword1', 'keyword2', 'keyword3',
    ],
    setup_requires=[
        'setuptools_scm'
    ],
    install_requires=requirements(),
    extras_require={
        # eg:
        #   'rst': ['docutils>=0.11'],
        #   ':python_version=="2.6"': ['argparse'],
    },
    entry_points={
        'console_scripts': [
            # eg: 'eata = eata.cli:main',
        ]
    },
)
