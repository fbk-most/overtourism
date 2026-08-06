from pydantic import BaseModel, Field
from typing import Dict,List,Any,Union
import numpy as np
try:
    import jax.numpy as jnp
    is_jax_available = True
except ImportError:
    is_jax_available = False
try:
    import torch
    is_torch_available = True
except ImportError:
    is_torch_available = False
