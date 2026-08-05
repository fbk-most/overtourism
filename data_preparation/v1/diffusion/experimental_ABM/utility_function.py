"""
    In this script we are inserting the different 
"""
import numpy as np

def zaelot_term(v_unnormalized_preference: np.ndarray,
                v_zaelot: np.ndarray):
    """
        This term is an external field that is applied to the energy function associated to the user.
        This function essentially adds the perturbation of an external field to the unnormalized preference of the user.
        P = v_unnormalized_preference + v_zaelot
    """
    assert np.shape(v_unnormalized_preference) == np.shape(v_zaelot), f"shape state {np.shape(v_unnormalized_preference)} different from shape perturbation {np.shape(v_zaelot)}"
    v_unnormalized_preference = np.array(v_unnormalized_preference)
    v_zaelot = np.array(v_zaelot)
    return v_unnormalized_preference + v_zaelot