#!/usr/bin/env python3
"""
Test script to verify the NaN handling fixes in Mobility_Hierarchy_functions.py
"""

import numpy as np
import pandas as pd
from Mobility_Hierarchy_functions import get_lorenz_curve, get_loubar_threshold

def test_nan_handling():
    print("Testing NaN handling in mobility hierarchy functions...")
    
    # Test case 1: All zeros
    print("\n1. Testing with all zeros:")
    test_df = pd.DataFrame({
        'flows': [0, 0, 0, 0, 0]
    })
    result = get_loubar_threshold(test_df, 'flows')
    print(f"Result: {result}")
    
    # Test case 2: Mix of zeros and valid values
    print("\n2. Testing with mix of zeros and valid values:")
    test_df = pd.DataFrame({
        'flows': [0, 1, 2, 0, 3]
    })
    result = get_loubar_threshold(test_df, 'flows')
    print(f"Result: {result}")
    
    # Test case 3: NaN values
    print("\n3. Testing with NaN values:")
    test_df = pd.DataFrame({
        'flows': [np.nan, 1, 2, np.nan, 3]
    })
    result = get_loubar_threshold(test_df, 'flows')
    print(f"Result: {result}")
    
    # Test case 4: Very small values
    print("\n4. Testing with very small values:")
    test_df = pd.DataFrame({
        'flows': [1e-10, 1e-9, 1e-8, 1e-7, 1e-6]
    })
    result = get_loubar_threshold(test_df, 'flows')
    print(f"Result: {result}")
    
    # Test case 5: Lorenz curve with zeros
    print("\n5. Testing Lorenz curve with zeros:")
    flows = np.array([0, 0, 0, 1, 2])
    x, y, indices = get_lorenz_curve(flows)
    print(f"Lorenz curve - x: {x[:3]}..., y: {y[:3]}..., valid: {np.isfinite(y).all()}")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    test_nan_handling()
