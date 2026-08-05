# Analysis of Fluxes Applied on Vodafone Geometries

# Configure matplotlib to manage memory efficiently
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to save memory
import matplotlib.pyplot as plt
plt.rcParams['figure.max_open_warning'] = 5  # Lower warning threshold
plt.rcParams['figure.dpi'] = 100  # Reduce default DPI to save memory

# P
from pathlib import Path
import pandas as pd

# G
import gc  # For garbage collection
import json  # For saving configuration files
# L
import logging
logger = logging.getLogger(__name__)
# N
import numpy as np
import os
# P
###### Personal Import ######
from data_preparation.diffusion.BusStops import *
from data_preparation.diffusion.Coils import *
from data_preparation.diffusion.constant_names_variables import *
from data_preparation.diffusion.DataHandler import *
from data_preparation.diffusion.DateTime_ import *
from data_preparation.diffusion.GeometryComparisons import *
from data_preparation.diffusion.GenerateFakeFluxes import *
from data_preparation.diffusion.Grid import *
from data_preparation.diffusion.gtfs_routines import *
from data_preparation.diffusion.Istat_data_population import *
from itertools import product
from data_preparation.diffusion.Lattice import *
from data_preparation.diffusion.Markowitz import *
from data_preparation.diffusion.Markowitz_pipeline import *
from data_preparation.diffusion.MeasuresOfImportance import *
from data_preparation.diffusion.Mobility_Hierarchy import *
from data_preparation.diffusion.Mobility_Hierarchy_functions import *
from data_preparation.diffusion.OD import *
from data_preparation.diffusion.OD_pipeline import *
from data_preparation.diffusion.pipeline_diffusione_1_2 import *
from data_preparation.diffusion.PolygonRetrievialOsmnx import *
from data_preparation.diffusion.Presences import compute_presences_average
from data_preparation.diffusion.Plots import * 
from data_preparation.diffusion.Presences import *
from data_preparation.diffusion.ResourceCheck import *
from data_preparation.diffusion.set_config import *
from data_preparation.diffusion.ShapeFiles import *
from data_preparation.diffusion.VodafoneData import *
import digitalhub as dh
import boto3
import io
